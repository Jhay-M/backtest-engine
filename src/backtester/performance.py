"""Performance analytics and tear sheet.

Metrics are computed here directly from the equity curve with numpy rather than
imported from a stats package — deriving Sharpe, Sortino, and drawdown by hand
is precisely the competency this piece is meant to demonstrate.

The crypto market trades 24/7, so annualisation uses calendar time, not equity
trading days. ``periods_per_year`` defaults to hourly bars (``365 * 24``);
callers pass the value matching their bar size.

Conventions: a risk-free rate of zero is assumed; standard deviations use the
sample estimator (``ddof=1``); degenerate inputs (fewer than two returns, zero
dispersion, no downside) return ``0.0`` rather than ``nan``/``inf`` so summary
tables and plots stay clean.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

HOURS_PER_YEAR = 365 * 24


def _returns(equity: pd.Series) -> pd.Series:
    """Per-bar simple returns of an equity curve (first NaN dropped)."""
    return equity.astype(float).pct_change().dropna()


def sharpe_ratio(returns: pd.Series, periods_per_year: int = HOURS_PER_YEAR) -> float:
    """Annualised Sharpe ratio of a per-bar return series.

    Args:
        returns: Per-bar simple returns.
        periods_per_year: Number of bars in a calendar year (24/7 market).

    Returns:
        The annualised Sharpe ratio, or ``0.0`` if undefined.
    """
    values = returns.to_numpy(dtype=float)
    if values.size < 2:
        return 0.0
    std = values.std(ddof=1)
    if std == 0.0:
        return 0.0
    return float(values.mean() / std * np.sqrt(periods_per_year))


def sortino_ratio(returns: pd.Series, periods_per_year: int = HOURS_PER_YEAR) -> float:
    """Annualised Sortino ratio (downside-deviation-adjusted).

    Uses the target semideviation with a zero target: the RMS of the negative
    part of returns over *all* periods.

    Args:
        returns: Per-bar simple returns.
        periods_per_year: Number of bars in a calendar year.

    Returns:
        The annualised Sortino ratio, or ``0.0`` if undefined.
    """
    values = returns.to_numpy(dtype=float)
    if values.size < 2:
        return 0.0
    downside = np.minimum(values, 0.0)
    downside_dev = float(np.sqrt(np.mean(downside**2)))
    if downside_dev == 0.0:
        return 0.0
    return float(values.mean() / downside_dev * np.sqrt(periods_per_year))


def max_drawdown(equity: pd.Series) -> float:
    """Maximum peak-to-trough drawdown of an equity curve.

    Args:
        equity: Equity level over time.

    Returns:
        The worst drawdown as a non-positive fraction (e.g. ``-0.25``).
    """
    values = equity.to_numpy(dtype=float)
    if values.size == 0:
        return 0.0
    running_max = np.maximum.accumulate(values)
    drawdowns = values / running_max - 1.0
    return float(drawdowns.min())


def cagr(equity: pd.Series, periods_per_year: int = HOURS_PER_YEAR) -> float:
    """Compound annual growth rate implied by an equity curve.

    Args:
        equity: Equity level over time.
        periods_per_year: Number of bars in a calendar year.

    Returns:
        The CAGR as a fraction; ``0.0`` if undefined, ``-1.0`` if wiped out.
    """
    values = equity.to_numpy(dtype=float)
    if values.size < 2:
        return 0.0
    start, end = float(values[0]), float(values[-1])
    years = (values.size - 1) / periods_per_year
    if start <= 0.0 or years <= 0.0:
        return 0.0
    ratio = end / start
    if ratio <= 0.0:
        return -1.0
    return float(ratio ** (1.0 / years) - 1.0)


def win_rate(returns: pd.Series) -> float:
    """Fraction of non-flat bars that were positive.

    Flat bars (zero return, typically while holding no position) are excluded
    so the figure reflects only bars where equity actually moved.

    Args:
        returns: Per-bar simple returns.

    Returns:
        Win rate in ``[0, 1]``, or ``0.0`` if there are no non-flat bars.
    """
    values = returns.to_numpy(dtype=float)
    nonzero = values[values != 0.0]
    if nonzero.size == 0:
        return 0.0
    return float((nonzero > 0.0).sum() / nonzero.size)


def exposure(position: pd.Series) -> float:
    """Fraction of bars spent holding a non-zero position.

    Args:
        position: Signed position size per bar.

    Returns:
        Exposure in ``[0, 1]``.
    """
    values = position.to_numpy(dtype=float)
    if values.size == 0:
        return 0.0
    return float((values != 0.0).sum() / values.size)


def summary(curve: pd.DataFrame, periods_per_year: int = HOURS_PER_YEAR) -> dict[str, float]:
    """Compute the full metric set from a portfolio equity curve.

    Args:
        curve: Equity curve with at least an ``equity`` column and, for
            exposure, a ``position`` column (as produced by the portfolio).
        periods_per_year: Number of bars in a calendar year.

    Returns:
        Mapping of metric name to value.
    """
    equity = curve["equity"].astype(float)
    returns = _returns(equity)
    if equity.empty:
        total_return = 0.0
    else:
        first = float(equity.iloc[0])
        total_return = float(equity.iloc[-1] / first - 1.0) if first != 0.0 else 0.0
    return {
        "total_return": total_return,
        "cagr": cagr(equity, periods_per_year),
        "sharpe": sharpe_ratio(returns, periods_per_year),
        "sortino": sortino_ratio(returns, periods_per_year),
        "max_drawdown": max_drawdown(equity),
        "win_rate": win_rate(returns),
        "exposure": exposure(curve["position"].astype(float)) if "position" in curve else 0.0,
    }


def tear_sheet(
    curve: pd.DataFrame,
    out_path: str | Path,
    periods_per_year: int = HOURS_PER_YEAR,
) -> None:
    """Render the equity curve, drawdown, and returns histogram to a PNG.

    Uses the Agg canvas directly (no pyplot), so it is safe to call headless.

    Args:
        curve: Portfolio equity curve (``equity`` and ``position`` columns).
        out_path: Destination image path.
        periods_per_year: Number of bars in a calendar year, for the stats.
    """
    equity = curve["equity"].astype(float)
    returns = _returns(equity)
    stats = summary(curve, periods_per_year)

    values = equity.to_numpy(dtype=float)
    drawdown = values / np.maximum.accumulate(values) - 1.0  # empty in, empty out

    fig = Figure(figsize=(10, 12))
    FigureCanvasAgg(fig)
    top, mid, bottom = fig.subplots(3, 1)

    top.plot(equity.index, values, color="C0")
    top.set_title("Equity curve")
    top.set_ylabel("Equity")

    mid.fill_between(equity.index, drawdown, 0.0, color="C3", alpha=0.4)
    mid.set_title("Drawdown")
    mid.set_ylabel("Drawdown")

    bottom.hist(returns.to_numpy(dtype=float), bins=50, color="C0", alpha=0.8)
    bottom.set_title("Per-bar returns")
    bottom.set_xlabel("Return")

    caption = "   ".join(f"{name}: {value:.4f}" for name, value in stats.items())
    fig.suptitle(caption, fontsize=9)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))
    fig.savefig(Path(out_path), dpi=120)
