"""Unit tests for the risk-based portfolio: sizing, accounting, equity curve."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backtester.config import BacktestConfig, SizingConfig
from backtester.events import (
    FillEvent,
    MarketEvent,
    OrderSide,
    OrderType,
    SignalDirection,
    SignalEvent,
)
from backtester.portfolio import RiskBasedPortfolio

_START = datetime(2021, 1, 1, tzinfo=UTC)
_UNUSED_PATH = Path("unused.csv")


def _config(
    cash: float = 100_000.0,
    risk_fraction: float = 0.02,
    stop_loss_pct: float = 0.10,
    symbol: str = "BTC/USD",
) -> BacktestConfig:
    return BacktestConfig(
        symbol=symbol,
        data_path=_UNUSED_PATH,
        initial_cash=cash,
        sizing=SizingConfig(risk_fraction=risk_fraction, stop_loss_pct=stop_loss_pct),
    )


def _market(i: int, close: float, symbol: str = "BTC/USD") -> MarketEvent:
    return MarketEvent(_START + timedelta(hours=i), symbol, close, close, close, close, 1.0)


def _signal(i: int, direction: SignalDirection, symbol: str = "BTC/USD") -> SignalEvent:
    return SignalEvent(_START + timedelta(hours=i), symbol, direction)


def test_long_signal_sizes_by_risk_formula() -> None:
    portfolio = RiskBasedPortfolio(_config())
    portfolio.on_market(_market(0, close=100.0))

    order = portfolio.on_signal(_signal(0, SignalDirection.LONG))

    # qty = risk_fraction * equity / (stop_loss_pct * price) = 0.02*100000/(0.10*100)
    assert order is not None
    assert order.side is OrderSide.BUY
    assert order.order_type is OrderType.MARKET
    assert order.quantity == 200.0
    # Risk-at-stop equals risk_fraction of equity: 200 units * (10% * 100) = 2000 = 2% of 100k.
    assert order.quantity * (0.10 * 100.0) == 0.02 * 100_000.0


def test_short_signal_targets_negative_position() -> None:
    portfolio = RiskBasedPortfolio(_config())
    portfolio.on_market(_market(0, close=100.0))

    order = portfolio.on_signal(_signal(0, SignalDirection.SHORT))

    assert order is not None
    assert order.side is OrderSide.SELL
    assert order.quantity == 200.0


def test_no_order_without_a_prior_market_event() -> None:
    portfolio = RiskBasedPortfolio(_config())
    assert portfolio.on_signal(_signal(0, SignalDirection.LONG)) is None


def test_exit_with_no_position_declines() -> None:
    portfolio = RiskBasedPortfolio(_config())
    portfolio.on_market(_market(0, close=100.0))
    assert portfolio.on_signal(_signal(0, SignalDirection.EXIT)) is None


def test_fill_updates_cash_and_position_with_commission() -> None:
    portfolio = RiskBasedPortfolio(_config())
    portfolio.on_market(_market(0, close=100.0))
    portfolio.on_signal(_signal(0, SignalDirection.LONG))  # would BUY 200

    # Simulate the executor filling at the next bar's open (101) with commission.
    fill = FillEvent(
        timestamp=_START + timedelta(hours=1),
        symbol="BTC/USD",
        side=OrderSide.BUY,
        quantity=200.0,
        fill_price=101.0,
        commission=20.2,
        slippage=0.0,
    )
    portfolio.on_fill(fill)

    assert portfolio.position == 200.0
    assert portfolio.cash == pytest.approx(79_779.8)  # 100000 - 200*101 - 20.2

    portfolio.on_market(_market(1, close=101.0))
    curve = portfolio.equity_curve()
    # Equity after the round trip = initial - commission (bought at the mark).
    assert curve["equity"].iloc[-1] == pytest.approx(99_979.8)  # 100000 - 20.2


def test_sell_fill_adds_cash() -> None:
    portfolio = RiskBasedPortfolio(_config())
    portfolio.position = 200.0
    portfolio.cash = 79_779.8

    fill = FillEvent(
        timestamp=_START + timedelta(hours=2),
        symbol="BTC/USD",
        side=OrderSide.SELL,
        quantity=200.0,
        fill_price=102.0,
        commission=20.4,
        slippage=0.0,
    )
    portfolio.on_fill(fill)

    assert portfolio.position == 0.0
    assert portfolio.cash == pytest.approx(100_159.4)  # 79779.8 + 200*102 - 20.4


def test_buy_is_capped_to_available_cash() -> None:
    # Tiny cash: the risk formula would want more than we can afford.
    portfolio = RiskBasedPortfolio(_config(cash=500.0, risk_fraction=1.0, stop_loss_pct=0.10))
    portfolio.on_market(_market(0, close=100.0))

    order = portfolio.on_signal(_signal(0, SignalDirection.LONG))

    assert order is not None
    # Unconstrained size would be 1.0*500/(0.10*100)=50 units (5000 notional),
    # but 500 cash only affords ~4.995 units.
    assert order.quantity < 50.0
    assert order.quantity * 100.0 <= 500.0


def test_equity_curve_has_one_row_per_bar() -> None:
    portfolio = RiskBasedPortfolio(_config())
    for i, close in enumerate([100.0, 101.0, 102.0, 103.0]):
        portfolio.on_market(_market(i, close=close))

    curve = portfolio.equity_curve()
    assert list(curve.columns) == ["price", "cash", "position", "equity"]
    assert len(curve) == 4
    assert curve.index.name == "timestamp"
    # Flat the whole time → equity stays at initial cash.
    assert (curve["equity"] == 100_000.0).all()


def test_no_order_when_equity_non_positive() -> None:
    portfolio = RiskBasedPortfolio(_config())
    portfolio.cash = 0.0  # wiped out
    portfolio.on_market(_market(0, close=100.0))
    assert portfolio.on_signal(_signal(0, SignalDirection.LONG)) is None


def test_on_fill_ignores_other_symbol() -> None:
    portfolio = RiskBasedPortfolio(_config())
    other = FillEvent(
        timestamp=_START,
        symbol="ETH/USD",
        side=OrderSide.BUY,
        quantity=1.0,
        fill_price=100.0,
        commission=1.0,
        slippage=0.0,
    )
    portfolio.on_fill(other)
    assert portfolio.position == 0.0
    assert portfolio.cash == 100_000.0


def test_ignores_other_symbols() -> None:
    portfolio = RiskBasedPortfolio(_config())
    portfolio.on_market(_market(0, close=100.0, symbol="ETH/USD"))
    # No BTC/USD price seen yet → cannot size.
    assert portfolio.on_signal(_signal(0, SignalDirection.LONG, symbol="ETH/USD")) is None
    assert portfolio.equity_curve().empty
