"""Event-driven crypto backtesting engine.

Public API surface. Import the interfaces from here; concrete
implementations live in their respective modules and are wired together by
:class:`~backtester.engine.BacktestEngine`.
"""

from __future__ import annotations

from backtester.config import BacktestConfig, CostConfig
from backtester.data import DataHandler, HistoricCSVDataHandler
from backtester.engine import BacktestEngine
from backtester.events import (
    Event,
    EventType,
    FillEvent,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderType,
    SignalDirection,
    SignalEvent,
)
from backtester.execution import ExecutionHandler
from backtester.portfolio import Portfolio
from backtester.strategy import MovingAverageCrossStrategy, Strategy

__version__ = "0.1.0"

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "CostConfig",
    "DataHandler",
    "Event",
    "EventType",
    "ExecutionHandler",
    "FillEvent",
    "HistoricCSVDataHandler",
    "MarketEvent",
    "MovingAverageCrossStrategy",
    "OrderEvent",
    "OrderSide",
    "OrderType",
    "Portfolio",
    "SignalDirection",
    "SignalEvent",
    "Strategy",
    "__version__",
]
