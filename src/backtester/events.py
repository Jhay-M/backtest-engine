"""The four events that flow through the engine's queue.

``MarketEvent -> SignalEvent -> OrderEvent -> FillEvent``

Events are frozen dataclasses: once emitted, an event is an immutable fact.
This prevents a downstream component from mutating an event another component
still holds a reference to, and makes the event log trivially replayable.

Each event carries its :class:`EventType` as a ``ClassVar`` discriminator, but
dispatch in the engine is done with ``isinstance`` so the type checker can
narrow the union.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import ClassVar


class EventType(StrEnum):
    """Discriminator for the four event kinds."""

    MARKET = "MARKET"
    SIGNAL = "SIGNAL"
    ORDER = "ORDER"
    FILL = "FILL"


class SignalDirection(StrEnum):
    """Direction a strategy wants to take (or unwind) exposure in."""

    LONG = "LONG"
    SHORT = "SHORT"
    EXIT = "EXIT"


class OrderSide(StrEnum):
    """Side of a concrete order once the portfolio has sized it."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """Order type. v1 is market-only; LIMIT is reserved for a later piece."""

    MARKET = "MARKET"


@dataclass(frozen=True, slots=True)
class MarketEvent:
    """A new OHLCV bar became available for ``symbol`` at ``timestamp``.

    Attributes:
        timestamp: Close time of the bar (point-in-time "now").
        symbol: Instrument identifier, e.g. ``"BTC/USD"``.
        open: Bar open price.
        high: Bar high price.
        low: Bar low price.
        close: Bar close price.
        volume: Bar volume in base units.
    """

    type: ClassVar[EventType] = EventType.MARKET

    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class SignalEvent:
    """A strategy's view on ``symbol`` produced from a :class:`MarketEvent`.

    Carries no size or price — turning a signal into a sized, priced order is
    the portfolio's job, which keeps strategies free of risk-model concerns.

    Attributes:
        timestamp: Timestamp of the bar that produced the signal.
        symbol: Instrument the signal refers to.
        direction: LONG, SHORT, or EXIT.
        strength: Optional conviction in ``[0, 1]`` for sizing; defaults to 1.
    """

    type: ClassVar[EventType] = EventType.SIGNAL

    timestamp: datetime
    symbol: str
    direction: SignalDirection
    strength: float = 1.0


@dataclass(frozen=True, slots=True)
class OrderEvent:
    """A sized, priced-at-market instruction for the execution handler.

    Attributes:
        timestamp: Timestamp of the bar on which the order was raised.
        symbol: Instrument to trade.
        order_type: Order type (market-only in v1).
        side: BUY or SELL.
        quantity: Fractional base-asset quantity (crypto supports fractions).
    """

    type: ClassVar[EventType] = EventType.ORDER

    timestamp: datetime
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: float


@dataclass(frozen=True, slots=True)
class FillEvent:
    """The result of executing an :class:`OrderEvent`.

    Fills occur at the *next* bar's open (never the signal bar's close) and
    always carry costs — a costless fill is a modelling bug, not a feature.

    Attributes:
        timestamp: Timestamp of the bar the fill executed on (``t+1``).
        symbol: Instrument traded.
        side: BUY or SELL.
        quantity: Filled fractional quantity.
        fill_price: All-in price per unit including modelled slippage.
        commission: Commission charged for this fill, in quote currency.
        slippage: Slippage cost baked into ``fill_price``, in quote currency.
    """

    type: ClassVar[EventType] = EventType.FILL

    timestamp: datetime
    symbol: str
    side: OrderSide
    quantity: float
    fill_price: float
    commission: float
    slippage: float


#: Discriminated union of every event that can sit on the engine queue.
Event = MarketEvent | SignalEvent | OrderEvent | FillEvent
