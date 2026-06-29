from __future__ import annotations

from dataclasses import dataclass

from stock_trainer.models import AccountSnapshot, Fill, Side


@dataclass(frozen=True)
class TrainingReport:
    start_equity: float
    end_equity: float
    total_return: float
    max_drawdown: float
    trade_count: int
    win_rate: float
    profit_factor: float
    coach_notes: list[str]


def build_report(snapshots: list[AccountSnapshot], fills: list[Fill]) -> TrainingReport:
    if not snapshots:
        raise ValueError("no snapshots to report")
    start_equity = snapshots[0].total_equity
    end_equity = snapshots[-1].total_equity
    closed_trades = _pair_buy_sell_pnl(fills)
    wins = [pnl for pnl in closed_trades if pnl > 0]
    losses = [pnl for pnl in closed_trades if pnl < 0]
    profit_factor = sum(wins) / abs(sum(losses)) if losses else float("inf")
    win_rate = len(wins) / len(closed_trades) if closed_trades else 0.0
    notes = _coach_notes(snapshots, fills, win_rate, profit_factor)
    return TrainingReport(
        start_equity=round(start_equity, 2),
        end_equity=round(end_equity, 2),
        total_return=round(end_equity / start_equity - 1, 4),
        max_drawdown=round(max(snapshot.max_drawdown for snapshot in snapshots), 4),
        trade_count=len(fills),
        win_rate=round(win_rate, 4),
        profit_factor=round(profit_factor, 4) if profit_factor != float("inf") else profit_factor,
        coach_notes=notes,
    )


def _pair_buy_sell_pnl(fills: list[Fill]) -> list[float]:
    inventory: dict[str, list[tuple[int, float]]] = {}
    closed: list[float] = []
    for fill in fills:
        if fill.side is Side.BUY:
            inventory.setdefault(fill.symbol, []).append((fill.quantity, fill.price + fill.fee / fill.quantity))
            continue
        remaining = fill.quantity
        proceeds_price = fill.price - (fill.fee + fill.tax) / fill.quantity
        lots = inventory.setdefault(fill.symbol, [])
        while remaining > 0 and lots:
            quantity, cost = lots[0]
            matched = min(quantity, remaining)
            closed.append((proceeds_price - cost) * matched)
            remaining -= matched
            if matched == quantity:
                lots.pop(0)
            else:
                lots[0] = (quantity - matched, cost)
    return closed


def _coach_notes(
    snapshots: list[AccountSnapshot],
    fills: list[Fill],
    win_rate: float,
    profit_factor: float,
) -> list[str]:
    notes: list[str] = []
    max_drawdown = max(snapshot.max_drawdown for snapshot in snapshots)
    if max_drawdown > 0.12:
        notes.append("最大回撤偏高，下一轮训练建议降低单笔仓位或更早执行止损。")
    if len(fills) > max(8, len(snapshots) // 4):
        notes.append("交易频率较高，复盘时重点检查是否在震荡阶段过度交易。")
    if fills and win_rate < 0.4 and profit_factor < 1:
        notes.append("胜率和盈亏比同时偏弱，先收窄交易条件，避免为了参与而参与。")
    if fills and profit_factor > 1.5:
        notes.append("盈亏比表现不错，可以继续观察收益是否集中在少数大单。")
    if not fills:
        notes.append("本轮没有成交，适合用来练习等待，但还需要主动验证交易计划。")
    return notes or ["本轮交易结构比较均衡，建议继续复盘入场理由和离场执行。"]
