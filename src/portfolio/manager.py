import asyncio
import logging
from datetime import datetime

from src.alpaca_client import AlpacaClient
from src.orders.models import TrackedOrder
from src.portfolio.models import Position, PortfolioSnapshot

logger = logging.getLogger(__name__)


class PortfolioManager:
    def __init__(self, client: AlpacaClient | None = None, initial_cash: float = 0.0):
        self._client = client
        self._positions: dict[str, Position] = {}
        self._cash: float = initial_cash
        self._snapshots: list[PortfolioSnapshot] = []

    async def sync(self) -> None:
        if self._client is None:
            logger.warning("sync() called in backtest mode — no-op")
            return

        loop = asyncio.get_event_loop()

        account = await loop.run_in_executor(None, self._client.trading.get_account)
        self._cash = float(account.cash)

        positions = await loop.run_in_executor(None, self._client.trading.get_all_positions)
        self._positions = {
            p.symbol: Position(
                symbol=p.symbol,
                qty=float(p.qty),
                avg_cost=float(p.avg_entry_price),
                current_price=float(p.current_price),
            )
            for p in positions
        }

    def update_position(self, symbol: str, qty_delta: float, fill_price: float) -> None:
        if symbol not in self._positions:
            if qty_delta > 0:
                self._positions[symbol] = Position(
                    symbol=symbol,
                    qty=qty_delta,
                    avg_cost=fill_price,
                    current_price=fill_price,
                )
            # If selling a position we don't have, skip silently
        else:
            pos = self._positions[symbol]
            if qty_delta > 0:
                new_qty = pos.qty + qty_delta
                pos.avg_cost = (pos.qty * pos.avg_cost + qty_delta * fill_price) / new_qty
                pos.qty = new_qty
                pos.current_price = fill_price
            else:
                pos.qty += qty_delta  # qty_delta is negative
                pos.current_price = fill_price
                if pos.qty <= 0:
                    del self._positions[symbol]

        self._cash -= qty_delta * fill_price

    def on_fill(self, order: TrackedOrder) -> None:
        if self._client is not None:
            # Live mode: re-sync with Alpaca as source of truth
            asyncio.create_task(self.sync())
        else:
            # Backtest mode: update locally
            if order.fill_price is None or order.fill_qty is None:
                logger.warning("on_fill called with missing fill data for order %s", order.order_id)
                return

            fill_price = order.fill_price
            fill_qty = order.fill_qty
            signal = order.signal

            if signal.action == "BUY":
                qty_delta = fill_qty
            elif signal.action == "SELL":
                qty_delta = -fill_qty
            else:
                logger.warning("on_fill: unknown signal action %s", signal.action)
                return

            self.update_position(signal.symbol, qty_delta, fill_price)

    def get_position(self, symbol: str) -> Position | None:
        return self._positions.get(symbol)

    def get_all_positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def snapshot(self) -> PortfolioSnapshot:
        snap = PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            positions=dict(self._positions),
            cash=self._cash,
            total_value=self.total_value,
        )
        self._snapshots.append(snap)
        return snap

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def total_value(self) -> float:
        return self._cash + sum(p.market_value for p in self._positions.values())

    @property
    def snapshots(self) -> list[PortfolioSnapshot]:
        return self._snapshots
