from __future__ import annotations

from dataclasses import dataclass

from stock_trainer.models import AccountSnapshot, Candle, Fill, Side


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


@dataclass(frozen=True)
class TradeReview:
    id: str
    symbol: str
    quantity: int
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    pnl: float
    return_rate: float
    holding_bars: int
    max_favorable_return: float
    max_adverse_return: float
    planned_stop_hit: bool
    planned_target_hit: bool
    reason: str
    stop_loss: float | None
    target_price: float | None
    review_note: str


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


def build_trade_reviews(fills: list[Fill], market_data: dict[str, list[Candle]]) -> list[TradeReview]:
    inventory: dict[str, list[tuple[Fill, int]]] = {}
    reviews: list[TradeReview] = []
    review_index = 1
    for fill in fills:
        if fill.side is Side.BUY:
            inventory.setdefault(fill.symbol, []).append((fill, fill.quantity))
            continue
        remaining = fill.quantity
        lots = inventory.setdefault(fill.symbol, [])
        while remaining > 0 and lots:
            entry_fill, entry_remaining = lots[0]
            matched = min(entry_remaining, remaining)
            reviews.append(_build_trade_review(review_index, entry_fill, fill, matched, market_data[fill.symbol]))
            review_index += 1
            remaining -= matched
            if matched == entry_remaining:
                lots.pop(0)
            else:
                lots[0] = (entry_fill, entry_remaining - matched)
    return reviews


def _build_trade_review(
    review_index: int,
    entry_fill: Fill,
    exit_fill: Fill,
    quantity: int,
    candles: list[Candle],
) -> TradeReview:
    entry_cost = entry_fill.price + entry_fill.fee / entry_fill.quantity
    exit_proceeds = exit_fill.price - (exit_fill.fee + exit_fill.tax) / exit_fill.quantity
    pnl = (exit_proceeds - entry_cost) * quantity
    segment = [
        candle
        for candle in candles
        if entry_fill.timestamp <= candle.timestamp <= exit_fill.timestamp
    ]
    if not segment:
        segment = [candle for candle in candles if candle.timestamp == exit_fill.timestamp]
    max_high = max((candle.high for candle in segment), default=exit_fill.price)
    min_low = min((candle.low for candle in segment), default=exit_fill.price)
    stop_hit = entry_fill.stop_loss is not None and min_low <= entry_fill.stop_loss
    target_hit = entry_fill.target_price is not None and max_high >= entry_fill.target_price
    return TradeReview(
        id=f"T{review_index:03d}",
        symbol=entry_fill.symbol,
        quantity=quantity,
        entry_time=entry_fill.timestamp.date().isoformat(),
        exit_time=exit_fill.timestamp.date().isoformat(),
        entry_price=round(entry_fill.price, 2),
        exit_price=round(exit_fill.price, 2),
        pnl=round(pnl, 2),
        return_rate=round(pnl / max(entry_cost * quantity, 0.01), 4),
        holding_bars=max(0, len(segment) - 1),
        max_favorable_return=round(max_high / entry_fill.price - 1, 4),
        max_adverse_return=round(min_low / entry_fill.price - 1, 4),
        planned_stop_hit=stop_hit,
        planned_target_hit=target_hit,
        reason=entry_fill.reason,
        stop_loss=entry_fill.stop_loss,
        target_price=entry_fill.target_price,
        review_note=entry_fill.review_note,
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
