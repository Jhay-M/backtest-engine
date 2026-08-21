"""Runnable BTC/USD moving-average-crossover backtest.

Runs the full event-driven engine on the committed sample data, prints the
performance summary, and writes a tear sheet PNG.

Run from the repo root::

    python examples/ma_crossover.py
    python examples/ma_crossover.py --short 10 --long 30 --out tearsheet.png
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from backtester.config import BacktestConfig
from backtester.data import HistoricCSVDataHandler
from backtester.engine import BacktestEngine
from backtester.execution import SimulatedExecutionHandler
from backtester.performance import summary, tear_sheet
from backtester.portfolio import RiskBasedPortfolio
from backtester.strategy import MovingAverageCrossStrategy

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = REPO_ROOT / "data" / "BTCUSD_1h_sample.csv"


def main() -> None:
    """Parse args, run the backtest, print the summary, and write a tear sheet."""
    parser = argparse.ArgumentParser(description="BTC/USD MA-crossover backtest demo.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="OHLCV CSV path.")
    parser.add_argument("--symbol", default="BTC/USD", help="Instrument symbol.")
    parser.add_argument("--short", type=int, default=10, help="Fast SMA window (bars).")
    parser.add_argument("--long", type=int, default=30, help="Slow SMA window (bars).")
    parser.add_argument("--out", type=Path, default=Path("tearsheet.png"), help="Tear sheet PNG.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    config = BacktestConfig(data_path=args.data, symbol=args.symbol)
    strategy = MovingAverageCrossStrategy(
        config.symbol, short_window=args.short, long_window=args.long
    )
    engine = BacktestEngine(
        data=HistoricCSVDataHandler(config.data_path, config.symbol),
        strategy=strategy,
        portfolio=RiskBasedPortfolio(config),
        execution=SimulatedExecutionHandler(config.costs),
        config=config,
    )

    curve = engine.run()
    stats = summary(curve)

    print("\nBacktest summary")
    print("-" * 32)
    for name, value in stats.items():
        print(f"{name:>14}: {value:+.4f}")

    tear_sheet(curve, args.out)
    print(f"\nWrote tear sheet to {args.out}")


if __name__ == "__main__":
    main()
