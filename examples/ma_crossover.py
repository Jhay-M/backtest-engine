"""Runnable BTC/USD moving-average-crossover backtest (placeholder).

Wiring, once the concrete components land, will read:

    config = BacktestConfig.from_yaml("examples/ma_crossover.yaml")
    engine = BacktestEngine(
        data=HistoricCSVDataHandler(config.data_path, config.symbol),
        strategy=MovingAverageCrossStrategy(config.symbol, short_window=20, long_window=50),
        portfolio=RiskBasedPortfolio(config),
        execution=SimulatedExecutionHandler(config.costs, data),
        config=config,
    )
    equity = engine.run()
    tear_sheet(equity["equity"], "tearsheet.png")

The concrete implementations are intentionally not built yet (v1 scope).
"""

from __future__ import annotations


def main() -> None:
    """Entry point for the example once concrete components exist."""
    raise NotImplementedError("Concrete components are not implemented yet (scaffold).")


if __name__ == "__main__":
    main()
