import logging
import os
from dataclasses import dataclass

import pandas as pd

from src.backtest.metrics import BacktestMetrics
from src.backtest.simulated_broker import SimulatedBroker
from src.data.historical_provider import HistoricalBar, HistoricalDataProvider
from src.engine import StrategyEngine
from src.portfolio.manager import PortfolioManager
from src.portfolio.models import PortfolioSnapshot
from src.strategies.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    snapshots: list[PortfolioSnapshot]
    metrics: BacktestMetrics
    buy_and_hold_return_pct: float | None


class BacktestRunner:
    def __init__(
        self,
        symbols: list[str],
        strategy: Strategy,
        data_dir: str = "./data",
        initial_cash: float = 100_000.0,
        start: str | None = None,
        end: str | None = None,
        timeframe: str = "1Day",
    ):
        self._symbols = symbols
        self._strategy = strategy
        self._data_dir = data_dir
        self._initial_cash = initial_cash
        self._start = start
        self._end = end
        self._timeframe = timeframe

    async def run(self) -> BacktestResult:
        data = HistoricalDataProvider(data_dir=self._data_dir, timeframe=self._timeframe)
        portfolio = PortfolioManager(client=None, initial_cash=self._initial_cash)
        broker = SimulatedBroker(portfolio=portfolio)
        engine = StrategyEngine(data=data, portfolio=portfolio)

        engine.register_strategy(self._strategy)
        await engine.initialize()
        engine.set_signal_handler(broker.submit_signal)

        # Pre-compute date bounds once so _on_bar doesn't re-parse on every bar
        _start_ts = pd.Timestamp(self._start, tz="UTC") if self._start else None
        _end_ts = pd.Timestamp(self._end, tz="UTC") if self._end else None

        async def _on_bar(bar: HistoricalBar) -> None:
            # Skip bars outside the requested backtest window.
            # The parquet file may contain warmup data (e.g. for MA crossover)
            # that predates --start; those bars must not generate trades or snapshots.
            ts = bar.timestamp
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            if _start_ts is not None and ts < _start_ts:
                return
            if _end_ts is not None and ts >= _end_ts:
                return

            broker.on_bar(bar)
            await engine.on_bar(bar)
            # Update current price so market_value reflects latest close
            pos = portfolio.get_position(bar.symbol)
            if pos is not None:
                pos.current_price = bar.close
            portfolio.snapshot()

        await data.subscribe_bars(self._symbols, _on_bar)
        await data.start()
        await data.wait()

        bnh = self._compute_buy_and_hold()
        metrics = BacktestMetrics(portfolio.snapshots)
        return BacktestResult(
            snapshots=portfolio.snapshots,
            metrics=metrics,
            buy_and_hold_return_pct=bnh,
        )

    def _compute_buy_and_hold(self) -> float | None:
        """Equal-weight buy-and-hold return across symbols."""
        per_symbol_returns: list[float] = []

        for symbol in self._symbols:
            for fname in os.listdir(self._data_dir):
                if fname.startswith(f"{symbol}_") and fname.endswith(".parquet"):
                    df = pd.read_parquet(os.path.join(self._data_dir, fname))
                    df = df.reset_index()

                    if self._start is not None:
                        df = df[df["timestamp"] >= pd.Timestamp(self._start, tz="UTC")]
                    if self._end is not None:
                        df = df[df["timestamp"] < pd.Timestamp(self._end, tz="UTC")]

                    if len(df) < 2:
                        break

                    df = df.sort_values("timestamp")
                    first_close = float(df["close"].iloc[0])
                    last_close = float(df["close"].iloc[-1])
                    if first_close > 0:
                        per_symbol_returns.append((last_close - first_close) / first_close * 100)
                    break

        if not per_symbol_returns:
            return None

        return sum(per_symbol_returns) / len(per_symbol_returns)
