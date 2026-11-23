from datetime import datetime, timezone
from unittest.mock import Mock, patch

from models import Candle
from main import poll


def candle(symbol="AAPL", timestamp="2026-11-22T15:25:00+00:00"):
    return Candle(
        symbol=symbol,
        timestamp=datetime.fromisoformat(timestamp),
        open=100,
        high=101,
        low=99,
        close=100.5,
        volume=123,
    )


def test_parse_candles_normalizes_values():
    response = {
        "result": [
            {
                "symbol": "AAPL",
                "result": [
                    {
                        "time": "2026-11-22T15:25:00Z",
                        "open": "100.123",
                        "high": "101.987",
                        "low": "99.456",
                        "close": "100.555",
                        "volume": "123",
                    }
                ],
            }
        ]
    }

    candles = poll.parse_candles(response)

    assert len(candles) == 1
    assert candles[0].symbol == "AAPL"
    assert candles[0].timestamp == datetime(2026, 11, 22, 15, 25, tzinfo=timezone.utc)
    assert candles[0].open == 100.12
    assert candles[0].high == 101.99
    assert candles[0].low == 99.46
    assert candles[0].close == 100.56
    assert candles[0].volume == 123


def test_parse_candles_handles_missing_results():
    assert poll.parse_candles({"result": []}) == []
    assert poll.parse_candles({}) == []


def test_fetch_bar_calls_market_data_and_returns_candles():
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {
        "result": [
            {
                "symbol": "AAPL",
                "result": [
                    {
                        "time": "2026-11-22T15:25:00Z",
                        "open": "100",
                        "high": "101",
                        "low": "99",
                        "close": "100.5",
                        "volume": "123",
                    }
                ],
            }
        ]
    }
    data_client = Mock()
    data_client.market_data.get_batch_history_bar.return_value = response

    result = poll.fetch_bar(data_client, ["AAPL"], count=5)

    data_client.market_data.get_batch_history_bar.assert_called_once_with(
        symbols=["AAPL"],
        category=poll.Category.US_STOCK.name,
        timespan=poll.Timespan.M5.name,
        count="5",
        trading_sessions=["RTH"],
        real_time_required=True,
    )
    response.raise_for_status.assert_called_once_with()
    assert result == poll.parse_candles(response.json.return_value)


def test_create_data_client_configures_webull():
    with (
        patch.dict(
            "os.environ",
            {"WEBULL_APP_KEY": "key", "WEBULL_APP_SECRET": "secret"},
            clear=False,
        ),
        patch("main.poll.ApiClient") as api_client_class,
        patch("main.poll.DataClient") as data_client_class,
    ):
        api_client = api_client_class.return_value

        result = poll.create_data_client()

    api_client_class.assert_called_once_with(
        app_key="key",
        app_secret="secret",
        region_id="us",
    )
    api_client.add_endpoint.assert_called_once_with("us", "api.webull.com")
    data_client_class.assert_called_once_with(api_client)
    assert result == data_client_class.return_value


def test_run_returns_before_trading_session():
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 22, 9, 29, tzinfo=tz)

    writer = Mock()

    with (
        patch("main.poll.datetime", FrozenDateTime),
        patch("main.poll.S3CandleWriter", return_value=writer),
        patch("main.poll.fetch_bar") as fetch_bar,
    ):
        poll.run(Mock())

    fetch_bar.assert_not_called()
    writer.upload_batch.assert_not_called()


def test_run_returns_after_trading_session():
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 22, 11, 0, tzinfo=tz)

    writer = Mock()

    with (
        patch("main.poll.datetime", FrozenDateTime),
        patch("main.poll.S3CandleWriter", return_value=writer),
        patch("main.poll.fetch_bar") as fetch_bar,
    ):
        poll.run(Mock())

    fetch_bar.assert_not_called()
    writer.upload_batch.assert_not_called()


def test_run_uploads_only_eligible_completed_candles():
    class FrozenDateTime(datetime):
        eastern_calls = 0

        @classmethod
        def now(cls, tz=None):
            if tz is timezone.utc:
                return cls(2026, 11, 22, 15, 30, tzinfo=timezone.utc)

            cls.eastern_calls += 1
            if cls.eastern_calls >= 4:
                return cls(2026, 11, 22, 11, 0, 2, tzinfo=poll.EASTERN)
            return cls(2026, 11, 22, 10, 30, tzinfo=poll.EASTERN)

    eligible = candle()
    forming = candle(timestamp="2026-11-22T15:30:00+00:00")
    before_session = candle(timestamp="2026-11-22T14:29:00+00:00")
    after_session = candle(timestamp="2026-11-22T16:00:00+00:00")
    wrong_date = candle(timestamp="2026-11-21T15:25:00+00:00")
    writer = Mock()
    writer.candle_count = 1
    writer.symbols = {"AAPL"}

    with (
        patch("main.poll.datetime", FrozenDateTime),
        patch("main.poll.S3CandleWriter", return_value=writer),
        patch("main.poll.fetch_bar", return_value=[
            eligible,
            forming,
            before_session,
            after_session,
            wrong_date,
        ]),
    ):
        poll.run(Mock())

    writer.upload_batch.assert_called_once()
    uploaded_candles, trading_date = writer.upload_batch.call_args.args
    assert uploaded_candles == [eligible]
    assert trading_date == datetime(2026, 11, 22).date()
