"""Paper/live trading entry point.

Usage:
    python scripts/run_paper.py --symbols AAPL SPY [--qty 1] [--log-level INFO]
"""
import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import AlpacaSettings
from src.alpaca_client import AlpacaClient
from src.data.live_provider import LiveDataProvider
from src.engine import StrategyEngine
from src.orders.manager import OrderManager
from src.portfolio.manager import PortfolioManager
from src.portfolio.reporter import PortfolioReporter
from datetime import timedelta

from src.strategies.buy_and_hold import BuyAndHoldStrategy
from src.strategies.ma_crossover import MovingAverageCrossoverStrategy
from src.strategies.rsi import RSIStrategy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper/live trading")
    parser.add_argument("--symbols", nargs="+", required=True, help="Symbols to trade")
    parser.add_argument(
        "--strategy",
        choices=["buy_and_hold", "ma_crossover", "rsi"],
        default="buy_and_hold",
        help="Strategy to run (default: buy_and_hold)",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser.parse_args()


async def status_loop(portfolio: PortfolioManager, shutdown_event: asyncio.Event) -> None:
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            pass
        if not shutdown_event.is_set():
            now = datetime.now().strftime("%H:%M:%S")
            positions = portfolio.get_all_positions()
            pos_str = " ".join(f"{sym}×{p.qty:.0f}" for sym, p in positions.items())
            print(
                f"[{now}] cash=${portfolio.cash:,.2f} | "
                f"total=${portfolio.total_value:,.2f} | "
                f"positions: {pos_str or 'none'}"
            )


async def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = AlpacaSettings()
    client = AlpacaClient(settings)
    mode = "paper" if client.is_paper else "live"
    print(f"Starting {mode} trading for {args.symbols}")

    data = LiveDataProvider(client)
    portfolio = PortfolioManager(client=client)
    order_manager = OrderManager(client)
    engine = StrategyEngine(data=data, portfolio=portfolio)

    if args.strategy == "ma_crossover":
        warmup_start = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        warmup_end = datetime.now().strftime("%Y-%m-%d")
        strategy = MovingAverageCrossoverStrategy(
            args.symbols,
            warmup_start=warmup_start,
            warmup_end=warmup_end,
        )
    elif args.strategy == "rsi":
        strategy = RSIStrategy(args.symbols)
    else:
        strategy = BuyAndHoldStrategy(args.symbols)
    engine.register_strategy(strategy)

    await engine.initialize()

    order_manager.register_fill_callback(portfolio.on_fill)
    engine.set_signal_handler(order_manager.submit_signal)

    await portfolio.sync()
    portfolio.snapshot()
    print(f"Initial portfolio: cash=${portfolio.cash:,.2f}, total=${portfolio.total_value:,.2f}")

    shutdown_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, shutdown_event.set)
    loop.add_signal_handler(signal.SIGTERM, shutdown_event.set)

    await order_manager.start()
    await data.subscribe_bars(args.symbols, engine.on_bar)
    await data.start()
    print("Streaming bars. Press Ctrl-C to stop.")

    status_task = asyncio.create_task(status_loop(portfolio, shutdown_event))

    await shutdown_event.wait()

    print("\nShutting down...")
    status_task.cancel()
    try:
        await status_task
    except asyncio.CancelledError:
        pass

    await data.stop()
    await order_manager.stop()

    portfolio.snapshot()
    print(f"Final portfolio: cash=${portfolio.cash:,.2f}, total=${portfolio.total_value:,.2f}")
    reporter = PortfolioReporter(portfolio.snapshots)
    reporter.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
