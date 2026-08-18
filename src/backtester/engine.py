"""The event loop that ties the four components together.

The loop is single-threaded and queue-driven. A ``collections.deque`` is used
rather than ``queue.Queue`` because there is no cross-thread contention to
guard against — the lock overhead of a synchronised queue would buy nothing.

Dispatch is by ``isinstance`` so the type checker narrows the event union and
each branch sees a concrete event type.
"""

from __future__ import annotations

import logging
import random
from collections import deque

import numpy as np
import pandas as pd

from backtester.config import BacktestConfig
from backtester.data import DataHandler
from backtester.events import Event, FillEvent, MarketEvent, OrderEvent, SignalEvent
from backtester.execution import ExecutionHandler
from backtester.portfolio import Portfolio
from backtester.strategy import Strategy

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Drives ``MarketEvent -> SignalEvent -> OrderEvent -> FillEvent``.

    The engine owns only the loop and the queue; all behaviour lives in the
    injected components, which are addressed purely through their abstract
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
        self._queue: deque[Event] = deque()
        self._seed(config.seed)

    @staticmethod
    def _seed(seed: int) -> None:
        """Seed stdlib and numpy RNGs so identical inputs give identical runs."""
        random.seed(seed)
        np.random.seed(seed)

    def run(self) -> pd.DataFrame:
        """Run the backtest to exhaustion and return the equity curve.

        The outer loop pulls one new bar at a time; the inner loop drains every
        event that bar cascades into before the clock advances. This ordering
        is what enforces "signal at ``t``, fill at ``t+1``": a fill can never be
        priced on the bar that produced its signal.

        Returns:
            The portfolio's equity curve as a time-indexed frame.
        """
        while self.data.continue_backtest:
            market = self.data.update_bars()
            if market is None:
                break
            self._queue.append(market)
            self._drain()
        return self.portfolio.equity_curve()

    def _drain(self) -> None:
        """Process the queue until it is empty."""
        while self._queue:
            event = self._queue.popleft()
            if isinstance(event, MarketEvent):
                self.portfolio.on_market(event)
                self._queue.extend(self.strategy.calculate_signals(event))
            elif isinstance(event, SignalEvent):
                order = self.portfolio.on_signal(event)
                if order is not None:
                    self._queue.append(order)
            elif isinstance(event, OrderEvent):
                self._queue.append(self.execution.execute_order(event))
            elif isinstance(event, FillEvent):
                self.portfolio.on_fill(event)
