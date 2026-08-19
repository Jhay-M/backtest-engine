"""Portfolio interface.

The portfolio is the risk brain: it turns intent (:class:`SignalEvent`) into a
sized order (:class:`OrderEvent`), updates cash and positions on
:class:`FillEvent`, and marks equity to market on every bar so the performance
layer has a clean equity curve to analyse.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

from backtester.config import BacktestConfig
from backtester.events import (
    FillEvent,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderType,
    SignalDirection,
    SignalEvent,
)


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


_EQUITY_COLUMNS = ["price", "cash", "position", "equity"]


class RiskBasedPortfolio(Portfolio):
    """Fixed-fractional risk portfolio with target-position sizing.

    **Sizing.** A new position is sized so that, if price moved against it by
    ``stop_loss_pct``, the loss would equal ``risk_fraction`` of current
    equity::

        quantity = risk_fraction * equity / (stop_loss_pct * price)

    That makes risk-at-stop equal to ``risk_fraction * equity`` — textbook
    fixed-fractional sizing. The stop distance only *sizes* the trade; v1 does
    not place protective stop orders (advanced order types are out of scope),
    so nothing here forces an exit at that level.

    **Targets, not increments.** A LONG/SHORT/EXIT signal sets the *desired*
    position (``+size`` / ``-size`` / ``0``); the emitted order is the
    difference from the current position. Buys are capped to available cash so
    the account never goes negative on a long.

    **Accounting.** Cash and position update on fills (commission deducted,
    slippage already baked into the fill price); equity is marked to market on
    every bar and appended to the curve.
    """

    _QTY_EPS = 1e-9
    _CASH_BUFFER = 0.999  # leave headroom for commission on a max-size buy

    def __init__(self, config: BacktestConfig) -> None:
        """Initialise from config: symbol, starting cash, and sizing knobs.

        Args:
            config: Validated run configuration.
        """
        self.symbol = config.symbol
        self.initial_cash = config.initial_cash
        self.cash = config.initial_cash
        self.position = 0.0
        self._risk_fraction = config.sizing.risk_fraction
        self._stop_loss_pct = config.sizing.stop_loss_pct
        self._last_price: float | None = None
        self._rows: list[dict[str, float | datetime]] = []

    def on_market(self, event: MarketEvent) -> None:
        """Update the mark price and append an equity snapshot for this bar."""
        if event.symbol != self.symbol:
            return
        self._last_price = event.close
        self._rows.append(
            {
                "timestamp": event.timestamp,
                "price": event.close,
                "cash": self.cash,
                "position": self.position,
                "equity": self._equity(event.close),
            }
        )

    def on_signal(self, event: SignalEvent) -> OrderEvent | None:
        """Turn a signal into a target-position order, or decline it."""
        if event.symbol != self.symbol or self._last_price is None:
            return None

        price = self._last_price
        equity = self._equity(price)
        if equity <= 0.0:
            return None

        size = (self._risk_fraction * equity) / (self._stop_loss_pct * price)
        target = self._target_position(event.direction, size)
        delta = target - self.position
        if abs(delta) < self._QTY_EPS:
            return None

        if delta > 0.0:
            quantity = self._cap_buy_to_cash(delta, price)
            if quantity < self._QTY_EPS:
                return None
            side = OrderSide.BUY
        else:
            quantity = -delta
            side = OrderSide.SELL

        return OrderEvent(event.timestamp, self.symbol, OrderType.MARKET, side, quantity)

    def on_fill(self, event: FillEvent) -> None:
        """Apply a fill to cash and position (commission deducted)."""
        if event.symbol != self.symbol:
            return
        notional = event.quantity * event.fill_price
        if event.side is OrderSide.BUY:
            self.position += event.quantity
            self.cash -= notional + event.commission
        else:
            self.position -= event.quantity
            self.cash += notional - event.commission

    def equity_curve(self) -> pd.DataFrame:
        """Return the per-bar equity curve as a timestamp-indexed frame."""
        if not self._rows:
            empty_index = pd.DatetimeIndex([], name="timestamp")
            return pd.DataFrame(columns=_EQUITY_COLUMNS, index=empty_index)
        frame = pd.DataFrame(self._rows).set_index("timestamp")
        return frame[_EQUITY_COLUMNS]

    def _equity(self, price: float) -> float:
        """Mark-to-market equity at ``price``."""
        return self.cash + self.position * price

    @staticmethod
    def _target_position(direction: SignalDirection, size: float) -> float:
        """Desired signed position for a signal direction."""
        if direction is SignalDirection.LONG:
            return size
        if direction is SignalDirection.SHORT:
            return -size
        return 0.0  # EXIT

    def _cap_buy_to_cash(self, quantity: float, price: float) -> float:
        """Clamp a buy quantity to what available cash can afford."""
        affordable = (self.cash * self._CASH_BUFFER) / price
        return min(quantity, max(0.0, affordable))
