# Sibyl

Modular algorithmic trading platform for US stocks and ETFs, built on [Alpaca's API](https://alpaca.markets). Supports paper trading, live trading, and historical backtesting with a shared strategy core across all modes.

## Tech stack

- **Python 3.10+** with `asyncio` throughout
- **[alpaca-py](https://github.com/alpacahq/alpaca-py)** — brokerage, market data, and streaming
- **pandas / pyarrow** — historical data storage and replay
- **pydantic-settings** — typed config from environment variables
- **uv** — package management

---

## Setup

### 1. Install dependencies

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 2. Configure API keys

Create a `.env` file in the project root with your Alpaca credentials:

```ini
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true          # true = paper trading, false = live
```

Paper trading keys are free at [alpaca.markets](https://alpaca.markets). Live trading requires a funded account with separate keys.

---

## Usage

### Smoke test (verify connectivity)

```bash
python scripts/smoke_test.py
```

### Download historical data

```bash
python scripts/download_data.py --symbols AAPL SPY --start 2020-01-01 --end 2024-12-31
```

Files are saved to `./data/` using the naming convention `{SYMBOL}_{TIMEFRAME}.parquet` — e.g. `SPY_1Day.parquet`. The timeframe refers to the **bar size** (each row = one day of OHLCV data), not the total date range. A `1Day` file downloaded over 5 years contains ~1260 rows, one per trading day. Re-downloading the same symbol and timeframe overwrites the existing file.

Available timeframes: `1Day` (default), `1Min`, `5Min`, etc.

For MA crossover, download extra history to cover the warmup window:

```bash
python scripts/download_data.py --symbols SPY --start 2019-07-01 --end 2024-12-31
```

### Backtest

```bash
python scripts/run_backtest.py --symbols SPY --start 2020-01-01 --end 2024-12-31 --strategy buy_and_hold
```

**Flags**

| Flag | Default | Description |
|------|---------|-------------|
| `--symbols` | required | One or more tickers |
| `--strategy` | `buy_and_hold` | Strategy to run (see below) |
| `--start` / `--end` | none | Backtest date window (YYYY-MM-DD) |
| `--timeframe` | `1Day` | Bar size — must match a downloaded parquet file |
| `--initial-cash` | `100000` | Starting capital |
| `--data-dir` | `./data` | Directory containing parquet files |

**Available strategies**

| Strategy | Description | Notes |
|----------|-------------|-------|
| `buy_and_hold` | Buys all symbols on the first bar, holds until end | Good baseline benchmark |
| `ma_crossover` | 20/50-day MA crossover — buys golden cross, sells death cross | Download ~100 days before `--start` for warmup |
| `rsi` | RSI(14) — buys when RSI < 30, sells when RSI > 70 | Works on any timeframe |

**Examples**

```bash
# Daily MA crossover (needs warmup data from 2019)
python scripts/run_backtest.py --symbols SPY --start 2020-01-01 --end 2024-12-31 --strategy ma_crossover

# RSI on daily bars
python scripts/run_backtest.py --symbols SPY --start 2020-01-01 --end 2024-12-31 --strategy rsi

# RSI on 1-minute bars (download first)
python scripts/download_data.py --symbols SPY --start 2024-01-01 --end 2024-06-01 --timeframe 1Min
python scripts/run_backtest.py --symbols SPY --start 2024-01-01 --end 2024-06-01 --strategy rsi --timeframe 1Min

# Multiple symbols, custom capital
python scripts/run_backtest.py --symbols AAPL SPY QQQ --start 2022-01-01 --end 2024-01-01 --initial-cash 50000
```

### Paper trading

```bash
python scripts/run_paper.py --symbols AAPL SPY --qty 1
```

Requires a valid `.env` with paper trading keys.

---

## Project structure

```
sibyl/
├── config/
│   └── settings.py              # Pydantic settings (loads .env)
├── scripts/
│   ├── download_data.py         # Fetch and save historical bars
│   ├── run_backtest.py          # Backtest entry point
│   ├── run_paper.py             # Paper/live trading entry point
│   └── smoke_test.py            # API connectivity check
├── src/
│   ├── alpaca_client.py         # Thin Alpaca client factory
│   ├── engine.py                # Routes bars to strategies, collects signals
│   ├── backtest/
│   │   ├── metrics.py           # Sharpe, Sortino, drawdown, win rate
│   │   ├── runner.py            # Orchestrates the backtest loop
│   │   └── simulated_broker.py  # Fills orders against historical prices
│   ├── data/
│   │   ├── provider.py          # DataProvider ABC
│   │   ├── historical_provider.py  # Parquet replay
│   │   └── live_provider.py     # Alpaca WebSocket + REST
│   ├── orders/
│   │   ├── manager.py           # Signal → Alpaca order, fill tracking
│   │   └── models.py            # TrackedOrder dataclass
│   ├── portfolio/
│   │   ├── manager.py           # Position and cash tracking
│   │   ├── models.py            # Position, PortfolioSnapshot dataclasses
│   │   └── reporter.py          # Print return/drawdown summary
│   └── strategies/
│       ├── base.py              # Strategy ABC, Signal, StrategyContext
│       ├── buy_and_hold.py      # Buy once, hold forever
│       ├── ma_crossover.py      # 20/50-day moving average crossover
│       └── rsi.py               # RSI(14) mean reversion
└── tests/
```

---

## Adding a strategy

1. Create `src/strategies/my_strategy.py` and subclass `Strategy`:

```python
from src.strategies.base import Signal, Strategy, StrategyContext

class MyStrategy(Strategy):
    @property
    def name(self) -> str:
        return "my_strategy"

    async def initialize(self, context: StrategyContext) -> None:
        pass  # load warmup data, set up state, etc.

    async def on_bar(self, symbol: str, bar, context: StrategyContext) -> Signal | None:
        # bar has: .open .high .low .close .volume .timestamp
        # context has: .portfolio (cash, positions) .data .current_time
        return Signal(symbol=symbol, action="BUY", qty=10)
```

2. Wire it up in `scripts/run_backtest.py` (or `run_paper.py`):

```python
from src.strategies.my_strategy import MyStrategy
strategy = MyStrategy(args.symbols)
```

Strategies must not call Alpaca directly. All market access goes through `context.data` and all order placement through returning a `Signal`.

---

## Tests

```bash
pytest                              # all tests
pytest tests/test_foo.py::test_bar  # single test
```

No API keys required for tests.
