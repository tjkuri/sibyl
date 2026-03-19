import logging
from typing import Any, Callable, Awaitable

from src.strategies.base import Signal, Strategy, StrategyContext

logger = logging.getLogger(__name__)


class StrategyEngine:
    def __init__(self, data: Any = None, portfolio: Any = None):
        self._data = data
        self._portfolio = portfolio
        self._strategies: list[Strategy] = []
        self._signal_handler: Callable[[Signal, str], Awaitable[None]] | None = None

    def register_strategy(self, strategy: Strategy) -> None:
        self._strategies.append(strategy)

    def set_signal_handler(self, callback: Callable[[Signal, str], Awaitable[None]]) -> None:
        self._signal_handler = callback

    async def initialize(self) -> None:
        context = StrategyContext(
            portfolio=self._portfolio,
            data=self._data,
            current_time=None,  # type: ignore[arg-type]
        )
        for strategy in self._strategies:
            await strategy.initialize(context)

    async def on_bar(self, bar: Any) -> None:
        context = StrategyContext(
            portfolio=self._portfolio,
            data=self._data,
            current_time=bar.timestamp,
        )
        for strategy in self._strategies:
            if bar.symbol not in strategy.symbols:
                continue
            signal = await strategy.on_bar(bar.symbol, bar, context)
            if signal is None or signal.action == "HOLD":
                continue
            if signal.qty is None or signal.qty <= 0:
                logger.warning(
                    "Strategy %s emitted signal with invalid qty=%s for %s — skipping",
                    strategy.name,
                    signal.qty,
                    signal.symbol,
                )
                continue
            if self._signal_handler is not None:
                await self._signal_handler(signal, strategy.name)
