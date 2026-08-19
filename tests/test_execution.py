"""Unit tests for the simulated execution handler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backtester.config import CostConfig
from backtester.events import MarketEvent, OrderEvent, OrderSide, OrderType
from backtester.execution import SimulatedExecutionHandler

_START = datetime(2021, 1, 1, tzinfo=UTC)


def _bar(i: int, open_: float, symbol: str = "BTC/USD") -> MarketEvent:
    return MarketEvent(_START + timedelta(hours=i), symbol, open_, open_, open_, open_, 1.0)


def _order(side: OrderSide, quantity: float = 10.0, symbol: str = "BTC/USD") -> OrderEvent:
    return OrderEvent(_START, symbol, OrderType.MARKET, side, quantity)


def test_no_fill_without_a_pending_order() -> None:
    handler = SimulatedExecutionHandler(CostConfig())
    assert handler.on_market(_bar(1, open_=100.0)) == []


def test_fill_prices_at_next_bar_open_with_no_costs() -> None:
    handler = SimulatedExecutionHandler(CostConfig(commission_bps=0.0, slippage_bps=0.0))
    handler.submit_order(_order(OrderSide.BUY, quantity=10.0))

    fills = handler.on_market(_bar(1, open_=100.0))

    assert len(fills) == 1
    fill = fills[0]
    assert fill.fill_price == pytest.approx(100.0)
    assert fill.commission == pytest.approx(0.0)
    assert fill.slippage == pytest.approx(0.0)
    assert fill.timestamp == _START + timedelta(hours=1)


def test_buy_slips_up_sell_slips_down() -> None:
    handler = SimulatedExecutionHandler(CostConfig(commission_bps=0.0, slippage_bps=50.0))  # 50 bps
    handler.submit_order(_order(OrderSide.BUY, quantity=1.0))
    handler.submit_order(_order(OrderSide.SELL, quantity=1.0))

    fills = handler.on_market(_bar(1, open_=100.0))

    buy = next(f for f in fills if f.side is OrderSide.BUY)
    sell = next(f for f in fills if f.side is OrderSide.SELL)
    assert buy.fill_price == pytest.approx(100.0 * 1.005)  # +0.5%
    assert sell.fill_price == pytest.approx(100.0 * 0.995)  # -0.5%
    assert buy.slippage == pytest.approx(0.5)
    assert sell.slippage == pytest.approx(0.5)


def test_commission_is_bps_of_filled_notional() -> None:
    handler = SimulatedExecutionHandler(CostConfig(commission_bps=10.0, slippage_bps=0.0))  # 10 bps
    handler.submit_order(_order(OrderSide.BUY, quantity=2.0))

    (fill,) = handler.on_market(_bar(1, open_=100.0))

    # notional = 2 * 100 = 200; commission = 200 * 10bps = 0.2
    assert fill.commission == pytest.approx(0.2)


def test_pending_orders_are_consumed_once() -> None:
    handler = SimulatedExecutionHandler(CostConfig())
    handler.submit_order(_order(OrderSide.BUY))

    first = handler.on_market(_bar(1, open_=100.0))
    second = handler.on_market(_bar(2, open_=110.0))

    assert len(first) == 1
    assert second == []  # nothing left pending


def test_orders_for_other_symbols_stay_pending() -> None:
    handler = SimulatedExecutionHandler(CostConfig())
    handler.submit_order(_order(OrderSide.BUY, symbol="ETH/USD"))

    # A BTC bar must not fill an ETH order.
    assert handler.on_market(_bar(1, open_=100.0, symbol="BTC/USD")) == []
    eth_fills = handler.on_market(_bar(2, open_=200.0, symbol="ETH/USD"))
    assert len(eth_fills) == 1
    assert eth_fills[0].symbol == "ETH/USD"
