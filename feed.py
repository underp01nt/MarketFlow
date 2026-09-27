import argparse
import csv
import time
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel

REQUIRED_DATA_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}

class Candle(BaseModel):
    timestamp: datetime
    
    # OHLCV
    open: float
    high: float
    low: float
    close: float
    volume: int

    # bar changes
    bar_change: float
    bar_change_pct: float

class MarketDataFeed:
    """
    * `file_path` -- path to market CSV data 
    * `interval` -- replay speed (in seconds)
    """

    def __init__(self, file_path: str, interval: float = 1.0):
        self.file_path = Path(file_path)  
        self.interval = interval

        if not self.file_path.exists():
            raise FileNotFoundError(f"Cannot find file: {self.file_path}")

    def load(self):
        """
        Loads candle data from `self.file_path`
        """
        candles = []

        with self.file_path.open("r", newline="") as file:
            reader = csv.DictReader(file)

            if reader.fieldnames:
                missing = REQUIRED_DATA_COLUMNS - set(reader.fieldnames)
                if missing:
                    raise ValueError(f"CSV does not contain the required columns: {sorted(missing)}")
            else: raise ValueError("CSV does not contain headers")
            

            for row_number, row in enumerate(reader, start=2):
                try:
                    candle = Candle(
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

                    candles.append(candle)

                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Invalid data on CSV row {row_number}: {exc}"
                    ) from exc

        return candles

    @staticmethod
    def _emit(candle: Candle):
        print(
            f"{candle.timestamp} | "
            f"O {candle.open:.2f} "
            f"H {candle.high:.2f} "
            f"L {candle.low:.2f} "
            f"C {candle.close:.2f} "
            f"V {candle.volume}"
        )

    def replay(self):
        """
        Replays 1m candles every `self.interval` seconds
        """
        candles = self.load()

        print(f"{len(candles)} total candles")
        print(f"Replay interval: {self.interval} seconds")
        print()
        print("*** Starting market-data replay... ***")
        print()

        for candle in candles:
            self._emit(candle)
            time.sleep(self.interval)

        print()
        print("REPLAY COMPLETE")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="data/es_1m.csv", help="Path to the market-data CSV")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between candles")

    args = parser.parse_args()
    file_path, interval = args.file, args.interval

    feed = MarketDataFeed(file_path=file_path, interval=interval)
    feed.replay()
