"""Unit tests for BacktestMetrics calculations."""
import math
from datetime import datetime

import pytest

from src.backtest.metrics import BacktestMetrics
from src.portfolio.models import PortfolioSnapshot


def make_snapshots(values: list[float]) -> list[PortfolioSnapshot]:
    base = datetime(2024, 1, 1)
    from datetime import timedelta
    return [
        PortfolioSnapshot(
            timestamp=base + timedelta(days=i),
            positions={},
            cash=v,
            total_value=v,
        )
        for i, v in enumerate(values)
    ]


def test_total_return_pct():
    m = BacktestMetrics(make_snapshots([100, 110]))
    assert m.total_return_pct() == pytest.approx(10.0)


def test_total_return_flat():
    m = BacktestMetrics(make_snapshots([100, 100]))
    assert m.total_return_pct() == pytest.approx(0.0)


def test_max_drawdown():
    # Peak at 120, trough at 90 → -25%
    m = BacktestMetrics(make_snapshots([100, 120, 90, 110]))
    assert m.max_drawdown_pct() == pytest.approx(-25.0)


def test_max_drawdown_no_drawdown():
    m = BacktestMetrics(make_snapshots([100, 110, 120, 130]))
    assert m.max_drawdown_pct() == pytest.approx(0.0)


def test_win_rate():
    # returns: +10%, -5%, +10% → 2 wins out of 3 → 66.67%
    m = BacktestMetrics(make_snapshots([100, 110, 105, 115]))
    assert m.win_rate() == pytest.approx(200 / 3, rel=1e-3)


def test_sharpe_nan_on_one_snapshot():
    m = BacktestMetrics(make_snapshots([100]))
    assert math.isnan(m.sharpe_ratio())


def test_sharpe_nan_on_zero_std():
    # All returns == 0 → std == 0 → nan
    m = BacktestMetrics(make_snapshots([100, 100, 100, 100]))
    assert math.isnan(m.sharpe_ratio())


def test_sharpe_positive_trend():
    values = [100 * (1.001 ** i) for i in range(50)]
    m = BacktestMetrics(make_snapshots(values))
    assert m.sharpe_ratio() > 0


def test_sortino_nan_no_negative_returns():
    # All returns non-negative → fewer than 2 negative → nan
    m = BacktestMetrics(make_snapshots([100, 105, 110, 115]))
    assert math.isnan(m.sortino_ratio())
