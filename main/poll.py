from datetime import datetime, timezone
from dotenv import load_dotenv
from main.ingestion import CandleProcessor
from models import Candle
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
COUNT = 2      # number of closed candles to return since the worker started
DATABASE_URL = os.environ["DATABASE_URL"]

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
        trading_sessions=["PRE", "RTH", "ATH"],
        real_time_required=True,
    )
    res.raise_for_status()
    return parse_candles(res.json())

def run(data_client):
    step = INTERVAL * 60
    last_acted: dict[str, datetime] = {}
    candle_processor = CandleProcessor(DATABASE_URL)

    with candle_processor.get_db_connection() as conn:
        while True:
            now = datetime.now(timezone.utc)
            # get closest 5m interval registered 
            forming = now.replace(minute=now.minute - (now.minute % INTERVAL), second=0, microsecond=0)

            try:
                for candle in fetch_bar(data_client, SYMBOLS):
                    # drop any registered or forming bar  
                    if last_acted.get(candle.symbol) == candle.timestamp or candle.timestamp >= forming:
                        continue

                    # run trading strategy here
                    
                    # save candle for persistence
                    with conn:
                        candle_processor.process(candle, conn)
                    last_acted[candle.symbol] = candle.timestamp

                    logger.info(
                        "Successfully inserted candle: %s %s %s %s %s %s %s",
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

            time.sleep(step - (time.time() % step) + DELAY)   # wait for next 5m boundary

if __name__ == "__main__":
    try: 
        data_client = create_data_client()
        run(data_client)
    except KeyboardInterrupt:
        print("Terminating program...")
