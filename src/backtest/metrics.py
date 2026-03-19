import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.portfolio.models import PortfolioSnapshot


class BacktestMetrics:
    def __init__(
        self,
        snapshots: "list[PortfolioSnapshot]",
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ):
        self._snapshots = snapshots
        self._rfr = risk_free_rate
        self._ppy = periods_per_year

    def _returns(self) -> list[float]:
        values = [s.total_value for s in self._snapshots]
        if len(values) < 2:
            return []
        return [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values))]

    def sharpe_ratio(self) -> float:
        returns = self._returns()
        if len(returns) < 2:
            return float("nan")
        excess = [r - self._rfr / self._ppy for r in returns]
        mean = sum(excess) / len(excess)
        variance = sum((r - mean) ** 2 for r in excess) / (len(excess) - 1)
        std = math.sqrt(variance)
        if std == 0:
            return float("nan")
        return mean / std * math.sqrt(self._ppy)

    def sortino_ratio(self) -> float:
        returns = self._returns()
        if len(returns) < 2:
            return float("nan")
        excess = [r - self._rfr / self._ppy for r in returns]
        mean = sum(excess) / len(excess)
        negatives = [r for r in excess if r < 0]
        if len(negatives) < 2:
            return float("nan")
        down_var = sum(r ** 2 for r in negatives) / (len(negatives) - 1)
        down_std = math.sqrt(down_var)
        if down_std == 0:
            return float("nan")
        return mean / down_std * math.sqrt(self._ppy)

    def max_drawdown_pct(self) -> float:
        if not self._snapshots:
            return 0.0
        peak = self._snapshots[0].total_value
        max_dd = 0.0
        for snap in self._snapshots:
            if snap.total_value > peak:
                peak = snap.total_value
            if peak > 0:
                dd = (snap.total_value - peak) / peak * 100
                if dd < max_dd:
                    max_dd = dd
        return max_dd

    def total_return_pct(self) -> float:
        if len(self._snapshots) < 2:
            return 0.0
        first = self._snapshots[0].total_value
        last = self._snapshots[-1].total_value
        if first == 0:
            return 0.0
        return (last - first) / first * 100

    def win_rate(self) -> float:
        returns = self._returns()
        if not returns:
            return 0.0
        wins = sum(1 for r in returns if r > 0)
        return wins / len(returns) * 100

    def summary(self) -> dict:
        return {
            "total_return_pct": self.total_return_pct(),
            "sharpe": self.sharpe_ratio(),
            "sortino": self.sortino_ratio(),
            "max_drawdown_pct": self.max_drawdown_pct(),
            "win_rate": self.win_rate(),
            "n_snapshots": len(self._snapshots),
        }

    def print_summary(self) -> None:
        s = self.summary()

        def fmt_float(v: float) -> str:
            if math.isnan(v):
                return "N/A"
            return f"{v:.4f}"

        print("--- Backtest Metrics ---")
        print(f"  Total return  : {s['total_return_pct']:.2f}%")
        print(f"  Sharpe ratio  : {fmt_float(s['sharpe'])}")
        print(f"  Sortino ratio : {fmt_float(s['sortino'])}")
        print(f"  Max drawdown  : {s['max_drawdown_pct']:.2f}%")
        print(f"  Win rate      : {s['win_rate']:.2f}%")
        print(f"  Snapshots     : {s['n_snapshots']}")
