"""The event loop that ties the four components together.

The loop is single-threaded. Per bar the order of operations is fixed, and that
ordering is the crux of the no-lookahead guarantee:

    1. fill orders pending from the previous bar, at THIS bar's open;
    2. mark the portfolio to market (so equity reflects those fills);
    3. let the strategy react to this bar and size any signals into orders,
       which are submitted for execution at the NEXT bar's open.

A ``collections.deque`` carries the intra-bar signal -> order cascade; a richer
system may grow deeper cascades (child orders, fill-driven signals) without the
loop changing.
"""

from __future__ import annotations

import logging
import random
from collections import deque

import numpy as np
import pandas as pd

from backtester.config import BacktestConfig
from backtester.data import DataHandler
from backtester.events import MarketEvent, OrderEvent, SignalEvent
from backtester.execution import ExecutionHandler
from backtester.portfolio import Portfolio
from backtester.strategy import Strategy

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Drives ``MarketEvent -> SignalEvent -> OrderEvent -> FillEvent``.

    The engine owns only the loop and the intra-bar queue; all behaviour lives
    in the injected components, addressed purely through their abstract
    interfaces. That dependency injection is what lets a live feed, a real
    executor, or an ML strategy replace a piece without the loop changing.
    """

    def __init__(
        self,
        *,
        data: DataHandler,
        strategy: Strategy,
        portfolio: Portfolio,
        execution: ExecutionHandler,
        config: BacktestConfig,
    ) -> None:
        """Wire the components together and seed the RNGs for reproducibility.

        Args:
            data: Point-in-time market-data source.
            strategy: Signal generator.
            portfolio: Position sizer and equity tracker.
            execution: Order executor.
            config: Validated run configuration.
        """
        self.data = data
        self.strategy = strategy
        self.portfolio = portfolio
        self.execution = execution
        self.config = config
        self._queue: deque[SignalEvent | OrderEvent] = deque()
        self._seed(config.seed)

    @staticmethod
    def _seed(seed: int) -> None:
        """Seed stdlib and numpy RNGs so identical inputs give identical runs."""
        random.seed(seed)
        np.random.seed(seed)

    def run(self) -> pd.DataFrame:
        """Run the backtest to exhaustion and return the equity curve.

        Orders still pending after the final bar never fill — there is no next
        bar to price them at, and peeking past the data would be lookahead.

        Returns:
            The portfolio's equity curve as a time-indexed frame.
        """
        logger.info("backtest start: symbol=%s seed=%d", self.config.symbol, self.config.seed)
        bars = 0
        while self.data.continue_backtest:
            bar = self.data.update_bars()
            if bar is None:
                break
            self._process_bar(bar)
            bars += 1
        logger.info("backtest complete: %d bars processed", bars)
        return self.portfolio.equity_curve()

    def _process_bar(self, bar: MarketEvent) -> None:
        """Run the fixed fill -> mark -> signal sequence for one bar."""
        # 1. Fill orders pending from the previous bar at THIS bar's open, and
        #    apply them before marking so equity reflects the new position.
        for fill in self.execution.on_market(bar):
            self.portfolio.on_fill(fill)
        # 2. Mark to market for this bar.
        self.portfolio.on_market(bar)
        # 3. Strategy reacts; size signals into orders and submit them for
        #    execution at the NEXT bar's open.
        self._queue.extend(self.strategy.calculate_signals(bar))
        while self._queue:
            event = self._queue.popleft()
            if isinstance(event, SignalEvent):
                order = self.portfolio.on_signal(event)
                if order is not None:
                    self._queue.append(order)
            elif isinstance(event, OrderEvent):
                self.execution.submit_order(event)
