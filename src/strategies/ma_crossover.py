import logging
import math
from collections import deque
from statistics import mean
from typing import Any

from src.strategies.base import Signal, Strategy, StrategyContext

logger = logging.getLogger(__name__)


class MovingAverageCrossoverStrategy(Strategy):
    def __init__(
        self,
        symbols: list[str],
        short_window: int = 20,
        long_window: int = 50,
        warmup_start: str | None = None,
        warmup_end: str | None = None,
        config: dict | None = None,
    ):
        super().__init__(symbols, config)
        self._short_window = short_window
        self._long_window = long_window
        self._warmup_start = warmup_start
        self._warmup_end = warmup_end

        self._prices: dict[str, deque] = {}
        self._prev_short: dict[str, float] = {}
        self._prev_long: dict[str, float] = {}
        self._in_position: dict[str, bool] = {}

    @property
    def name(self) -> str:
        return "ma_crossover"

    async def initialize(self, context: StrategyContext) -> None:
        for symbol in self.symbols:
            self._prices[symbol] = deque(maxlen=self._long_window)
            self._prev_short[symbol] = 0.0
            self._prev_long[symbol] = 0.0
            self._in_position[symbol] = False

        if self._warmup_start and self._warmup_end:
            try:
                df = await context.data.get_bars(
                    self.symbols, "1Day", self._warmup_start, self._warmup_end
                )
                for symbol in self.symbols:
                    if isinstance(df.index, __import__("pandas").MultiIndex):
                        sym_df = df.xs(symbol, level="symbol") if symbol in df.index.get_level_values("symbol") else df
                    else:
                        sym_df = df[df["symbol"] == symbol] if "symbol" in df.columns else df

                    closes = sym_df["close"].tolist()
                    for c in closes:
                        self._prices[symbol].append(c)

                    prices_list = list(self._prices[symbol])
                    if len(prices_list) >= self._long_window:
                        self._prev_short[symbol] = mean(prices_list[-self._short_window:])
                        self._prev_long[symbol] = mean(prices_list)
            except Exception:
                pass  # warmup data unavailable — strategy will warm up on live bars

    async def on_bar(self, symbol: str, bar: Any, context: StrategyContext) -> Signal | None:
        if symbol not in self._prices:
            self._prices[symbol] = deque(maxlen=self._long_window)
            self._prev_short[symbol] = 0.0
            self._prev_long[symbol] = 0.0
            self._in_position[symbol] = False

        self._prices[symbol].append(bar.close)
        prices_list = list(self._prices[symbol])

        if len(prices_list) < self._long_window:
            return None

        short_ma = mean(prices_list[-self._short_window:])
        long_ma = mean(prices_list)

        prev_short = self._prev_short[symbol]
        prev_long = self._prev_long[symbol]

        signal = None

        if prev_short > 0 and prev_long > 0:
            if prev_short <= prev_long and short_ma > long_ma:
                # Crossover up — buy if flat
                if not self._in_position[symbol]:
                    qty = math.floor(context.portfolio.cash * 0.95 / bar.close)
                    if qty >= 1:
                        self._in_position[symbol] = True
                        logger.info(
                            "BUY signal %s: date=%s close=%.4f qty=%d short_ma=%.4f long_ma=%.4f cash_used=%.2f cash_remaining=%.2f",
                            symbol, bar.timestamp.date(), bar.close, qty,
                            short_ma, long_ma,
                            qty * bar.close, context.portfolio.cash - qty * bar.close,
                        )
                        signal = Signal(symbol=symbol, action="BUY", qty=qty, reason="MA crossover up")
            elif prev_short >= prev_long and short_ma < long_ma:
                # Crossover down — sell if holding
                if self._in_position[symbol]:
                    position = context.portfolio.get_position(symbol)
                    qty = position.qty if position else 0
                    if qty > 0:
                        self._in_position[symbol] = False
                        logger.info(
                            "SELL signal %s: date=%s close=%.4f qty=%d short_ma=%.4f long_ma=%.4f",
                            symbol, bar.timestamp.date(), bar.close, qty, short_ma, long_ma,
                        )
                        signal = Signal(symbol=symbol, action="SELL", qty=qty, reason="MA crossover down")

        self._prev_short[symbol] = short_ma
        self._prev_long[symbol] = long_ma

        return signal
