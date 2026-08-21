"""Unit tests for the performance metrics and tear sheet."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from backtester.config import BacktestConfig
from backtester.data import HistoricCSVDataHandler
from backtester.engine import BacktestEngine
from backtester.execution import SimulatedExecutionHandler
from backtester.performance import (
    cagr,
    exposure,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    summary,
    tear_sheet,
    win_rate,
)
from backtester.portfolio import RiskBasedPortfolio
from backtester.strategy import MovingAverageCrossStrategy

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "BTCUSD_1h_sample.csv"
_START = datetime(2021, 1, 1, tzinfo=UTC)


def _equity(values: list[float]) -> pd.Series:
    index = pd.date_range(_START, periods=len(values), freq="h")
    return pd.Series(values, index=index, dtype=float)


def test_sharpe_matches_definition() -> None:
    returns = pd.Series([0.01, 0.02, 0.03])  # mean 0.02, sample std 0.01
    expected = (0.02 / 0.01) * math.sqrt(252)
    assert sharpe_ratio(returns, periods_per_year=252) == pytest.approx(expected)


def test_sharpe_zero_when_not_computable() -> None:
    assert sharpe_ratio(pd.Series([0.01]), periods_per_year=252) == 0.0  # < 2 points
    assert sharpe_ratio(pd.Series([0.01, 0.01, 0.01]), periods_per_year=252) == 0.0  # std 0


def test_sortino_matches_definition() -> None:
    returns = pd.Series([0.02, -0.01, 0.03, -0.02])
    downside_dev = math.sqrt((0.01**2 + 0.02**2) / 4)  # zeros for the up bars
    expected = (returns.mean() / downside_dev) * math.sqrt(252)
    assert sortino_ratio(returns, periods_per_year=252) == pytest.approx(expected)


def test_sortino_zero_without_downside() -> None:
    assert sortino_ratio(pd.Series([0.01, 0.02, 0.03]), periods_per_year=252) == 0.0


def test_max_drawdown() -> None:
    # Peak 120, trough 80 -> worst drawdown -1/3.
    assert max_drawdown(_equity([100, 120, 90, 110, 80])) == pytest.approx(-1 / 3)


def test_max_drawdown_empty_is_zero() -> None:
    assert max_drawdown(pd.Series([], dtype=float)) == 0.0


def test_cagr_doubling_in_one_year() -> None:
    # 252 intervals at 252 periods/year = 1 year; 100 -> 200 = +100%.
    equity = _equity([100.0] * 252 + [200.0])
    assert cagr(equity, periods_per_year=252) == pytest.approx(1.0)


def test_cagr_undefined_is_zero() -> None:
    assert cagr(_equity([100.0]), periods_per_year=252) == 0.0


def test_win_rate_excludes_flat_bars() -> None:
    # Non-flat bars: +, -, + -> 2 of 3.
    assert win_rate(pd.Series([0.01, -0.02, 0.0, 0.03])) == pytest.approx(2 / 3)


def test_exposure_fraction_of_held_bars() -> None:
    assert exposure(pd.Series([0.0, 1.0, 1.0, 0.0, 2.0])) == pytest.approx(0.6)


def test_summary_has_all_metrics_and_is_finite() -> None:
    curve = pd.DataFrame(
        {
            "equity": [100.0, 101.0, 99.0, 103.0],
            "position": [0.0, 1.0, 1.0, 0.0],
        },
        index=pd.date_range(_START, periods=4, freq="h"),
    )
    stats = summary(curve, periods_per_year=252)
    assert set(stats) == {
        "total_return",
        "cagr",
        "sharpe",
        "sortino",
        "max_drawdown",
        "win_rate",
        "exposure",
    }
    assert all(isinstance(v, float) and math.isfinite(v) for v in stats.values())
    assert stats["total_return"] == pytest.approx(0.03)
    assert stats["exposure"] == pytest.approx(0.5)


def test_tear_sheet_writes_a_png(tmp_path: Path) -> None:
    curve = pd.DataFrame(
        {
            "equity": [100.0, 101.0, 99.0, 103.0, 105.0],
            "position": [0.0, 1.0, 1.0, 0.0, 1.0],
        },
        index=pd.date_range(_START, periods=5, freq="h"),
    )
    out = tmp_path / "tearsheet.png"
    tear_sheet(curve, out, periods_per_year=252)
    assert out.exists()
    assert out.stat().st_size > 0


def test_summary_on_a_real_backtest_is_finite() -> None:
    config = BacktestConfig(data_path=SAMPLE, symbol="BTC/USD")
    engine = BacktestEngine(
        data=HistoricCSVDataHandler(SAMPLE, "BTC/USD"),
        strategy=MovingAverageCrossStrategy("BTC/USD", short_window=10, long_window=30),
        portfolio=RiskBasedPortfolio(config),
        execution=SimulatedExecutionHandler(config.costs),
        config=config,
    )
    curve = engine.run()
    stats = summary(curve)

    assert len(curve) == 720
    assert all(math.isfinite(v) for v in stats.values())
    # Exposure is a real fraction; the strategy is not always in the market.
    assert 0.0 <= stats["exposure"] <= 1.0
