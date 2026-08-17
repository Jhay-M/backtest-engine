# Backtesting Engine — Build Spec

## Purpose
The first production portfolio piece for the pivot to professional trading-systems roles. Public on GitHub, built to production standards. It is the **anchor**: an event-driven crypto backtesting engine in Python (BTC/USD demo), and the architectural foundation that later accepts a live data feed and an ML strategy.

Two audiences will read this repo: an **engineer** judging code quality and a **quant** checking backtest correctness. Design for both.

## Architecture — EVENT-DRIVEN (non-negotiable)
An event loop with a queue and four event types flowing through it:
`MarketEvent → SignalEvent → OrderEvent → FillEvent`

The same strategy code that runs here must be able to run live later — that property is the whole point of the design and the main credibility signal.

## Components (all behind clean interfaces / ABCs)
- **DataHandler** — abstract base + a concrete historical handler for BTC/USD OHLCV (CSV/parquet). Streams bar-by-bar and is **point-in-time correct**: only ever exposes data up to the current timestamp. Interface designed so a live feed can drop in later.
- **Strategy** — abstract base; consumes `MarketEvent`, emits `SignalEvent`. Ships with 1–2 examples (MA crossover; optionally a mean-reversion). Pluggable so an ML strategy fits later.
- **Portfolio** — tracks positions, cash, holdings, and the equity curve; does **risk-based position sizing**; converts `SignalEvent → OrderEvent`; updates state on `FillEvent`.
- **ExecutionHandler** — abstract base + a simulated executor; models **commission (bps) + slippage**; fills at the **next bar's open**, never the signal bar's close. Interface designed so a real exchange executor can drop in later.
- **Performance** — equity curve + real metrics: Sharpe, Sortino, max drawdown, CAGR, win rate, exposure. Produces a tear sheet (plot + summary stats).

## Correctness requirements (mandatory — quants check these first)
- **No lookahead bias:** a signal at bar *t* uses only data ≤ *t*; orders fill at *t+1* open. **Include a test that proves this.**
- **Costs always modeled:** commission + slippage on every fill. A costless backtest is a red flag.
- **Point-in-time data:** the DataHandler must not leak future data.
- **Deterministic/reproducible:** seed control; same inputs → same outputs.
- **Crypto realism:** 24/7 market (no equity market-hours assumptions); fractional position sizes.

## Production engineering standards
- Python 3.11+, full type hints, docstrings.
- Clean modular architecture (ABCs, dependency injection); no god-objects.
- **Tests (pytest)** for each component + the no-lookahead test; meaningful coverage.
- **CI (GitHub Actions):** run tests + `ruff`/`black`/`mypy`.
- Config-driven (dataclass or YAML); structured logging.
- Packaged: `pyproject.toml`, `src/` layout, installable.
- **README:** what/why, an architecture diagram, quickstart, a runnable example with a sample tear sheet, and short design notes on no-lookahead + cost modeling.
- Clean, meaningful git history — the commit log is itself a portfolio signal.

## Suggested repo layout
```
src/backtester/{events,data,strategy,portfolio,execution,performance}.py
tests/            # incl. test_no_lookahead.py
examples/         # runnable BTC/USD MA-crossover backtest
data/             # small committed BTC/USD sample
README.md  pyproject.toml  .github/workflows/ci.yml
```

## Scope
**IN (v1, lean):** event loop + 4 components + analytics; 1–2 example strategies; commission/slippage; core metrics + tear sheet; tests + CI + docs; committed BTC/USD sample data.
**OUT (later pieces / v2):** walk-forward analysis, parameter optimization, multi-asset portfolios, live-trading adapter, advanced order types, ML-strategy integration. The interfaces must *allow* these; do not *build* them now.

## The through-line (design intent)
Keep DataHandler, Strategy, and ExecutionHandler as clean swappable interfaces so the same engine later accepts (a) a live market-data feed → portfolio piece #2, (b) a real exchange executor → piece #3, (c) an ML strategy → the endgame. This is the foundation the eventual own-system runs on. **Design for it; don't build it yet.**

## Data
Use free historical BTC/USD OHLCV (an exchange API dump via CCXT, or a public dataset). Commit a small sample so the example runs out-of-the-box; document how to fetch more.

## Acceptance criteria
- Event-driven loop runs end-to-end on the BTC/USD demo.
- No-lookahead test passes.
- Costs + slippage applied on fills.
- Metrics + equity curve produced.
- CI green; lint + type-check clean.
- A stranger can clone, install, and run the example in minutes from the README.

## Build notes
- This is Python — Claude Code can **write, run, and test it end-to-end**. Build iteratively: implement a component, run its tests, iterate on real output. No manual compile loop.
