# CLAUDE.md — Backtesting Engine (Python)

## Context
This project builds an event-driven crypto backtesting engine in Python (BTC/USD demo) — the first production portfolio piece for Joshua's pivot to professional trading-systems roles. It is a **public, hire-signal artifact**: two audiences read it — an engineer judging code quality and a quant checking backtest correctness. See `BACKTESTER_SPEC.md` for the full build spec. Joshua is an expert trading developer, strong in trading domain logic, building production Python depth.

## How to work here
- Write **production-grade, expert-level** Python. Full type hints, docstrings, clean modular design.
- Build **iteratively and test as you go** — implement a component, run its tests, iterate on real output. You can run everything here; use that.
- Surface **judgment calls** (sizing defaults, slippage model, metric choices) as choices, don't silently default.
- **Flag uncertainty explicitly** — assumptions or anything unverified. No false confidence.

## Correctness rules (non-negotiable — a quant will check these)
- **No lookahead bias:** signal at bar *t* uses only data ≤ *t*; orders fill at *t+1* open. There must be a test proving this (`test_no_lookahead.py`).
- **Costs always modeled:** commission (bps) + slippage on every fill.
- **Point-in-time DataHandler:** never expose future data.
- **Deterministic:** seed control; reproducible runs.
- **Crypto realism:** 24/7 market, fractional sizes; no equity market-hours assumptions.

## Architecture rules
- Event-driven only: `MarketEvent → SignalEvent → OrderEvent → FillEvent` through an event queue.
- DataHandler, Strategy, ExecutionHandler are **abstract interfaces with swappable implementations** — so a live feed, a real exchange executor, and an ML strategy can drop in later. Design for that; do NOT build those now.

## Engineering standards
- pytest for every component + the no-lookahead test.
- GitHub Actions CI: tests + `ruff` + `black` + `mypy`.
- `src/` layout, `pyproject.toml`, structured logging, config via dataclass/YAML.
- README with architecture diagram, quickstart, runnable BTC/USD example + sample tear sheet.
- Clean, meaningful commits — the git history is part of the portfolio.

## Scope discipline
- Build the LEAN v1 only (event loop, 4 components, analytics, 1–2 strategies, costs, metrics, tests, CI, docs). Do NOT build walk-forward, optimization, multi-asset, live adapter, or ML integration yet — interfaces should allow them; implementations come later.
