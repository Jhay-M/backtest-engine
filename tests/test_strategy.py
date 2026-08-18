"""Unit tests for the moving-average-crossover strategy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backtester.events import MarketEvent, SignalDirection, SignalEvent
from backtester.strategy import MovingAverageCrossStrategy

_START = datetime(2021, 1, 1, tzinfo=UTC)


def _bars(closes: list[float], symbol: str = "BTC/USD") -> list[MarketEvent]:
    return [
        MarketEvent(_START + timedelta(hours=i), symbol, c, c, c, c, 1.0)
        for i, c in enumerate(closes)
    ]


def _collect(strategy: MovingAverageCrossStrategy, closes: list[float]) -> list[SignalEvent]:
    signals: list[SignalEvent] = []
    for bar in _bars(closes):
        signals.extend(strategy.calculate_signals(bar))
    return signals


@pytest.mark.parametrize(
    ("short", "long"),
    [(0, 5), (5, 5), (6, 5), (-1, 3)],
)
def test_invalid_windows_raise(short: int, long: int) -> None:
    with pytest.raises(ValueError, match="window"):
        MovingAverageCrossStrategy("BTC/USD", short_window=short, long_window=long)


def test_no_signal_before_long_window_is_filled() -> None:
    strategy = MovingAverageCrossStrategy("BTC/USD", short_window=2, long_window=4)
    # Only three bars — never enough to compute the long SMA.
    assert _collect(strategy, [10.0, 9.0, 8.0]) == []


def test_golden_cross_emits_single_long() -> None:
    strategy = MovingAverageCrossStrategy("BTC/USD", short_window=2, long_window=4)
    # V-shape: short SMA sits below the long SMA, then crosses above at bar 6.
    signals = _collect(strategy, [10.0, 9.0, 8.0, 7.0, 6.0, 8.0, 10.0, 12.0, 14.0])

    assert len(signals) == 1
    assert signals[0].direction is SignalDirection.LONG
    assert signals[0].timestamp == _START + timedelta(hours=6)


def test_death_cross_emits_short_when_allowed() -> None:
    strategy = MovingAverageCrossStrategy(
        "BTC/USD", short_window=2, long_window=4, allow_short=True
    )
    # Inverted-V: short SMA above, then crosses below at bar 6.
    signals = _collect(strategy, [2.0, 4.0, 6.0, 8.0, 10.0, 8.0, 6.0, 4.0])

    assert len(signals) == 1
    assert signals[0].direction is SignalDirection.SHORT
    assert signals[0].timestamp == _START + timedelta(hours=6)


def test_death_cross_emits_exit_when_short_disallowed() -> None:
    strategy = MovingAverageCrossStrategy(
        "BTC/USD", short_window=2, long_window=4, allow_short=False
    )
    signals = _collect(strategy, [2.0, 4.0, 6.0, 8.0, 10.0, 8.0, 6.0, 4.0])

    assert len(signals) == 1
    assert signals[0].direction is SignalDirection.EXIT


def test_signals_fire_only_on_transitions() -> None:
    strategy = MovingAverageCrossStrategy("BTC/USD", short_window=2, long_window=4)
    # One golden cross, then a long monotonic climb: still exactly one signal.
    closes = [10.0, 9.0, 8.0, 7.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    assert len(_collect(strategy, closes)) == 1


def test_ignores_events_for_other_symbols() -> None:
    strategy = MovingAverageCrossStrategy("BTC/USD", short_window=2, long_window=4)
    eth = _bars([10.0, 9.0, 8.0, 7.0, 6.0, 8.0, 10.0, 12.0], symbol="ETH/USD")
    signals: list[SignalEvent] = []
    for bar in eth:
        signals.extend(strategy.calculate_signals(bar))
    assert signals == []
