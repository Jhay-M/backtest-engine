"""The event loop dispatches each event kind to the right component in order.

Minimal in-test fakes stand in for the four components so the loop's wiring can
be verified without any concrete strategy or data implementation existing yet.
"""

from __future__ import annotations

from datetime import datetime, timedelta

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

_START = datetime(2021, 1, 1)


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


class FakeData(DataHandler):
    """Streams a fixed list of bars once."""

    def __init__(self, bars: list[MarketEvent]) -> None:
        self._bars = bars
        self._i = -1

    def update_bars(self) -> MarketEvent | None:
        self._i += 1
        if self._i >= len(self._bars):
            return None
        return self._bars[self._i]

    def get_latest_bars(self, symbol: str, n: int = 1) -> list[MarketEvent]:
        return self._bars[max(0, self._i - n + 1) : self._i + 1]

    @property
    def continue_backtest(self) -> bool:
        return self._i < len(self._bars) - 1


class FakeStrategy(Strategy):
    """Emits one LONG signal on the very first bar it sees."""

    def __init__(self) -> None:
        self._fired = False

    def calculate_signals(self, event: MarketEvent) -> list[SignalEvent]:
        if self._fired:
            return []
        self._fired = True
        return [SignalEvent(event.timestamp, event.symbol, SignalDirection.LONG)]


class RecordingPortfolio(Portfolio):
    """Records the sequence of callbacks and sizes any signal to one unit."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def on_market(self, event: MarketEvent) -> None:
        self.calls.append("market")

    def on_signal(self, event: SignalEvent) -> OrderEvent | None:
        self.calls.append("signal")
        return OrderEvent(
            event.timestamp, event.symbol, OrderType.MARKET, OrderSide.BUY, quantity=1.0
        )

    def on_fill(self, event: FillEvent) -> None:
        self.calls.append("fill")

    def equity_curve(self) -> pd.DataFrame:
        return pd.DataFrame({"equity": [100.0, 101.0]})


class FakeExecution(ExecutionHandler):
    """Fills at a flat price with token costs."""

    def execute_order(self, event: OrderEvent) -> FillEvent:
        return FillEvent(
            timestamp=event.timestamp,
            symbol=event.symbol,
            side=event.side,
            quantity=event.quantity,
            fill_price=100.0,
            commission=0.1,
            slippage=0.05,
        )


def _config(tmp_path: object) -> BacktestConfig:
    return BacktestConfig(data_path=str(tmp_path))  # type: ignore[arg-type]


def test_full_event_cascade_in_order(tmp_path: object) -> None:
    portfolio = RecordingPortfolio()
    engine = BacktestEngine(
        data=FakeData([_bar(0), _bar(1)]),
        strategy=FakeStrategy(),
        portfolio=portfolio,
        execution=FakeExecution(),
        config=_config(tmp_path),
    )

    curve = engine.run()

    # Bar 0 cascades market -> signal -> (order) -> fill; bar 1 is market-only.
    assert portfolio.calls == ["market", "signal", "fill", "market"]
    # A fill is never processed before the signal that produced it.
    assert portfolio.calls.index("signal") < portfolio.calls.index("fill")
    assert list(curve.columns) == ["equity"]
