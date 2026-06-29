from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_trainer.models import Order, Side
from stock_trainer.simulator import TradingSimulator


def main() -> None:
    simulator = TradingSimulator.with_generated_market(days=90, seed=11, cash=100_000)
    print(f"start: {simulator.now.date()} equity={simulator.snapshots[-1].total_equity}")
    print("symbols:", ", ".join(simulator.current_candles()))

    simulator.step(5)
    fill = simulator.submit_order(Order(symbol="TECH_A", side=Side.BUY, quantity=1000))
    print("buy:", asdict(fill) if fill else "not filled")

    simulator.step(20)
    fill = simulator.submit_order(Order(symbol="TECH_A", side=Side.SELL, quantity=500))
    print("sell:", asdict(fill) if fill else "not filled")

    simulator.run_to_end()
    report = simulator.report()
    print("report:", asdict(report))


if __name__ == "__main__":
    main()
