from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Signal:
    symbol: str
    action: str  # "BUY", "SELL", "HOLD"
    qty: float | None = None
    order_type: str = "market"  # "market", "limit", "stop"
    limit_price: float | None = None
    reason: str = ""


@dataclass
class StrategyContext:
    portfolio: Any  # PortfolioManager (Step 6) — Any for now
    data: Any       # DataProvider
    current_time: datetime


class Strategy(ABC):
    def __init__(self, symbols: list[str], config: dict | None = None):
        self.symbols = symbols
        self.config = config or {}

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def initialize(self, context: StrategyContext) -> None: ...

    @abstractmethod
    async def on_bar(self, symbol: str, bar: Any, context: StrategyContext) -> Signal | None: ...

    def on_order_fill(self, order_result: dict) -> None:
        pass
