"""The engine's per-bar sequence: fill pending -> mark -> signal -> submit.

Minimal in-test fakes stand in for the four components so the loop's wiring and
its next-bar-open timing can be verified in isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from backtester.config import BacktestConfig
from backtester.data import DataHandler
from backtester.engine import BacktestEngine
from backtester.events import (
    FillEvent,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderType,
    SignalDirection,
    SignalEvent,
)
from backtester.execution import ExecutionHandler
from backtester.portfolio import Portfolio
from backtester.strategy import Strategy

_START = datetime(2021, 1, 1, tzinfo=UTC)
_UNUSED = Path("unused.csv")


def _bar(i: int, open_: float, close: float) -> MarketEvent:
    return MarketEvent(_START + timedelta(hours=i), "BTC/USD", open_, open_, close, close, 1.0)


def _config() -> BacktestConfig:
    return BacktestConfig(data_path=_UNUSED, symbol="BTC/USD")


class FakeData(DataHandler):
    """Streams a fixed list of bars once."""

    def __init__(self, bars: list[MarketEvent]) -> None:
        self._bars = bars
        self._i = -1

    def update_bars(self) -> MarketEvent | None:
        self._i += 1
        return self._bars[self._i] if self._i < len(self._bars) else None

    def get_latest_bars(self, symbol: str, n: int = 1) -> list[MarketEvent]:
        return self._bars[max(0, self._i - n + 1) : self._i + 1]

    @property
    def continue_backtest(self) -> bool:
        return self._i < len(self._bars) - 1


class FakeStrategy(Strategy):
    """Emits one LONG signal on the first bar it sees."""

    def __init__(self) -> None:
        self._fired = False

    def calculate_signals(self, event: MarketEvent) -> list[SignalEvent]:
        if self._fired:
            return []
        self._fired = True
        return [SignalEvent(event.timestamp, event.symbol, SignalDirection.LONG)]


class RecordingPortfolio(Portfolio):
    """Records the callback sequence and sizes any signal to one unit."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fills: list[FillEvent] = []

    def on_market(self, event: MarketEvent) -> None:
        self.calls.append("market")

    def on_signal(self, event: SignalEvent) -> OrderEvent | None:
        self.calls.append("signal")
        return OrderEvent(
            event.timestamp, event.symbol, OrderType.MARKET, OrderSide.BUY, quantity=1.0
        )

    def on_fill(self, event: FillEvent) -> None:
        self.calls.append("fill")
        self.fills.append(event)

    def equity_curve(self) -> pd.DataFrame:
        return pd.DataFrame({"equity": [1.0]})


class FakeExecution(ExecutionHandler):
    """Defers fills to the next bar's open, like the real handler."""

    def __init__(self) -> None:
        self._pending: list[OrderEvent] = []

    def submit_order(self, order: OrderEvent) -> None:
        self._pending.append(order)

    def on_market(self, event: MarketEvent) -> list[FillEvent]:
        fills = [
            FillEvent(event.timestamp, o.symbol, o.side, o.quantity, event.open, 0.0, 0.0)
            for o in self._pending
        ]
        self._pending = []
        return fills


def test_per_bar_sequence_and_next_bar_open_fill() -> None:
    bars = [_bar(0, open_=100.0, close=105.0), _bar(1, open_=110.0, close=115.0)]
    portfolio = RecordingPortfolio()
    engine = BacktestEngine(
        data=FakeData(bars),
        strategy=FakeStrategy(),
        portfolio=portfolio,
        execution=FakeExecution(),
        config=_config(),
    )

    engine.run()

    # Bar 0: mark, then signal (order submitted). Bar 1: fill, then mark.
    assert portfolio.calls == ["market", "signal", "fill", "market"]
    # The fill is priced at bar 1's open (110), never bar 0's close (105).
    assert len(portfolio.fills) == 1
    assert portfolio.fills[0].fill_price == 110.0


def test_order_on_final_bar_never_fills() -> None:
    # The strategy fires on the only bar, so its order has no next bar to fill on.
    portfolio = RecordingPortfolio()
    engine = BacktestEngine(
        data=FakeData([_bar(0, open_=100.0, close=105.0)]),
        strategy=FakeStrategy(),
        portfolio=portfolio,
        execution=FakeExecution(),
        config=_config(),
    )

    engine.run()

    assert portfolio.fills == []
    assert "fill" not in portfolio.calls
