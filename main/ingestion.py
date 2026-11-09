from datetime import date, datetime, timezone
from models import Candle

import boto3
import json
import logging
import os
import uuid

# get logger config name
logger = logging.getLogger(__name__)
BUCKET = "marketflow-data"

class S3CandleWriter:
    def __init__(self, bucket: str = BUCKET):
        # configure basic bucket + s3 config
        self.bucket = bucket
        self.run_id = str(uuid.uuid4())
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.s3 = boto3.client("s3", region_name=self.region)

        # some relevant candle metadata
        self.candle_count = 0
        self.symbols: set[str] = set()

    def upload_batch(self, candles: list[Candle], trading_date: date) -> list[str]:
        """
        Adds today's available candle batch to S3
        """
        if not candles:
            return []

        # group candles by their associated symbol
        grouped_candles: dict[str, list[Candle]] = {}

        # {"symbolA": list[Candle], ...}
        for candle in candles:
            grouped_candles.setdefault(candle.symbol, []).append(candle)

        timestamp = datetime.now(timezone.utc)
        timestamp_label = timestamp.strftime("%Y%m%dT%H%M%S%fZ")

        uploaded_keys = []
        for symbol, symbol_candles in grouped_candles.items():
            records = [
                {
                    "symbol": candle.symbol,
                    "timestamp": candle.timestamp.isoformat(),
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                }
                for candle in symbol_candles
            ]

            # form the body and the key with the candles data before adding object to s3 bucket
            body = "\n".join(json.dumps(record, default=str) for record in records) + "\n"
            key = (
                f"candles/{trading_date.isoformat()}/{symbol}/"
                f"batch={self.run_id}-{timestamp_label}.jsonl"
            )

            self.s3.put_object(Bucket=self.bucket, Key=key, 
                Body=body.encode("utf-8"),
                ContentType="application/x-ndjson",
            )

            uploaded_keys.append(key)
            self.symbols.add(symbol)
            self.candle_count += len(symbol_candles)

            logger.info(
                "Uploaded %s candles for %s to s3://%s/%s",
                len(symbol_candles), symbol, self.bucket, key
            )

        return uploaded_keys