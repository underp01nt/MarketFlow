"""
To poll, validate, and store SQS message into DB before deletion 

"""

from botocore.exceptions import BotoCoreError, ClientError
from models import Candle
from processor.ingest import CandleProcessor

import boto3
import json
import logging
import os
import time

# configure worker logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("marketflow.worker")

def start_SQS_worker():
    queue_url = os.environ["SQS_QUEUE_URL"]
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    # create SQS client with configured AWS credentials
    sqs = boto3.client("sqs", region_name=region)
    processor = CandleProcessor(database_url=os.environ["DATABASE_URL"])

    logger.info("SQS worker started")

    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=30,
            )

            for message in response.get("Messages", []):
                try:
                    candle = Candle(**json.loads(message["Body"]))

                    with processor.get_db_connection() as connection:
                        processor.process(candle, connection)

                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message["ReceiptHandle"],
                    )
                    logger.info("Processed candle: %s", candle.symbol)

                except Exception:
                    logger.exception("Message processing failed")

        except (BotoCoreError, ClientError):
            logger.exception("SQS request failed")
            time.sleep(5)

if __name__ == "__main__":
    start_SQS_worker()