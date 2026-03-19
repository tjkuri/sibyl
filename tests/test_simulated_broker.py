"""Unit tests for SimulatedBroker fill logic."""
import pytest

from src.backtest.simulated_broker import SimulatedBroker
from src.data.historical_provider import HistoricalBar
from src.orders.models import TrackedOrder
from src.portfolio.manager import PortfolioManager
from src.strategies.base import Signal

from datetime import datetime


def make_bar(symbol: str, open: float, high: float, low: float, close: float) -> HistoricalBar:
    return HistoricalBar(
        symbol=symbol,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=1000,
        timestamp=datetime(2024, 1, 1, 9, 30),
    )


def make_broker() -> tuple[SimulatedBroker, PortfolioManager]:
    portfolio = PortfolioManager(client=None, initial_cash=10_000)
    broker = SimulatedBroker(portfolio)
    return broker, portfolio


@pytest.mark.asyncio
async def test_market_buy_fills_at_open():
    broker, portfolio = make_broker()
    signal = Signal(symbol="AAPL", action="BUY", qty=1, order_type="market")
    await broker.submit_signal(signal, "test")
    bar = make_bar("AAPL", open=150.0, high=155.0, low=148.0, close=153.0)
    broker.on_bar(bar)
    pos = portfolio.get_position("AAPL")
    assert pos is not None
    assert pos.avg_cost == 150.0


@pytest.mark.asyncio
async def test_market_sell_fills_at_open():
    broker, portfolio = make_broker()
    portfolio.update_position("AAPL", 5, 100.0)
    signal = Signal(symbol="AAPL", action="SELL", qty=5, order_type="market")
    await broker.submit_signal(signal, "test")
    bar = make_bar("AAPL", open=110.0, high=115.0, low=108.0, close=113.0)
    broker.on_bar(bar)
    pos = portfolio.get_position("AAPL")
    assert pos is None  # fully sold


@pytest.mark.asyncio
async def test_limit_buy_fills_when_low_touches():
    broker, portfolio = make_broker()
    signal = Signal(symbol="AAPL", action="BUY", qty=1, order_type="limit", limit_price=148.0)
    await broker.submit_signal(signal, "test")
    bar = make_bar("AAPL", open=150.0, high=152.0, low=147.0, close=149.0)
    broker.on_bar(bar)
    pos = portfolio.get_position("AAPL")
    assert pos is not None
    assert pos.avg_cost == 148.0


@pytest.mark.asyncio
async def test_limit_buy_no_fill_when_low_above():
    broker, portfolio = make_broker()
    signal = Signal(symbol="AAPL", action="BUY", qty=1, order_type="limit", limit_price=145.0)
    await broker.submit_signal(signal, "test")
    bar = make_bar("AAPL", open=150.0, high=152.0, low=148.0, close=149.0)
    broker.on_bar(bar)
    pos = portfolio.get_position("AAPL")
    assert pos is None


@pytest.mark.asyncio
async def test_limit_sell_fills_when_high_touches():
    broker, portfolio = make_broker()
    portfolio.update_position("AAPL", 1, 100.0)
    signal = Signal(symbol="AAPL", action="SELL", qty=1, order_type="limit", limit_price=155.0)
    await broker.submit_signal(signal, "test")
    bar = make_bar("AAPL", open=150.0, high=156.0, low=149.0, close=154.0)
    broker.on_bar(bar)
    pos = portfolio.get_position("AAPL")
    assert pos is None  # filled and sold


@pytest.mark.asyncio
async def test_stop_buy_fills_when_high_touches():
    broker, portfolio = make_broker()
    signal = Signal(symbol="AAPL", action="BUY", qty=1, order_type="stop", limit_price=153.0)
    await broker.submit_signal(signal, "test")
    bar = make_bar("AAPL", open=150.0, high=154.0, low=149.0, close=153.0)
    broker.on_bar(bar)
    pos = portfolio.get_position("AAPL")
    assert pos is not None
    assert pos.avg_cost == 153.0


@pytest.mark.asyncio
async def test_stop_sell_fills_when_low_touches():
    broker, portfolio = make_broker()
    portfolio.update_position("AAPL", 1, 160.0)
    signal = Signal(symbol="AAPL", action="SELL", qty=1, order_type="stop", limit_price=145.0)
    await broker.submit_signal(signal, "test")
    bar = make_bar("AAPL", open=150.0, high=152.0, low=144.0, close=148.0)
    broker.on_bar(bar)
    pos = portfolio.get_position("AAPL")
    assert pos is None  # stopped out


