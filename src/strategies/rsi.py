import logging
import math
from collections import deque
from typing import Any

from src.strategies.base import Signal, Strategy, StrategyContext

logger = logging.getLogger(__name__)


class RSIStrategy(Strategy):
    """
    Buy when RSI crosses below `oversold` (default 30).
    Sell when RSI crosses above `overbought` (default 70).
    Uses a standard Wilder smoothed RSI with `period` bars (default 14).
    """

    def __init__(
        self,
        symbols: list[str],
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        config: dict | None = None,
    ):
        super().__init__(symbols, config)
        self._period = period
        self._oversold = oversold
        self._overbought = overbought

        self._closes: dict[str, deque] = {}
        self._avg_gain: dict[str, float] = {}
        self._avg_loss: dict[str, float] = {}
        self._prev_rsi: dict[str, float] = {}
        self._in_position: dict[str, bool] = {}
        self._warmed_up: dict[str, bool] = {}

    @property
    def name(self) -> str:
        return "rsi"

    async def initialize(self, context: StrategyContext) -> None:
        for symbol in self.symbols:
            self._closes[symbol] = deque(maxlen=self._period + 1)
            self._avg_gain[symbol] = 0.0
            self._avg_loss[symbol] = 0.0
            self._prev_rsi[symbol] = 50.0
            self._in_position[symbol] = False
            self._warmed_up[symbol] = False

    async def on_bar(self, symbol: str, bar: Any, context: StrategyContext) -> Signal | None:
        if symbol not in self._closes:
            self._closes[symbol] = deque(maxlen=self._period + 1)
            self._avg_gain[symbol] = 0.0
            self._avg_loss[symbol] = 0.0
            self._prev_rsi[symbol] = 50.0
            self._in_position[symbol] = False
            self._warmed_up[symbol] = False

        self._closes[symbol].append(bar.close)

        if len(self._closes[symbol]) < self._period + 1:
            return None

        closes = list(self._closes[symbol])
        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

        if not self._warmed_up[symbol]:
            gains = [c for c in changes if c > 0]
            losses = [-c for c in changes if c < 0]
            self._avg_gain[symbol] = sum(gains) / self._period
            self._avg_loss[symbol] = sum(losses) / self._period
            self._warmed_up[symbol] = True
        else:
            # Wilder smoothing
            change = changes[-1]
            gain = change if change > 0 else 0.0
            loss = -change if change < 0 else 0.0
            self._avg_gain[symbol] = (self._avg_gain[symbol] * (self._period - 1) + gain) / self._period
            self._avg_loss[symbol] = (self._avg_loss[symbol] * (self._period - 1) + loss) / self._period

        if self._avg_loss[symbol] == 0:
            rsi = 100.0
        else:
            rs = self._avg_gain[symbol] / self._avg_loss[symbol]
            rsi = 100.0 - (100.0 / (1.0 + rs))

        prev_rsi = self._prev_rsi[symbol]
        self._prev_rsi[symbol] = rsi

        signal = None

        if prev_rsi >= self._oversold and rsi < self._oversold:
            # Crossed into oversold — buy
            if not self._in_position[symbol]:
                qty = math.floor(context.portfolio.cash * 0.95 / bar.close)
                if qty >= 1:
                    self._in_position[symbol] = True
                    logger.info(
                        "BUY signal %s: date=%s close=%.4f qty=%d rsi=%.2f cash_used=%.2f cash_remaining=%.2f",
                        symbol, bar.timestamp, bar.close, qty, rsi,
                        qty * bar.close, context.portfolio.cash - qty * bar.close,
                    )
                    signal = Signal(symbol=symbol, action="BUY", qty=qty, reason=f"RSI oversold ({rsi:.1f})")

        elif prev_rsi <= self._overbought and rsi > self._overbought:
            # Crossed into overbought — sell
            if self._in_position[symbol]:
                position = context.portfolio.get_position(symbol)
                qty = position.qty if position else 0
                if qty > 0:
                    self._in_position[symbol] = False
                    logger.info(
                        "SELL signal %s: date=%s close=%.4f qty=%d rsi=%.2f",
                        symbol, bar.timestamp, bar.close, qty, rsi,
                    )
                    signal = Signal(symbol=symbol, action="SELL", qty=qty, reason=f"RSI overbought ({rsi:.1f})")

        return signal
