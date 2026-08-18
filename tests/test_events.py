"""Events are immutable, typed facts with correct discriminators."""

from __future__ import annotations

from datetime import datetime

import pytest

from backtester.events import (
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderType,
    SignalDirection,
    SignalEvent,
)

_TS = datetime(2021, 1, 1)


def test_event_type_discriminators() -> None:
    assert MarketEvent.type is EventType.MARKET
    assert SignalEvent.type is EventType.SIGNAL
    assert OrderEvent.type is EventType.ORDER
    assert FillEvent.type is EventType.FILL


def test_market_event_is_frozen() -> None:
    bar = MarketEvent(
        timestamp=_TS, symbol="BTC/USD", open=1.0, high=2.0, low=0.5, close=1.5, volume=10.0
    )
    with pytest.raises(AttributeError):
        bar.close = 999.0  # type: ignore[misc]


def test_signal_defaults_to_full_strength() -> None:
    sig = SignalEvent(timestamp=_TS, symbol="BTC/USD", direction=SignalDirection.LONG)
    assert sig.strength == 1.0


def test_fill_carries_costs() -> None:
    fill = FillEvent(
        timestamp=_TS,
        symbol="BTC/USD",
        side=OrderSide.BUY,
        quantity=0.25,
        fill_price=30_000.0,
        commission=7.5,
        slippage=1.5,
    )
    assert fill.commission > 0
    assert fill.slippage > 0


def test_order_is_market_only_in_v1() -> None:
    order = OrderEvent(
        timestamp=_TS,
        symbol="BTC/USD",
        order_type=OrderType.MARKET,
        side=OrderSide.SELL,
        quantity=0.1,
    )
    assert order.order_type is OrderType.MARKET
