from contextlib import contextmanager
from models import Candle

import logging
import psycopg2

REQUIRED_DATA_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}

# get logger config name
logger = logging.getLogger(__name__)

class CandleProcessor:
    def __init__(self, database_url: str):
        self.database_url = database_url

    @contextmanager   # treat get_db_connection yield as connection object
    def get_db_connection(self):
        connection = psycopg2.connect(self.database_url)
        try:
            yield connection
        finally:
            connection.close()

    def process(self, candle: Candle, connection):
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
            with connection.cursor() as cursor:
                cursor.execute(query, data)

        except psycopg2.Error:
            logger.exception(
                "Database error while processing candle symbol=%s timestamp=%s", 
                candle.symbol, 
                candle.timestamp
            ); raise