"""Strategy interface.

A strategy consumes :class:`MarketEvent` bars and emits :class:`SignalEvent`
intents. It never sees cash, positions, or costs — that separation is what lets
an ML strategy drop in later behind the same interface without touching risk or
execution code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque

from backtester.events import MarketEvent, SignalDirection, SignalEvent


class Strategy(ABC):
    """Abstract signal generator.

    Implementations may keep internal rolling state (e.g. moving averages) but
    must derive signals only from bars at or before ``event`` — the handler
    contract guarantees no future bar is reachable, and strategies must not
    reach around it.
    """

    @abstractmethod
    def calculate_signals(self, event: MarketEvent) -> list[SignalEvent]:
        """React to a new bar and produce zero or more signals.

        Args:
            event: The bar that just closed.

        Returns:
            Signals to enqueue; an empty list means "no action this bar".
        """


class MovingAverageCrossStrategy(Strategy):
    """Dual simple-moving-average crossover.

    Emits a LONG when the short SMA crosses **above** the long SMA (a golden
    cross) and, on the reverse (a death cross), a SHORT when ``allow_short`` is
    set, otherwise an EXIT. Signals fire only on the crossover bar itself, not
    on every bar the relationship persists, so the portfolio is not handed a
    fresh order each bar.

    The strategy keeps its own rolling window of closes drawn from the event
    stream, so it is point-in-time correct by construction: it can only ever
    see bars it has already been given.
    """

    def __init__(
        self,
        symbol: str,
        short_window: int = 20,
        long_window: int = 50,
        *,
        allow_short: bool = True,
    ) -> None:
        """Configure the crossover windows.

        Args:
            symbol: Instrument to trade; events for other symbols are ignored.
            short_window: Length of the fast SMA (bars).
            long_window: Length of the slow SMA (bars); must exceed ``short_window``.
            allow_short: If true, a death cross emits SHORT; otherwise EXIT.

        Raises:
            ValueError: If windows are non-positive or ``short_window`` is not
                strictly less than ``long_window``.
        """
        if short_window <= 0 or long_window <= 0:
            raise ValueError("windows must be positive")
        if short_window >= long_window:
            raise ValueError("short_window must be strictly less than long_window")

        self.symbol = symbol
        self.short_window = short_window
        self.long_window = long_window
        self.allow_short = allow_short
        self._closes: deque[float] = deque(maxlen=long_window)
        self._short_above: bool | None = None

    def calculate_signals(self, event: MarketEvent) -> list[SignalEvent]:
        """Update the SMAs with ``event`` and emit a signal on a crossover."""
        if event.symbol != self.symbol:
            return []

        self._closes.append(event.close)
        if len(self._closes) < self.long_window:
            return []

        closes = list(self._closes)
        short_sma = sum(closes[-self.short_window :]) / self.short_window
        long_sma = sum(closes) / self.long_window
        short_above = short_sma > long_sma

        previous = self._short_above
        self._short_above = short_above
        # First computable bar establishes the baseline; a signal needs a flip.
        if previous is None or short_above == previous:
            return []

        if short_above:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.SHORT if self.allow_short else SignalDirection.EXIT
        return [SignalEvent(event.timestamp, self.symbol, direction)]
