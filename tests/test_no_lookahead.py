"""The no-lookahead guarantee — the single most important correctness test.

The invariant, stated precisely:

* A signal computed on bar ``t`` may read only bars ``<= t``.
* The order it raises fills at the **open of bar ``t+1``**, never at the close
  of bar ``t``.

The first invariant is proven here two ways: a property-based check over random
bar streams that the data handler never reveals a future bar, and an
end-to-end run of the real engine over the sample data with a spy strategy that
fails if it is ever shown a bar dated after the current one. The second
invariant (fill pricing) is owned by the execution handler and is proven once
that lands.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from backtester.config import BacktestConfig, CostConfig
from backtester.data import HistoricCSVDataHandler
from backtester.engine import BacktestEngine
from backtester.events import (
    FillEvent,
    MarketEvent,
    OrderEvent,
    SignalDirection,
    SignalEvent,
)
from backtester.execution import ExecutionHandler, SimulatedExecutionHandler
from backtester.portfolio import Portfolio, RiskBasedPortfolio
from backtester.strategy import Strategy

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "BTCUSD_1h_sample.csv"
_START = datetime(2021, 1, 1, tzinfo=UTC)


@st.composite
def _bar_series(draw: st.DrawFn) -> list[MarketEvent]:
    """Generate a chronological BTC/USD bar series of 1-40 flat bars."""
    price = st.floats(min_value=1_000.0, max_value=100_000.0, allow_nan=False, allow_infinity=False)
    prices = draw(st.lists(price, min_size=1, max_size=40))
    return [
        MarketEvent(_START + timedelta(hours=i), "BTC/USD", p, p, p, p, 1.0)
        for i, p in enumerate(prices)
    ]


@given(bars=_bar_series())
def test_get_latest_bars_never_leaks_future(bars: list[MarketEvent]) -> None:
    handler = HistoricCSVDataHandler.from_bars(bars, "BTC/USD")
    streamed = 0
    while True:
        event = handler.update_bars()
        if event is None:
            break
        streamed += 1
        window = handler.get_latest_bars("BTC/USD", n=len(bars))
        # Exactly the bars seen so far, in order — never a later one.
        assert len(window) == streamed
        assert window[-1] is event
        assert all(bar.timestamp <= event.timestamp for bar in window)
        assert [id(bar) for bar in window] == [id(bar) for bar in bars[:streamed]]
    assert streamed == len(bars)


class _NoopPortfolio(Portfolio):
    """Does nothing but satisfy the interface for a signal-free run."""

    def on_market(self, event: MarketEvent) -> None:
        return None

    def on_signal(self, event: SignalEvent) -> OrderEvent | None:
        return None

    def on_fill(self, event: FillEvent) -> None:
        return None

    def equity_curve(self) -> pd.DataFrame:
        return pd.DataFrame({"equity": []})


class _UnusedExecution(ExecutionHandler):
    """The spy strategy emits no orders, so nothing is ever submitted."""

    def submit_order(self, order: OrderEvent) -> None:
        raise AssertionError("no orders expected from the spy strategy")

    def on_market(self, event: MarketEvent) -> list[FillEvent]:
        return []


class _VisibilitySpyStrategy(Strategy):
    """Records any bar for which the visible window extends into the future."""

    def __init__(self, data: HistoricCSVDataHandler, symbol: str) -> None:
        self._data = data
        self._symbol = symbol
        self.bars_checked = 0
        self.violations: list[datetime] = []

    def calculate_signals(self, event: MarketEvent) -> list[SignalEvent]:
        self.bars_checked += 1
        window = self._data.get_latest_bars(self._symbol, n=10_000)
        if window and max(bar.timestamp for bar in window) > event.timestamp:
            self.violations.append(event.timestamp)
        return []


def test_engine_strategy_never_sees_a_future_bar() -> None:
    handler = HistoricCSVDataHandler(SAMPLE, "BTC/USD")
    spy = _VisibilitySpyStrategy(handler, "BTC/USD")
    engine = BacktestEngine(
        data=handler,
        strategy=spy,
        portfolio=_NoopPortfolio(),
        execution=_UnusedExecution(),
        config=BacktestConfig(data_path=SAMPLE, symbol="BTC/USD"),
    )

    engine.run()

    assert spy.bars_checked == 720
    assert spy.violations == []


class _FireOnceStrategy(Strategy):
    """Emits a single LONG on a chosen bar index, to pin down fill timing."""

    def __init__(self, fire_index: int, symbol: str) -> None:
        self._fire_index = fire_index
        self._symbol = symbol
        self._i = -1

    def calculate_signals(self, event: MarketEvent) -> list[SignalEvent]:
        self._i += 1
        if self._i == self._fire_index:
            return [SignalEvent(event.timestamp, self._symbol, SignalDirection.LONG)]
        return []


class _RecordingExecution(SimulatedExecutionHandler):
    """Simulated executor that also records every fill it produces."""

    def __init__(self, costs: CostConfig) -> None:
        super().__init__(costs)
        self.fills: list[FillEvent] = []

    def on_market(self, event: MarketEvent) -> list[FillEvent]:
        produced = super().on_market(event)
        self.fills.extend(produced)
        return produced


def test_fill_prices_at_next_bar_open() -> None:
    opens = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0]
    closes = [105.0, 115.0, 125.0, 135.0, 145.0, 155.0]
    bars = [
        MarketEvent(
            _START + timedelta(hours=i),
            "BTC/USD",
            open=o,
            high=max(o, c) + 1.0,
            low=min(o, c) - 1.0,
            close=c,
            volume=1.0,
        )
        for i, (o, c) in enumerate(zip(opens, closes, strict=True))
    ]
    # Zero costs so the fill lands exactly on the open, isolating the timing.
    execution = _RecordingExecution(CostConfig(commission_bps=0.0, slippage_bps=0.0))
    config = BacktestConfig(data_path=SAMPLE, symbol="BTC/USD")
    engine = BacktestEngine(
        data=HistoricCSVDataHandler.from_bars(bars, "BTC/USD"),
        strategy=_FireOnceStrategy(fire_index=3, symbol="BTC/USD"),
        portfolio=RiskBasedPortfolio(config),
        execution=execution,
        config=config,
    )

    engine.run()

    # The signal is raised on bar 3; its order fills at bar 4's OPEN (140.0),
    # never bar 3's close (135.0). That is the execution-side no-lookahead proof.
    assert len(execution.fills) == 1
    fill = execution.fills[0]
    assert fill.timestamp == bars[4].timestamp
    assert fill.fill_price == pytest.approx(bars[4].open)
    assert fill.fill_price != bars[3].close
