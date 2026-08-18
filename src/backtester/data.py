"""Market-data handling interface.

The :class:`DataHandler` is the seam that makes the engine reusable live: the
same strategy code runs against a historical handler here and, later, against a
live exchange feed that implements this identical interface. The contract is
therefore deliberately minimal and **point-in-time correct** — it must never
reveal a bar the simulation clock has not yet reached.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

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


_REQUIRED_COLUMNS: tuple[str, ...] = ("timestamp", "open", "high", "low", "close", "volume")


class HistoricCSVDataHandler(DataHandler):
    """Point-in-time data handler backed by a single-symbol OHLCV CSV.

    Bars are loaded once, sorted by timestamp, then streamed one at a time.
    Only bars that have already been streamed are ever visible through
    :meth:`get_latest_bars`, so future data is *structurally* unreachable —
    there is no code path that returns a bar past the current cursor. That is
    the no-lookahead guarantee ``tests/test_no_lookahead.py`` exercises.
    """

    def __init__(self, csv_path: str | Path, symbol: str) -> None:
        """Load and validate an OHLCV CSV for ``symbol``.

        Args:
            csv_path: Path to a CSV with columns
                ``timestamp,open,high,low,close,volume``.
            symbol: The instrument these bars represent.

        Raises:
            ValueError: If required columns are missing or timestamps duplicate.
        """
        self.symbol = symbol
        self._reset(self._load_csv(Path(csv_path), symbol))

    @classmethod
    def from_bars(cls, bars: Sequence[MarketEvent], symbol: str) -> HistoricCSVDataHandler:
        """Build a handler from in-memory bars, bypassing CSV loading.

        Feeds pre-materialised data through the identical point-in-time
        contract; used by tests and by callers that already hold bars.

        Args:
            bars: Bars in chronological order.
            symbol: The instrument the bars represent.

        Returns:
            A ready-to-stream handler.
        """
        obj: HistoricCSVDataHandler = cls.__new__(cls)
        obj.symbol = symbol
        obj._reset(list(bars))
        return obj

    def _reset(self, bars: list[MarketEvent]) -> None:
        """Initialise streaming state from an ordered list of bars."""
        self._bars = bars
        self._seen: list[MarketEvent] = []
        self._i = -1

    @staticmethod
    def _load_csv(path: Path, symbol: str) -> list[MarketEvent]:
        """Read, validate, and sort an OHLCV CSV into MarketEvents."""
        frame = pd.read_csv(path)
        missing = [c for c in _REQUIRED_COLUMNS if c not in frame.columns]
        if missing:
            raise ValueError(f"{path}: missing required columns {missing}")

        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame = frame.sort_values("timestamp", kind="stable").reset_index(drop=True)
        if bool(frame["timestamp"].duplicated().any()):
            raise ValueError(f"{path}: contains duplicate timestamps")

        records = frame[list(_REQUIRED_COLUMNS)].to_dict("records")
        return [
            MarketEvent(
                timestamp=pd.Timestamp(row["timestamp"]).to_pydatetime(),
                symbol=symbol,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            for row in records
        ]

    def update_bars(self) -> MarketEvent | None:
        """Advance one bar and expose it; return ``None`` once exhausted."""
        self._i += 1
        if self._i >= len(self._bars):
            return None
        bar = self._bars[self._i]
        self._seen.append(bar)
        return bar

    def get_latest_bars(self, symbol: str, n: int = 1) -> list[MarketEvent]:
        """Return up to ``n`` already-streamed bars for ``symbol``.

        Args:
            symbol: Instrument to fetch; a mismatch yields an empty list.
            n: Maximum number of trailing bars to return.

        Returns:
            Up to ``n`` bars in chronological order, none dated after the
            current cursor.
        """
        if symbol != self.symbol or n <= 0:
            return []
        return self._seen[-n:]

    @property
    def continue_backtest(self) -> bool:
        """Whether at least one more bar remains to be streamed."""
        return self._i < len(self._bars) - 1
