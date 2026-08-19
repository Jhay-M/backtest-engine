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


class SizingConfig(BaseModel):
    """Risk-based position-sizing parameters.

    A position is sized so that an adverse move of ``stop_loss_pct`` would cost
    exactly ``risk_fraction`` of current equity (fixed-fractional risk). The
    stop distance only *sizes* the trade — v1 does not place protective stop
    orders (advanced order types are out of scope).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_fraction: float = Field(
        default=0.02, gt=0.0, le=1.0, description="Equity fraction risked per position."
    )
    stop_loss_pct: float = Field(
        default=0.10, gt=0.0, le=1.0, description="Assumed stop distance as a fraction of price."
    )


class BacktestConfig(BaseModel):
    """Top-level backtest configuration.

    Attributes:
        symbol: Instrument to trade, e.g. ``"BTC/USD"``.
        data_path: Path to the OHLCV CSV/parquet file.
        initial_cash: Starting cash in quote currency.
        seed: RNG seed for reproducible runs.
        sizing: Risk-based position-sizing model.
        costs: Commission/slippage model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = "BTC/USD"
    data_path: Path
    initial_cash: float = Field(default=100_000.0, gt=0.0)
    seed: int = 42
    sizing: SizingConfig = Field(default_factory=SizingConfig)
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
