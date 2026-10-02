from contextlib import contextmanager
from datetime import datetime
from models import Candle
from pathlib import Path

import argparse
import csv
import logging
import os
import psycopg2
import time

REQUIRED_DATA_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}

# implement logger config
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)

class CandleProcessor:
    def __init__(self, database_url: str):
        self.database_url = database_url

    @contextmanager   # treat get_db_connection yield as connection object
    def get_db_connection(self):
        connection = psycopg2.connect(self.database_url)
        try:
            with connection: yield connection   # by default: commit if successful, else rollback
        finally:
            connection.close()

    def process(self, candle: Candle):
        """
        Processes and stores raw candle data in PSQL
        """
        query = """
            INSERT INTO candles (symbol, timestamp, open, high, low, close, volume)
            VALUES (
                %(symbol)s,
                %(timestamp)s,
                %(open)s,
                %(high)s,
                %(low)s,
                %(close)s,
                %(volume)s
            )
            ON CONFLICT (symbol, timestamp)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume;
        """

        data = {
            "symbol": candle.symbol,
            "timestamp": candle.timestamp,
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }

        try: 
            with self.get_db_connection() as connection:
                cursor = connection.cursor()
                cursor.execute(query, data)

        except psycopg2.Error:
            logger.exception(
                "Database error while processing candle symbol=%s timestamp=%s", 
                candle.symbol, 
                candle.timestamp
            ); raise

def load_csv(file_path: str, processor: CandleProcessor):
        """
        Loads candle data from `self.file_path`
        """
        processed_count = 0 
        start_time = time.monotonic() 
        logger.info("Starting ingestion file=%s", file_path)

        try:
            with open(file_path, "r", newline="") as file:
                reader = csv.DictReader(file)
                symbol = Path(file_path).stem.upper()

                if reader.fieldnames:
                    missing = REQUIRED_DATA_COLUMNS - set(reader.fieldnames)
                    if missing:
                        logger.error("Missing required columns file=%s missing=%s", file_path, sorted(missing))
                        raise ValueError(f"Missing required columns: {sorted(missing)}")
                else: 
                    logger.error("CSV does not contain headers file=%s", file_path)
                    raise ValueError("CSV does not contain headers")

                for row_number, row in enumerate(reader, start=2):
                    try:
                        candle = Candle(
                            symbol=symbol,
                            timestamp=datetime.strptime(
                                row["timestamp"],
                                "%Y-%m-%d %H:%M:%S",
                            ),
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=int(row["volume"]),
                        )

                        processor.process(candle)
                        processed_count += 1

                    except (ValueError, TypeError) as exc:
                        logger.error("Invalid CSV data file=%s row=%s error=%s", file_path, row_number, exc)
                        raise ValueError(f"Invalid data on CSV row {row_number}: {exc}") from exc

        except OSError: 
            logger.exception("Failed to read CSV file=%s", file_path) 
            raise

        duration = time.monotonic() - start_time
        logger.info("CSV ingestion complete file=%s symbol=%s rows=%s duration=%.2fs", 
                    file_path, 
                    symbol, 
                    processed_count, 
                    duration, 
        )

        return processed_count

def load_local_data(data_directory: str, processor: CandleProcessor) -> None: 
    """ Load all CSV files in the data directory """ 
    logger.info("Starting local data ingestion directory=%s", data_directory)

    start_time = time.monotonic() 
    data_path = Path(data_directory) 
    
    if not data_path.exists():
        logger.error("Data could not be found directory=%s", data_directory)
        raise FileNotFoundError( f"Directory does not exist: {data_directory}") 
    
    csv_files = sorted(data_path.glob("*.csv")) 
    if not csv_files: 
        logger.error("No CSV files found directory=%s", data_directory)
        raise FileNotFoundError(f"No files found in directory: {data_directory}") 
    
    total_processed = 0 
    for csv_file in csv_files: 
        count = load_csv(str(csv_file), processor) 
        total_processed += count 
        print(f"Loaded {count} candles for " f"{csv_file.stem.upper()}") 

    duration = time.monotonic() - start_time
    logger.info( 
        "Local data ingestion completed " "files=%s rows=%s duration=%.2fs", 
        len(csv_files), 
        total_processed, 
        duration
    )

# TODO: fetch market data from OpenAPI via webull?
def load_api_data(processor: CandleProcessor) -> None:
    raise NotImplementedError()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--dir", type=str, default="data")

    database_url = os.getenv("DATABASE_URL")
    if not database_url: 
        logger.critical("Missing DATABASE_URL environment variable")
        raise ValueError("DATABASE_URL credential required")

    args = parser.parse_args()
    processor = CandleProcessor(database_url)

    if args.local: load_local_data(args.dir, processor) 
    else: load_api_data(processor)