"""Unit tests for the historic CSV data handler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backtester.data import HistoricCSVDataHandler
from backtester.events import MarketEvent

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "BTCUSD_1h_sample.csv"
_START = datetime(2021, 1, 1, tzinfo=UTC)


def _bar(i: int) -> MarketEvent:
    return MarketEvent(
        timestamp=_START + timedelta(hours=i),
        symbol="BTC/USD",
        open=100.0 + i,
        high=101.0 + i,
        low=99.0 + i,
        close=100.5 + i,
        volume=1.0,
    )


def test_sample_file_is_present() -> None:
    assert SAMPLE.exists(), "run scripts/generate_sample_data.py"


def test_streams_every_bar_in_chronological_order() -> None:
    handler = HistoricCSVDataHandler(SAMPLE, "BTC/USD")
    streamed: list[MarketEvent] = []
    while True:
        bar = handler.update_bars()
        if bar is None:
            break
        streamed.append(bar)

    assert len(streamed) == 720
    timestamps = [b.timestamp for b in streamed]
    assert timestamps == sorted(timestamps)
    assert all(b.symbol == "BTC/USD" for b in streamed)


def test_get_latest_bars_windows_only_seen_bars() -> None:
    bars = [_bar(i) for i in range(5)]
    handler = HistoricCSVDataHandler.from_bars(bars, "BTC/USD")

    assert handler.get_latest_bars("BTC/USD") == []  # nothing streamed yet

    handler.update_bars()
    handler.update_bars()
    assert handler.get_latest_bars("BTC/USD", 1) == [bars[1]]
    assert handler.get_latest_bars("BTC/USD", 5) == [bars[0], bars[1]]  # only 2 seen
    assert handler.get_latest_bars("BTC/USD", 0) == []
    assert handler.get_latest_bars("ETH/USD", 5) == []  # wrong symbol


def test_continue_backtest_and_exhaustion() -> None:
    handler = HistoricCSVDataHandler.from_bars([_bar(0)], "BTC/USD")

    # Capture into locals so the property is read fresh around each mutation.
    pending = handler.continue_backtest
    first = handler.update_bars()
    exhausted = handler.continue_backtest
    beyond = handler.update_bars()

    assert pending is True
    assert first is not None
    assert exhausted is False
    assert beyond is None


def test_missing_column_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("timestamp,open,high,low,close\n2021-01-01,1,2,0,1\n")
    with pytest.raises(ValueError, match="missing required columns"):
        HistoricCSVDataHandler(bad, "BTC/USD")


def test_duplicate_timestamps_raise(tmp_path: Path) -> None:
    dup = tmp_path / "dup.csv"
    dup.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2021-01-01T00:00:00Z,1,2,0,1,5\n"
        "2021-01-01T00:00:00Z,1,2,0,1,5\n"
    )
    with pytest.raises(ValueError, match="duplicate timestamps"):
        HistoricCSVDataHandler(dup, "BTC/USD")


def test_unsorted_csv_is_sorted_on_load(tmp_path: Path) -> None:
    unsorted = tmp_path / "unsorted.csv"
    unsorted.write_text(
        "timestamp,open,high,low,close,volume\n"
        "2021-01-01T02:00:00Z,3,3,3,3,1\n"
        "2021-01-01T00:00:00Z,1,1,1,1,1\n"
        "2021-01-01T01:00:00Z,2,2,2,2,1\n"
    )
    handler = HistoricCSVDataHandler(unsorted, "BTC/USD")
    closes = []
    while True:
        bar = handler.update_bars()
        if bar is None:
            break
        closes.append(bar.close)
    assert closes == [1.0, 2.0, 3.0]
