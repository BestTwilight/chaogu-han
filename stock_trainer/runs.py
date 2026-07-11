from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from stock_trainer.simulator import TradingSimulator


def build_training_run_summary(
    simulator: TradingSimulator,
    mode: str,
    seed: int,
    message: str,
) -> dict[str, Any]:
    report = simulator.report()
    reviews = simulator.trade_reviews()
    first_snapshot = simulator.snapshots[0]
    last_snapshot = simulator.snapshots[-1]
    return {
        "id": uuid4().hex[:12],
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "seed": seed,
        "message": message,
        "start_time": first_snapshot.timestamp.date().isoformat(),
        "end_time": last_snapshot.timestamp.date().isoformat(),
        "bars_completed": simulator.clock.index + 1,
        "total_bars": len(simulator.clock.timeline),
        "start_equity": report.start_equity,
        "end_equity": report.end_equity,
        "total_return": report.total_return,
        "max_drawdown": report.max_drawdown,
        "trade_count": report.trade_count,
        "closed_trade_count": len(reviews),
        "win_rate": report.win_rate,
        "profit_factor": _safe_number(report.profit_factor),
        "coach_notes": report.coach_notes,
    }


def append_training_run(path: Path, run: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(run, ensure_ascii=False) + "\n")
    return run


def load_training_runs(path: Path, limit: int = 20) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    runs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            runs.append(json.loads(stripped))
    return runs[-limit:][::-1]


def save_training_run(
    path: Path,
    simulator: TradingSimulator,
    mode: str,
    seed: int,
    message: str,
) -> dict[str, Any]:
    run = build_training_run_summary(simulator, mode, seed, message)
    return append_training_run(path, run)


def _safe_number(value: Any) -> Any:
    if value == float("inf"):
        return "Infinity"
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
