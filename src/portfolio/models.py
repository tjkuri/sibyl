from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    symbol: str
    qty: float
    avg_cost: float
    current_price: float

    @property
    def market_value(self) -> float:
        return self.qty * self.current_price

    @property
    def unrealized_pl(self) -> float:
        return (self.current_price - self.avg_cost) * self.qty


@dataclass
class PortfolioSnapshot:
    timestamp: datetime
    positions: dict[str, Position]  # symbol → Position
    cash: float
    total_value: float
