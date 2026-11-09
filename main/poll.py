from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

from models import Candle
from main.ingestion import S3CandleWriter
from webull.core.client import ApiClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan
from webull.data.data_client import DataClient

import logging
import os
import time

# initialize logging + env variables
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# silence webull initialization logging 
logging.getLogger("webull.core.http.initializer.client_initializer").setLevel(logging.WARNING)

load_dotenv()

SYMBOLS = ["AAPL"]
INTERVAL = 5   # x-min interval
DELAY = 2      # seconds to finalize closing bar 
COUNT = 5      # number of latest candles to return

# relevant S3 configs
BUCKET = os.getenv("S3_BUCKET", "marketflow-data")
EASTERN = ZoneInfo("America/New_York")
SESSION_START = datetime.strptime("09:30", "%H:%M").time()
SESSION_END = datetime.strptime("11:00", "%H:%M").time()

def create_data_client() -> DataClient:
    # create the API client
    api_client = ApiClient(
        app_key=os.environ["WEBULL_APP_KEY"], 
        app_secret=os.environ["WEBULL_APP_SECRET"], 
        region_id="us"
    )
    api_client.add_endpoint("us", "api.webull.com")
    return DataClient(api_client)

def parse_candles(response: dict) -> list[Candle]:
    candles = []

    for item in response.get("result", []):
        symbol = item["symbol"]

        for bar in item.get("result", []):
            # parse timezone, then reformat to ISO
            timestamp = bar["time"].replace("Z", "+00:00")
            timestamp = datetime.fromisoformat(timestamp)

            candles.append(
                Candle(
                    symbol=symbol,
                    timestamp=timestamp,    # the timestamp is in UTC
                    open=round(float(bar["open"]), 2),
                    high=round(float(bar["high"]), 2),
                    low=round(float(bar["low"]), 2),
                    close=round(float(bar["close"]), 2), 
                    volume=int(bar["volume"]),
                )
            )

    return candles

def fetch_bar(data_client: DataClient, symbols: list[str], count: int = COUNT) -> list[Candle]:
    res = data_client.market_data.get_batch_history_bar(
        symbols=symbols,
        category=Category.US_STOCK.name,
        timespan=Timespan.M5.name,  # 5m candle data
        count=str(count),
        trading_sessions=["RTH"],
        real_time_required=True,
    )
    res.raise_for_status()
    return parse_candles(res.json())

def run(data_client):
    # configure writer and date
    writer = S3CandleWriter(bucket=BUCKET)
    trading_date = datetime.now(EASTERN).date()

    if datetime.now(EASTERN).time() < SESSION_START:
        logger.error("Task started before the scheduled session")
        return

    if datetime.now(EASTERN).time() >= SESSION_END:
        logger.info("Trading session has already ended")
        return
    
    step = INTERVAL * 60
    last_acted: dict[str, datetime] = {}
    while True:
        now = datetime.now(timezone.utc)
        
        # get closest 5m interval registered 
        forming = now.replace(minute=now.minute - (now.minute % INTERVAL), second=0, microsecond=0)

        try:
            eligible_candles = []

            for candle in fetch_bar(data_client, SYMBOLS):
                # only process completed candles from today's RTH session
                candle_time = candle.timestamp.astimezone(EASTERN)
                if (
                        candle_time.date() != trading_date 
                    or candle_time.time() < SESSION_START
                    or candle_time.time() >= SESSION_END 
                    or candle.timestamp >= forming): continue

                # consume newest candle, do not register uploaded old candles
                last_timestamp = last_acted.get(candle.symbol)
                if last_timestamp is not None and candle.timestamp <= last_timestamp:
                    continue

                eligible_candles.append(candle)

                """  !! run trading strategy here !!  """
                
            # upload batch of candle data to S3
            if eligible_candles:
                eligible_candles.sort(key=lambda candle: (candle.symbol, candle.timestamp))
                
                _ = writer.upload_batch(eligible_candles, trading_date)

                for candle in eligible_candles:
                    last_acted[candle.symbol] = candle.timestamp

                    logger.info(
                        "Successfully uploaded candle: %s %s %s %s %s %s %s",
                        candle.symbol,
                        candle.timestamp,
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                    )

        except Exception:
            logger.exception("Polling cycle failed; retrying next cycle")

        deadline = datetime.combine(trading_date, SESSION_END, tzinfo=EASTERN) + timedelta(seconds=DELAY)
        # run until end of trading session
        if datetime.now(EASTERN) >= deadline: break
        # otherwise, wait for next 5m boundary
        time.sleep(step - (time.time() % step) + DELAY)   

    logger.info(
        "Polling session completed | total candles uploaded: %s; symbols: %s",
        writer.candle_count,
        sorted(writer.symbols),
    )

if __name__ == "__main__":
    data_client = create_data_client()
    run(data_client)
