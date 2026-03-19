from src.portfolio.models import PortfolioSnapshot


class PortfolioReporter:
    def __init__(self, snapshots: list[PortfolioSnapshot]):
        self._snapshots = snapshots

    def summary(self) -> dict:
        if len(self._snapshots) < 2:
            return {}

        starting_value = self._snapshots[0].total_value
        ending_value = self._snapshots[-1].total_value

        if starting_value == 0:
            total_return_pct = 0.0
        else:
            total_return_pct = (ending_value / starting_value - 1) * 100

        daily_returns = [
            self._snapshots[i].total_value / self._snapshots[i - 1].total_value - 1
            for i in range(1, len(self._snapshots))
            if self._snapshots[i - 1].total_value != 0
        ]

        # Max drawdown
        peak = self._snapshots[0].total_value
        max_drawdown_pct = 0.0
        for snap in self._snapshots[1:]:
            if snap.total_value > peak:
                peak = snap.total_value
            elif peak != 0:
                drawdown = (snap.total_value - peak) / peak * 100
                if drawdown < max_drawdown_pct:
                    max_drawdown_pct = drawdown

        return {
            "starting_value": starting_value,
            "ending_value": ending_value,
            "total_return_pct": total_return_pct,
            "daily_returns": daily_returns,
            "max_drawdown_pct": max_drawdown_pct,
        }

    def print_summary(self) -> None:
        if len(self._snapshots) < 2:
            print("no data (fewer than 2 snapshots)")
            return

        s = self.summary()
        print("--- Portfolio Summary ---")
        print(f"  Starting value : ${s['starting_value']:,.2f}")
        print(f"  Ending value   : ${s['ending_value']:,.2f}")
        print(f"  Total return   : {s['total_return_pct']:.2f}%")
        print(f"  Max drawdown   : {s['max_drawdown_pct']:.2f}%")
        print(f"  # of periods   : {len(s['daily_returns'])}")
