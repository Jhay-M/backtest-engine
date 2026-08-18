"""Portfolio interface.

The portfolio is the risk brain: it turns intent (:class:`SignalEvent`) into a
sized order (:class:`OrderEvent`), updates cash and positions on
:class:`FillEvent`, and marks equity to market on every bar so the performance
layer has a clean equity curve to analyse.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from backtester.events import FillEvent, MarketEvent, OrderEvent, SignalEvent


class Portfolio(ABC):
    """Abstract position/cash tracker and position sizer.

    Concrete portfolios own the sizing policy (the spec calls for risk-based
    sizing) and the equity accounting. Sizing defaults are a judgment call and
    should be surfaced in config, not hard-coded silently.
    """

    @abstractmethod
    def on_market(self, event: MarketEvent) -> None:
        """Mark open positions to market and append to the equity curve.

        Args:
            event: The latest bar, used for mark-to-market pricing.
        """

    @abstractmethod
    def on_signal(self, event: SignalEvent) -> OrderEvent | None:
        """Size a signal into an order, or decline it.

        Args:
            event: The strategy's intent.

        Returns:
            A sized :class:`OrderEvent`, or ``None`` if no trade is warranted
            (e.g. an EXIT with no open position, or insufficient cash).
        """

    @abstractmethod
    def on_fill(self, event: FillEvent) -> None:
        """Update cash, holdings, and positions from an executed fill.

        Args:
            event: The fill to apply, inclusive of commission and slippage.
        """

    @abstractmethod
    def equity_curve(self) -> pd.DataFrame:
        """Return the equity curve accumulated over the run.

        Returns:
            A time-indexed frame with at least an ``equity`` column, suitable
            for the performance/tear-sheet layer.
        """
