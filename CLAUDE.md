# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Tests (no Alpaca keys required)
pytest
pytest tests/test_foo.py::test_bar   # single test

# Connectivity smoke test (requires .env)
python scripts/smoke_test.py

# Download historical data (requires .env)
python scripts/download_data.py --symbols AAPL SPY --start 2020-01-01 --end 2024-12-31

# Backtest (requires downloaded data in ./data/)
python scripts/run_backtest.py --symbols SPY --start 2020-01-01 --end 2024-12-31 --strategy buy_and_hold
python scripts/run_backtest.py --symbols SPY --start 2020-01-01 --end 2024-12-31 --strategy ma_crossover
python scripts/run_backtest.py --symbols SPY --start 2020-01-01 --end 2024-12-31 --strategy rsi
python scripts/run_backtest.py --symbols SPY --start 2024-01-01 --end 2024-06-01 --strategy rsi --timeframe 1Min

# Paper trading (requires .env with Alpaca paper keys)
python scripts/run_paper.py --symbols AAPL SPY --qty 1
```

## Architecture

Sibyl is an algo trading platform for US stocks/ETFs (no options, no crypto). It has two runtime modes wired by different entry points:

- **Paper/live:** `scripts/run_paper.py` → `LiveDataProvider` + `OrderManager` (Alpaca WebSocket + REST)
- **Backtest:** `scripts/run_backtest.py` → `HistoricalDataProvider` + `SimulatedBroker` (local replay)

The shared core — `StrategyEngine`, `Strategy`, `PortfolioManager` — is identical in both modes.

### Data flow
```
DataProvider → StrategyEngine → [OrderManager | SimulatedBroker] → PortfolioManager
```

### Key modules

| Path | Purpose |
|------|---------|
| `config/settings.py` | Pydantic-settings; loads `.env` with `ALPACA_` prefix |
| `src/alpaca_client.py` | Thin factory: exposes `trading`, `stock_data`, `stock_stream`, `trade_stream`, `is_paper` |
| `src/data/provider.py` | `DataProvider` ABC (`get_bars`, `get_latest_quote`, `subscribe_bars`, `start`, `stop`) |
| `src/data/live_provider.py` | `LiveDataProvider` — Alpaca WebSocket + REST implementation |
| `src/data/historical_provider.py` | `HistoricalDataProvider` — parquet replay; `HistoricalBar` dataclass; `timeframe` param filters which file is loaded |
| `src/strategies/base.py` | `Strategy` ABC, `Signal` dataclass, `StrategyContext` dataclass |
| `src/strategies/buy_and_hold.py` | Buys each symbol on first bar (~95% of cash), holds |
| `src/strategies/ma_crossover.py` | 20/50-day MA crossover; pre-seeds price history in `initialize()` via `get_bars()` |
| `src/strategies/rsi.py` | RSI(14) mean reversion; buys RSI < 30, sells RSI > 70; works on any timeframe |
| `src/engine.py` | `StrategyEngine` — routes bars to strategies, collects signals |
| `src/orders/models.py` | `TrackedOrder` dataclass |
| `src/orders/manager.py` | `OrderManager` — Signal → Alpaca OrderRequest, tracks fills via TradingStream |
| `src/portfolio/models.py` | `Position`, `PortfolioSnapshot` dataclasses |
| `src/portfolio/manager.py` | `PortfolioManager` — live mode syncs with Alpaca; backtest mode is self-contained |
| `src/portfolio/reporter.py` | `PortfolioReporter` — print summary of snapshots (return, drawdown) |
| `src/backtest/simulated_broker.py` | Fills orders against historical prices (market @ next open, limit @ next high/low) |
| `src/backtest/runner.py` | Orchestrates full backtest loop; filters bars by `start`/`end` so warmup data doesn't generate trades |
| `src/backtest/metrics.py` | Sharpe, Sortino, drawdown, win rate, buy-and-hold comparison |

### Abstraction boundaries
- `AlpacaClient` is NOT a full SDK wrapper — don't add pass-through methods. The boundary is at `DataProvider` and `OrderManager`.
- Strategies receive a `StrategyContext` (portfolio, data, current_time) and return a `Signal` or `None`. They must not call Alpaca directly.
- `context.data.get_bars()` is available in `on_bar` but should only be called in `initialize()` for warmup. Calling it per-bar causes repeated disk reads.

### Data files
Historical data lives in `./data/` as `{SYMBOL}_{TIMEFRAME}.parquet` (e.g. `SPY_1Day.parquet`). Timeframe is the bar size, not the date range. Re-downloading the same symbol+timeframe overwrites the file. The `data/` directory is gitignored.

### Config
`AppSettings` nests `AlpacaSettings`. Paper vs live is a single flag (`ALPACA_PAPER=true/false`) with different keys — code paths are identical.

### Async
The codebase is async throughout (`asyncio`). Alpaca's streaming clients require it.
