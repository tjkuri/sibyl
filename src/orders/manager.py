import asyncio
import logging
import threading
from datetime import datetime
from typing import Callable

from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, StopOrderRequest

from src.alpaca_client import AlpacaClient
from src.orders.models import TrackedOrder
from src.strategies.base import Signal

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, client: AlpacaClient):
        self._client = client
        self._orders: dict[str, TrackedOrder] = {}
        self._fill_callbacks: list[Callable[[TrackedOrder], None]] = []
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._stream_thread: threading.Thread | None = None

    def register_fill_callback(self, callback: Callable[[TrackedOrder], None]) -> None:
        self._fill_callbacks.append(callback)

    async def submit_signal(self, signal: Signal, strategy_name: str) -> TrackedOrder | None:
        if signal.action == "BUY":
            side = OrderSide.BUY
        elif signal.action == "SELL":
            side = OrderSide.SELL
        else:
            logger.warning("Unknown signal action %s for %s — skipping", signal.action, signal.symbol)
            return None

        qty = float(signal.qty)  # type: ignore[arg-type]

        order_type = signal.order_type.lower()
        if order_type == "market":
            request = MarketOrderRequest(
                symbol=signal.symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
        elif order_type == "limit":
            if signal.limit_price is None:
                logger.warning("Limit order for %s missing limit_price — skipping", signal.symbol)
                return None
            request = LimitOrderRequest(
                symbol=signal.symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.GTC,
                limit_price=signal.limit_price,
            )
        elif order_type == "stop":
            if signal.limit_price is None:
                logger.warning("Stop order for %s missing limit_price (stop_price) — skipping", signal.symbol)
                return None
            request = StopOrderRequest(
                symbol=signal.symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.GTC,
                stop_price=signal.limit_price,
            )
        else:
            logger.warning("Unknown order_type %s for %s — skipping", signal.order_type, signal.symbol)
            return None

        logger.info("Submitting %s %s qty=%s (%s)", signal.action, signal.symbol, qty, order_type)
        print(f"Submitting {signal.action} {signal.symbol} qty={qty} ({order_type})")

        loop = asyncio.get_event_loop()
        order = await loop.run_in_executor(None, self._client.trading.submit_order, request)

        tracked = TrackedOrder(
            order_id=str(order.id),
            strategy_name=strategy_name,
            signal=signal,
            status="pending",
        )
        self._orders[tracked.order_id] = tracked
        print(f"Order submitted: {tracked.order_id}")
        logger.info("Order submitted: %s", tracked.order_id)
        return tracked

    async def start(self) -> None:
        self._main_loop = asyncio.get_event_loop()
        self._client.trade_stream.subscribe_trade_updates(self._on_trade_update)
        self._stream_thread = threading.Thread(target=self._client.trade_stream.run, daemon=True)
        self._stream_thread.start()

    async def stop(self) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._client.trade_stream.stop)

    async def _on_trade_update(self, data) -> None:
        event = data.event
        order_id = str(data.order.id)
        tracked = self._orders.get(order_id)
        if tracked is None:
            logger.debug("Trade update for unknown order %s — ignoring", order_id)
            return

        tracked.status = event
        if event in ("fill", "partial_fill"):
            try:
                tracked.fill_price = float(data.order.filled_avg_price)
            except (TypeError, ValueError):
                tracked.fill_price = None
            try:
                tracked.fill_qty = float(data.order.filled_qty)
            except (TypeError, ValueError):
                tracked.fill_qty = None
            tracked.filled_at = datetime.utcnow()
            if self._main_loop is not None:
                asyncio.run_coroutine_threadsafe(self._notify_fill(tracked), self._main_loop)

    async def _notify_fill(self, order: TrackedOrder) -> None:
        for callback in self._fill_callbacks:
            callback(order)
