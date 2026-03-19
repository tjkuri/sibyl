import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from src.data.historical_provider import HistoricalBar
from src.orders.models import TrackedOrder
from src.strategies.base import Signal

logger = logging.getLogger(__name__)


@dataclass
class _PendingOrder:
    tracked: TrackedOrder
    tif: str  # "day" | "gtc"


class SimulatedBroker:
    def __init__(self, portfolio: "PortfolioManager"):  # type: ignore[name-defined]
        self._portfolio = portfolio
        self._pending: list[_PendingOrder] = []
        self._fill_callbacks: list[Callable[[TrackedOrder], None]] = []
        self._order_counter = 0

    def register_fill_callback(self, callback: Callable[[TrackedOrder], None]) -> None:
        self._fill_callbacks.append(callback)

    async def submit_signal(self, signal: Signal, strategy_name: str) -> TrackedOrder | None:
        if signal.action not in ("BUY", "SELL"):
            logger.warning("SimulatedBroker: ignoring signal with action=%s", signal.action)
            return None
        if signal.qty is None or signal.qty <= 0:
            logger.warning("SimulatedBroker: ignoring signal with qty=%s", signal.qty)
            return None

        self._order_counter += 1
        order_id = f"sim-{self._order_counter:06d}"

        tracked = TrackedOrder(
            order_id=order_id,
            strategy_name=strategy_name,
            signal=signal,
            status="pending",
        )

        tif = "gtc" if signal.order_type == "limit" else "day"
        self._pending.append(_PendingOrder(tracked=tracked, tif=tif))
        return tracked

    def on_bar(self, bar: HistoricalBar) -> None:
        """Fill pending orders at this bar's prices. Call BEFORE engine.on_bar."""
        remaining: list[_PendingOrder] = []

        for pending in self._pending:
            tracked = pending.tracked
            signal = tracked.signal

            if signal.symbol != bar.symbol:
                remaining.append(pending)
                continue

            fill_price: float | None = None

            if signal.order_type == "market":
                fill_price = bar.open
            elif signal.order_type == "limit":
                if signal.limit_price is None:
                    logger.warning("Limit order %s has no limit_price — canceling", tracked.order_id)
                    tracked.status = "canceled"
                    continue
                if signal.action == "BUY" and bar.low <= signal.limit_price:
                    fill_price = signal.limit_price
                elif signal.action == "SELL" and bar.high >= signal.limit_price:
                    fill_price = signal.limit_price
            elif signal.order_type == "stop":
                if signal.limit_price is None:
                    logger.warning("Stop order %s has no limit_price — canceling", tracked.order_id)
                    tracked.status = "canceled"
                    continue
                if signal.action == "BUY" and bar.high >= signal.limit_price:
                    fill_price = signal.limit_price
                elif signal.action == "SELL" and bar.low <= signal.limit_price:
                    fill_price = signal.limit_price

            if fill_price is not None:
                tracked.status = "filled"
                tracked.fill_price = fill_price
                tracked.fill_qty = signal.qty
                tracked.filled_at = datetime.utcnow()
                self._portfolio.on_fill(tracked)
                for cb in self._fill_callbacks:
                    cb(tracked)
            else:
                # Not filled this bar
                if pending.tif == "day":
                    tracked.status = "canceled"
                else:
                    remaining.append(pending)

        self._pending = remaining
