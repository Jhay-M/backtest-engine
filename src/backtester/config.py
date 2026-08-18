"""Run configuration, validated with pydantic.

Config is a validated pydantic model rather than a bare dataclass so that bad
inputs (negative cash, a risk fraction above 1) fail loudly at load time with a
clear message, and so a YAML file can be loaded and checked in one step.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class CostConfig(BaseModel):
    """Transaction-cost model parameters. Costs are applied on every fill."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    commission_bps: float = Field(
        default=10.0, ge=0.0, description="Commission per fill in basis points of notional."
    )
    slippage_bps: float = Field(
        default=5.0, ge=0.0, description="Slippage per fill in basis points of the fill price."
    )


class BacktestConfig(BaseModel):
    """Top-level backtest configuration.

    Attributes:
        symbol: Instrument to trade, e.g. ``"BTC/USD"``.
        data_path: Path to the OHLCV CSV/parquet file.
        initial_cash: Starting cash in quote currency.
        risk_fraction: Fraction of equity risked per position (risk-based sizing).
        seed: RNG seed for reproducible runs.
        costs: Commission/slippage model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = "BTC/USD"
    data_path: Path
    initial_cash: float = Field(default=100_000.0, gt=0.0)
    risk_fraction: float = Field(default=0.02, gt=0.0, le=1.0)
    seed: int = 42
    costs: CostConfig = Field(default_factory=CostConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> BacktestConfig:
        """Load and validate a :class:`BacktestConfig` from a YAML file.

        Args:
            path: Path to a YAML document with the config fields at top level.

        Returns:
            A validated configuration instance.
        """
        raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(raw)
