import logging
import math
from typing import Any

from src.strategies.base import Signal, Strategy, StrategyContext

logger = logging.getLogger(__name__)


class BuyAndHoldStrategy(Strategy):
    def __init__(self, symbols: list[str], config: dict | None = None):
        super().__init__(symbols, config)
        self._bought: set[str] = set()

    @property
    def name(self) -> str:
        return "buy_and_hold"

    async def initialize(self, context: StrategyContext) -> None:
        pass

    async def on_bar(self, symbol: str, bar: Any, context: StrategyContext) -> Signal | None:
        if symbol not in self._bought:
            cash = context.portfolio.cash
            qty = math.floor(cash * 0.95 / bar.close)
            if qty < 1:
                logger.info(
                    "BUY skipped %s: cash=%.2f close=%.4f — insufficient funds",
                    symbol, cash, bar.close,
                )
                return None
            self._bought.add(symbol)
            cash_used = qty * bar.close
            cash_remaining = cash - cash_used
            logger.info(
                "BUY signal %s: date=%s close=%.4f qty=%d cash_used=%.2f cash_remaining=%.2f",
                symbol, bar.timestamp.date(), bar.close, qty, cash_used, cash_remaining,
            )
            return Signal(symbol=symbol, action="BUY", qty=qty)
        return None
