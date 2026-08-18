"""Performance analytics and tear sheet.

Metrics are computed here directly from the equity curve with numpy rather than
imported from a stats package — deriving Sharpe, Sortino, and drawdown by hand
is precisely the competency this piece is meant to demonstrate.

The crypto market trades 24/7, so annualisation uses calendar time, not equity
trading days. ``periods_per_year`` defaults to hourly bars (``365 * 24``);
callers pass the value matching their bar size.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

HOURS_PER_YEAR = 365 * 24


def sharpe_ratio(returns: pd.Series, periods_per_year: int = HOURS_PER_YEAR) -> float:
    """Annualised Sharpe ratio of a per-bar return series.

    Args:
        returns: Per-bar simple returns.
        periods_per_year: Number of bars in a calendar year (24/7 market).

    Returns:
        The annualised Sharpe ratio.
    """
    raise NotImplementedError


def sortino_ratio(returns: pd.Series, periods_per_year: int = HOURS_PER_YEAR) -> float:
    """Annualised Sortino ratio (downside-deviation-adjusted).

    Args:
        returns: Per-bar simple returns.
        periods_per_year: Number of bars in a calendar year.

    Returns:
        The annualised Sortino ratio.
    """
    raise NotImplementedError


def max_drawdown(equity: pd.Series) -> float:
    """Maximum peak-to-trough drawdown of an equity curve.

    Args:
        equity: Equity level over time.

    Returns:
        The worst drawdown as a negative fraction (e.g. ``-0.25`` for -25%).
    """
    raise NotImplementedError


def cagr(equity: pd.Series, periods_per_year: int = HOURS_PER_YEAR) -> float:
    """Compound annual growth rate implied by an equity curve.

    Args:
        equity: Equity level over time.
        periods_per_year: Number of bars in a calendar year.

    Returns:
        The CAGR as a fraction.
    """
    raise NotImplementedError


def summary(equity: pd.Series, periods_per_year: int = HOURS_PER_YEAR) -> dict[str, float]:
    """Compute the full metric set for a tear-sheet summary table.

    Args:
        equity: Equity level over time.
        periods_per_year: Number of bars in a calendar year.

    Returns:
        Mapping of metric name to value (Sharpe, Sortino, max drawdown, CAGR,
        win rate, exposure, ...).
    """
    raise NotImplementedError


def tear_sheet(equity: pd.Series, out_path: str | Path) -> None:
    """Render the equity curve, drawdown, and summary stats to an image.

    Args:
        equity: Equity level over time.
        out_path: Destination image path (PNG).
    """
    raise NotImplementedError
