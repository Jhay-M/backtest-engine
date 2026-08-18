"""Market-data handling interface.

The :class:`DataHandler` is the seam that makes the engine reusable live: the
same strategy code runs against a historical handler here and, later, against a
live exchange feed that implements this identical interface. The contract is
therefore deliberately minimal and **point-in-time correct** — it must never
reveal a bar the simulation clock has not yet reached.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backtester.events import MarketEvent


class DataHandler(ABC):
    """Abstract, point-in-time-correct source of :class:`MarketEvent` bars.

    Implementations advance one bar per :meth:`update_bars` call and expose
    only already-seen bars through :meth:`get_latest_bars`. No method may
    return data dated after the most recent :meth:`update_bars` — that leak is
    exactly the lookahead bias the engine's tests guard against.
    """

    @abstractmethod
    def update_bars(self) -> MarketEvent | None:
        """Advance the clock by one bar.

        Returns:
            The :class:`MarketEvent` for the new bar, or ``None`` when the
            stream is exhausted.
        """

    @abstractmethod
    def get_latest_bars(self, symbol: str, n: int = 1) -> list[MarketEvent]:
        """Return up to ``n`` most-recent bars for ``symbol`` as of now.

        Args:
            symbol: Instrument to fetch history for.
            n: Maximum number of trailing bars to return.

        Returns:
            Up to ``n`` bars in chronological order, none dated after the
            current simulation timestamp.
        """

    @property
    @abstractmethod
    def continue_backtest(self) -> bool:
        """Whether more bars remain to be streamed."""
