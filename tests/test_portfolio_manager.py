"""Unit tests for PortfolioManager (backtest mode, client=None)."""
import pytest
from datetime import datetime

from src.orders.models import TrackedOrder
from src.portfolio.manager import PortfolioManager
from src.strategies.base import Signal


def make_portfolio(initial_cash: float = 10_000.0) -> PortfolioManager:
    return PortfolioManager(client=None, initial_cash=initial_cash)


def make_fill(symbol: str, action: str, qty: float, price: float) -> TrackedOrder:
    signal = Signal(symbol=symbol, action=action, qty=qty)
    return TrackedOrder(
        order_id="test-001",
        strategy_name="test",
        signal=signal,
        status="filled",
        fill_price=price,
        fill_qty=qty,
        filled_at=datetime.utcnow(),
    )


def test_initial_state():
    pm = make_portfolio(10_000)
    assert pm.cash == 10_000.0
    assert pm.get_all_positions() == {}


def test_buy_creates_position():
    pm = make_portfolio()
    pm.update_position("AAPL", 10, 100.0)
    pos = pm.get_position("AAPL")
    assert pos is not None
    assert pos.qty == 10
    assert pos.avg_cost == 100.0


def test_sell_reduces_position():
    pm = make_portfolio()
    pm.update_position("AAPL", 10, 100.0)
    pm.update_position("AAPL", -5, 110.0)
    pos = pm.get_position("AAPL")
    assert pos is not None
    assert pos.qty == 5


def test_sell_clears_position():
    pm = make_portfolio()
    pm.update_position("AAPL", 10, 100.0)
    pm.update_position("AAPL", -10, 110.0)
    pos = pm.get_position("AAPL")
    assert pos is None


def test_avg_cost_averaging():
    pm = make_portfolio(100_000)
    pm.update_position("AAPL", 10, 100.0)
    pm.update_position("AAPL", 10, 110.0)
    pos = pm.get_position("AAPL")
    assert pos is not None
    assert pos.avg_cost == pytest.approx(105.0)


def test_cash_decreases_on_buy():
    pm = make_portfolio(10_000)
    pm.update_position("AAPL", 10, 100.0)
    assert pm.cash == pytest.approx(9_000.0)


def test_cash_increases_on_sell():
    pm = make_portfolio(10_000)
    pm.update_position("AAPL", 10, 100.0)   # cash → 9000
    pm.update_position("AAPL", -10, 100.0)  # cash → 10000
    assert pm.cash == pytest.approx(10_000.0)


def test_total_value():
    pm = make_portfolio(10_000)
    pm.update_position("AAPL", 10, 100.0)  # market_value = 10*100 = 1000; cash = 9000
    # total = 9000 + 1000 = 10000
    assert pm.total_value == pytest.approx(10_000.0)


def test_on_fill_buy():
    pm = make_portfolio(10_000)
    order = make_fill("AAPL", "BUY", 5, 150.0)
    pm.on_fill(order)
    pos = pm.get_position("AAPL")
    assert pos is not None
    assert pos.qty == 5
    assert pos.avg_cost == 150.0


def test_on_fill_sell():
    pm = make_portfolio(10_000)
    pm.update_position("AAPL", 10, 100.0)
    order = make_fill("AAPL", "SELL", 4, 110.0)
    pm.on_fill(order)
    pos = pm.get_position("AAPL")
    assert pos is not None
    assert pos.qty == 6


def test_snapshot_appended():
    pm = make_portfolio(10_000)
    assert len(pm.snapshots) == 0
    pm.snapshot()
    assert len(pm.snapshots) == 1
    snap = pm.snapshots[0]
    assert snap.cash == 10_000.0
    assert snap.total_value == 10_000.0