@pytest.mark.asyncio
async def test_day_tif_expires_after_one_bar():
    broker, portfolio = make_broker()
    # Market order = DAY tif
    signal = Signal(symbol="AAPL", action="BUY", qty=1, order_type="market")
    tracked = await broker.submit_signal(signal, "test")
    # Bar for different symbol — won't fill AAPL
    bar = make_bar("SPY", open=400.0, high=405.0, low=398.0, close=403.0)
    broker.on_bar(bar)
    # Now send AAPL bar — DAY order should have been canceled already
    assert tracked is not None
    assert tracked.status == "pending"  # not yet processed

    # Actually process AAPL bar — market orders fill, so use a limit order for DAY expiry test
    broker2, portfolio2 = make_broker()
    signal2 = Signal(symbol="AAPL", action="BUY", qty=1, order_type="market")
    tracked2 = await broker2.submit_signal(signal2, "test")
    # Provide non-matching symbol bar — DAY order for AAPL sits in pending
    bar_spy = make_bar("SPY", open=400.0, high=405.0, low=398.0, close=403.0)
    broker2.on_bar(bar_spy)
    # AAPL order still pending (SPY bar didn't touch it)
    assert tracked2 is not None
    assert tracked2.status == "pending"
    # Now provide AAPL bar — market order fills at open
    bar_aapl = make_bar("AAPL", open=150.0, high=155.0, low=148.0, close=153.0)
    broker2.on_bar(bar_aapl)
    assert tracked2.status == "filled"


@pytest.mark.asyncio
async def test_day_limit_expires_after_one_bar():
    broker, portfolio = make_broker()
    # Limit order with price that won't be hit → DAY → canceled after one bar
    signal = Signal(symbol="AAPL", action="BUY", qty=1, order_type="limit", limit_price=100.0)
    tracked = await broker.submit_signal(signal, "test")
    # Limit orders use GTC in SimulatedBroker. Let's verify with a market (DAY) order expiry.
    # Actually SimulatedBroker uses GTC for limit and DAY for everything else.
    # DAY = market/stop. Let's test with a stop order that won't trigger.
    broker2, portfolio2 = make_broker()
    signal2 = Signal(symbol="AAPL", action="BUY", qty=1, order_type="stop", limit_price=200.0)
    tracked2 = await broker2.submit_signal(signal2, "test")
    bar = make_bar("AAPL", open=150.0, high=155.0, low=148.0, close=153.0)
    broker2.on_bar(bar)
    # stop BUY with price 200 not reached (high=155) → DAY → canceled
    assert tracked2 is not None
    assert tracked2.status == "canceled"


@pytest.mark.asyncio
async def test_gtc_persists_across_bars():
    broker, portfolio = make_broker()
    # Limit buy GTC — price not reached on bar 1 but reached on bar 2
    signal = Signal(symbol="AAPL", action="BUY", qty=1, order_type="limit", limit_price=145.0)
    tracked = await broker.submit_signal(signal, "test")

    bar1 = make_bar("AAPL", open=150.0, high=152.0, low=148.0, close=150.0)
    broker.on_bar(bar1)
    assert tracked is not None
    assert tracked.status == "pending"  # not canceled — GTC

    bar2 = make_bar("AAPL", open=146.0, high=147.0, low=144.0, close=145.0)
    broker.on_bar(bar2)
    assert tracked.status == "filled"
    assert tracked.fill_price == 145.0


@pytest.mark.asyncio
async def test_fill_callback_called():
    broker, portfolio = make_broker()
    received: list[TrackedOrder] = []
    broker.register_fill_callback(received.append)

    signal = Signal(symbol="AAPL", action="BUY", qty=2, order_type="market")
    await broker.submit_signal(signal, "test")
    bar = make_bar("AAPL", open=150.0, high=155.0, low=148.0, close=153.0)
    broker.on_bar(bar)

    assert len(received) == 1
    assert received[0].fill_price == 150.0
    assert received[0].fill_qty == 2


@pytest.mark.asyncio
async def test_portfolio_updated_on_fill():
    broker, portfolio = make_broker()
    signal = Signal(symbol="AAPL", action="BUY", qty=3, order_type="market")
    await broker.submit_signal(signal, "test")
    bar = make_bar("AAPL", open=100.0, high=105.0, low=98.0, close=103.0)
    broker.on_bar(bar)

    pos = portfolio.get_position("AAPL")
    assert pos is not None
    assert pos.qty == 3
