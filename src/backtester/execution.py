"""Execution interface.

The execution handler is the seam that makes the engine reusable against a real
exchange: swap the simulated handler for one that routes orders over an API and
nothing upstream changes. The simulated implementation models commission and
slippage and fills at the **next bar's open**, never the signal bar's close.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backtester.events import FillEvent, OrderEvent


class ExecutionHandler(ABC):
    """Abstract order executor turning an order into a fill."""

    @abstractmethod
    def execute_order(self, event: OrderEvent) -> FillEvent:
        """Execute (or simulate) an order and return the resulting fill.

        Implementations must apply the configured commission and slippage and
        price the fill at the next bar's open to avoid lookahead.

        Args:
            event: The order to execute.

        Returns:
            The resulting :class:`FillEvent`.
        """
