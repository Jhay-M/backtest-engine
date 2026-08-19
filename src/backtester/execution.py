"""Execution interface and a simulated executor.

The execution handler is the seam that makes the engine reusable against a real
exchange: swap the simulated handler for one that routes orders over an API and
nothing upstream changes.

Fills are deferred to the **next** bar's open, never the signal bar's close —
the execution-side defence against lookahead. An order submitted while
processing bar ``t`` sits pending until bar ``t+1`` arrives, then fills at that
bar's open. Commission and slippage are applied on every fill; a costless fill
is not representable here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backtester.config import CostConfig
from backtester.events import FillEvent, MarketEvent, OrderEvent, OrderSide

_BPS = 10_000.0


class ExecutionHandler(ABC):
    """Abstract order executor.

    The engine drives it with two calls: :meth:`submit_order` to accept an
    order, and :meth:`on_market` once per bar to realise any fills at that bar.
    Splitting the two is what lets a backtest defer fills to the next bar's
    open, while a live handler could fill however its venue does.
    """

    @abstractmethod
    def submit_order(self, order: OrderEvent) -> None:
        """Accept an order for execution at the next bar's open."""

    @abstractmethod
    def on_market(self, event: MarketEvent) -> list[FillEvent]:
        """Realise fills for this bar and return them.

        Args:
            event: The newly arrived bar; its open prices any pending fills.

        Returns:
            The fills produced on this bar (empty if nothing was pending).
        """


class SimulatedExecutionHandler(ExecutionHandler):
    """Simulated executor: next-bar-open fills with commission and slippage.

    Orders are held until the following bar and filled at its open. Slippage
    moves the fill price adversely by ``slippage_bps`` (buys up, sells down);
    commission is ``commission_bps`` of the filled notional. Both come from
    :class:`~backtester.config.CostConfig`.
    """

    def __init__(self, costs: CostConfig) -> None:
        """Configure the cost model.

        Args:
            costs: Commission/slippage parameters, in basis points.
        """
        self._commission_bps = costs.commission_bps
        self._slippage_bps = costs.slippage_bps
        self._pending: list[OrderEvent] = []

    def submit_order(self, order: OrderEvent) -> None:
        """Queue ``order`` to fill at the next bar's open."""
        self._pending.append(order)

    def on_market(self, event: MarketEvent) -> list[FillEvent]:
        """Fill all orders pending for this symbol at ``event``'s open."""
        if not self._pending:
            return []
        fills = [
            self._fill(order, event) for order in self._pending if order.symbol == event.symbol
        ]
        self._pending = [order for order in self._pending if order.symbol != event.symbol]
        return fills

    def _fill(self, order: OrderEvent, bar: MarketEvent) -> FillEvent:
        """Price ``order`` at ``bar``'s open with slippage and commission."""
        slip = self._slippage_bps / _BPS
        if order.side is OrderSide.BUY:
            fill_price = bar.open * (1.0 + slip)
        else:
            fill_price = bar.open * (1.0 - slip)
        notional = order.quantity * fill_price
        commission = notional * (self._commission_bps / _BPS)
        slippage_cost = order.quantity * abs(fill_price - bar.open)
        return FillEvent(
            timestamp=bar.timestamp,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            commission=commission,
            slippage=slippage_cost,
        )
