"""Generate a small, deterministic synthetic BTC/USD OHLCV sample.

The committed sample exists so the example backtest runs out-of-the-box with no
network access. It is **synthetic** — a seeded geometric-Brownian-motion price
path, not real market data (see ``data/README.md``). Real history can be
fetched later via the optional ``fetch`` extra (ccxt).

Run:
    python scripts/generate_sample_data.py
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_OUT = Path("data/BTCUSD_1h_sample.csv")


def generate(
    n: int = 720,
    start_price: float = 29_000.0,
    seed: int = 42,
    start: datetime | None = None,
) -> pd.DataFrame:
    """Build ``n`` hourly OHLCV bars from a seeded GBM close path.

    Open equals the prior close (continuous bars); high/low bracket the
    open/close with small positive noise so OHLC ordering is always valid.

    Args:
        n: Number of bars to generate.
        start_price: Price of the first bar's open.
        seed: RNG seed for reproducibility.
        start: Timestamp of the first bar (defaults to 2021-01-01 UTC).

    Returns:
        A DataFrame with ``timestamp,open,high,low,close,volume`` columns.
    """
    start = start or datetime(2021, 1, 1, tzinfo=UTC)
    rng = np.random.default_rng(seed)

    mu = 0.0002  # per-bar drift
    sigma = 0.01  # per-bar volatility
    shocks = rng.normal(0.0, 1.0, size=n)
    log_returns = (mu - 0.5 * sigma**2) + sigma * shocks
    closes = start_price * np.exp(np.cumsum(log_returns))

    opens = np.empty(n)
    opens[0] = start_price
    opens[1:] = closes[:-1]

    highs = np.maximum(opens, closes) * (1.0 + rng.uniform(0.0, 0.004, size=n))
    lows = np.minimum(opens, closes) * (1.0 - rng.uniform(0.0, 0.004, size=n))
    volumes = rng.uniform(10.0, 100.0, size=n)
    timestamps = [start + timedelta(hours=i) for i in range(n)]

    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )
    price_cols = ["open", "high", "low", "close"]
    frame[price_cols] = frame[price_cols].round(2)
    frame["volume"] = frame["volume"].round(4)
    return frame


def main() -> None:
    """CLI entry point: generate the sample and write it to CSV."""
    parser = argparse.ArgumentParser(description="Generate synthetic BTC/USD OHLCV sample data.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output CSV path.")
    parser.add_argument("--bars", type=int, default=720, help="Number of hourly bars.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed.")
    args = parser.parse_args()

    frame = generate(n=args.bars, seed=args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.out, index=False)
    print(f"wrote {len(frame)} bars to {args.out}")


if __name__ == "__main__":
    main()
