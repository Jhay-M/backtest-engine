"""Strategy interface.

A strategy consumes :class:`MarketEvent` bars and emits :class:`SignalEvent`
intents. It never sees cash, positions, or costs — that separation is what lets
an ML strategy drop in later behind the same interface without touching risk or
execution code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backtester.events import MarketEvent, SignalEvent


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
