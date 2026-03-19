"""
Usage:
    python scripts/run_backtest.py --symbols AAPL SPY --initial-cash 100000
    python scripts/run_backtest.py --symbols AAPL --data-dir ./data --start 2023-01-01 --end 2024-01-01
    python scripts/run_backtest.py --symbols SPY --start 2020-01-01 --end 2024-12-31 --strategy ma_crossover
"""
import argparse
import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.backtest.runner import BacktestRunner
from src.strategies.buy_and_hold import BuyAndHoldStrategy
from src.strategies.ma_crossover import MovingAverageCrossoverStrategy
from src.strategies.rsi import RSIStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Sibyl backtest")
    parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols")
    parser.add_argument("--initial-cash", type=float, default=100_000.0)
    parser.add_argument("--data-dir", default="./data")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--timeframe", default="1Day", help="Bar timeframe to replay (default: 1Day)")
    parser.add_argument(
        "--strategy",
        choices=["buy_and_hold", "ma_crossover", "rsi"],
        default="buy_and_hold",
        help="Strategy to run (default: buy_and_hold)",
    )
    return parser.parse_args()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    args = parse_args()

    if args.strategy == "ma_crossover":
        warmup_start = (
            datetime.strptime(args.start, "%Y-%m-%d") - timedelta(days=100)
        ).strftime("%Y-%m-%d") if args.start else None
        strategy = MovingAverageCrossoverStrategy(
            args.symbols,
            warmup_start=warmup_start,
            warmup_end=args.start,
        )
    elif args.strategy == "rsi":
        strategy = RSIStrategy(args.symbols)
    else:
        strategy = BuyAndHoldStrategy(args.symbols)

    runner = BacktestRunner(
        symbols=args.symbols,
        strategy=strategy,
        data_dir=args.data_dir,
        initial_cash=args.initial_cash,
        start=args.start,
        end=args.end,
        timeframe=args.timeframe,
    )

    print(f"Running backtest: symbols={args.symbols}, cash={args.initial_cash:,.0f}")
    result = await runner.run()

    print(f"Snapshots: {len(result.snapshots)}")
    result.metrics.print_summary()

    if result.buy_and_hold_return_pct is not None:
        print(f"Buy-and-hold (equal-weight): {result.buy_and_hold_return_pct:.2f}%")
        strat_return = result.metrics.total_return_pct()
        diff = strat_return - result.buy_and_hold_return_pct
        print(f"Strategy vs B&H: {diff:+.2f}%")


if __name__ == "__main__":
    asyncio.run(main())
