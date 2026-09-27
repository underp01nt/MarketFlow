from datetime import datetime
from pathlib import Path
from models import Candle

import argparse
import csv
import time

REQUIRED_DATA_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}

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

    def load(self, symbol: str):
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

                    candles.append(candle)

                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Invalid data on CSV row {row_number}: {exc}"
                    ) from exc

        return candles

    @staticmethod
    def _emit(candle: Candle, curr_bar, prev_bar):
        print(
            f"{candle.timestamp} |  "
            f"O {candle.open:8.2f} "
            f"H {candle.high:8.2f} "
            f"L {candle.low:8.2f} "
            f"C {candle.close:8.2f} "
            f"V {candle.volume:<6d} "
            f" {curr_bar - prev_bar:+.2f} ({curr_bar / prev_bar - 1:+.2%})"
        )

    def replay(self, symbol: str):
        """
        Replays 1m candles every `self.interval` second/s
        """
        candles = self.load(symbol)

        print(f"{len(candles)} total candles")
        print(f"Replay interval: {self.interval} seconds")
        print()
        print(f"*** Starting market-data replay for {symbol}... ***")
        print()

        prev_candle = candles[0]
        for candle in candles[1:]:
            self._emit(candle, candle.close, prev_candle.close)
            prev_candle = candle
            time.sleep(self.interval)

        print()
        print("REPLAY COMPLETE")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="data/es_1m.csv", help="Path to the market-data CSV")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between candles")
    parser.add_argument("--symbol", default="FLOW", type=str)

    args = parser.parse_args()
    file_path, interval, symbol = args.file, args.interval, args.symbol

    feed = MarketDataFeed(file_path=file_path, interval=interval)
    feed.replay(symbol)
