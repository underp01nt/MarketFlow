"""
To poll, validate, and store SQS message into DB before deletion 

"""

from botocore.exceptions import BotoCoreError, ClientError
from models import Candle
from processor.ingest import CandleProcessor
from pydantic import ValidationError
from threading import Event

import boto3
import json
import logging
import os
import signal
import time

# if worker asked to stop, call for shutdown
shutdown = Event()

# configure worker logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("marketflow.worker")


"""
        WORKER METHODS

"""

def handle_shutdown(signum, frame):
    logger.info("Shutdown requested by signal %s at %s", signum, frame)
    shutdown.set()

def start_SQS_worker():
    queue_url = os.environ["SQS_QUEUE_URL"]
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    # create SQS client with configured AWS credentials
    sqs = boto3.client("sqs", region_name=region)
    processor = CandleProcessor(database_url=os.environ["DATABASE_URL"])

    logger.info("SQS worker started")

    while not shutdown.is_set():
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=30,
            )

            for message in response.get("Messages", []):
                if shutdown.is_set(): break

                try:
                    candle = Candle(**json.loads(message["Body"]))

                    with processor.get_db_connection() as connection:
                        processor.process(candle, connection)

                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message["ReceiptHandle"],
                    )
                    logger.info("Processed candle: %s", candle.symbol)

                except (json.JSONDecodeError, ValidationError):
                    # leave invalid messages for SQS redrive to the DLQ
                    logger.exception("Invalid candle message")

                except Exception:
                    logger.exception("Message processing failed")

        except (BotoCoreError, ClientError):
            logger.exception("SQS request failed")
            shutdown.wait(5)

    logger.info("SQS worker stopped")

if __name__ == "__main__":
    # register handler for any termination + interrupts
    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    start_SQS_worker()