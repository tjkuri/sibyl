from dataclasses import dataclass, field
from datetime import datetime

from src.strategies.base import Signal


@dataclass
class TrackedOrder:
    order_id: str
    strategy_name: str
    signal: Signal
    status: str  # "pending", "filled", "partial_fill", "canceled"
    fill_price: float | None = None
    fill_qty: float | None = None
    submitted_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: datetime | None = None
