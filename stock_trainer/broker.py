from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from stock_trainer.models import Candle, Fill, Order, OrderStatus, OrderType, Position, Side


@dataclass(frozen=True)
class BrokerConfig:
    commission_rate: float = 0.00025
    min_commission: float = 5.0
    sell_tax_rate: float = 0.0005
    slippage_rate: float = 0.0008
    max_participation_rate: float = 0.08
    lot_size: int = 100
    t_plus_one: bool = True


@dataclass
class Portfolio:
    cash: float = 100_000.0
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    fills: list[Fill] = field(default_factory=list)
    _last_session_date: date | None = None

    def begin_session(self, session_date: date) -> None:
        if self._last_session_date == session_date:
            return
        for position in self.positions.values():
            position.sellable_quantity = position.quantity
        self._last_session_date = session_date

    def position_for(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def apply_fill(self, fill: Fill, config: BrokerConfig) -> None:
        position = self.position_for(fill.symbol)
        self.cash += fill.cash_delta
        if fill.side is Side.BUY:
            previous_cost = position.avg_cost * position.quantity
            added_cost = fill.quantity * fill.price + fill.fee
            position.quantity += fill.quantity
            if not config.t_plus_one:
                position.sellable_quantity += fill.quantity
            position.avg_cost = (previous_cost + added_cost) / max(position.quantity, 1)
        else:
            pnl = (fill.price - position.avg_cost) * fill.quantity - fill.fee - fill.tax
            self.realized_pnl += pnl
            position.quantity -= fill.quantity
            position.sellable_quantity -= fill.quantity
            if position.quantity <= 0:
                position.quantity = 0
                position.sellable_quantity = 0
                position.avg_cost = 0.0
        self.fills.append(fill)


class MatchingEngine:
    def __init__(self, config: BrokerConfig | None = None):
        self.config = config or BrokerConfig()

    def execute(self, order: Order, candle: Candle, portfolio: Portfolio) -> Fill | None:
        order.created_at = order.created_at or candle.timestamp
        if order.quantity <= 0:
            return self._reject(order, "quantity must be positive")
        if order.quantity % self.config.lot_size != 0:
            return self._reject(order, f"quantity must be a multiple of {self.config.lot_size}")
        if order.symbol != candle.symbol:
            return self._reject(order, "order symbol does not match candle")

        fill_price = self._fill_price(order, candle)
        if fill_price is None:
            order.status = OrderStatus.NEW
            order.message = "limit price not reached"
            return None

        max_quantity = max(self.config.lot_size, int(candle.volume * self.config.max_participation_rate))
        fill_quantity = min(order.quantity, max_quantity - (max_quantity % self.config.lot_size))
        if order.side is Side.SELL:
            position = portfolio.position_for(order.symbol)
            available = position.sellable_quantity if self.config.t_plus_one else position.quantity
            fill_quantity = min(fill_quantity, available - (available % self.config.lot_size))
            if fill_quantity <= 0:
                return self._reject(order, "no sellable shares available")

        fee = self._commission(fill_price, fill_quantity)
        tax = self._tax(order.side, fill_price, fill_quantity)
        if order.side is Side.BUY:
            affordable = self._affordable_quantity(portfolio.cash, fill_price)
            fill_quantity = min(fill_quantity, affordable)
            if fill_quantity <= 0:
                return self._reject(order, "insufficient cash")
            fee = self._commission(fill_price, fill_quantity)
            tax = 0.0

        fill = Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=fill_quantity,
            price=round(fill_price, 2),
            fee=round(fee, 2),
            tax=round(tax, 2),
            timestamp=candle.timestamp,
            reason=order.reason.strip(),
            stop_loss=order.stop_loss,
            target_price=order.target_price,
            review_note=order.review_note.strip(),
        )
        portfolio.apply_fill(fill, self.config)
        order.filled_quantity += fill.quantity
        order.avg_fill_price = fill.price
        order.status = OrderStatus.FILLED if fill.quantity == order.quantity else OrderStatus.PARTIALLY_FILLED
        order.message = "filled"
        return fill

    def _fill_price(self, order: Order, candle: Candle) -> float | None:
        if order.order_type is OrderType.LIMIT:
            if order.limit_price is None:
                order.status = OrderStatus.REJECTED
                order.message = "limit order requires limit_price"
                return None
            if order.side is Side.BUY and candle.low > order.limit_price:
                return None
            if order.side is Side.SELL and candle.high < order.limit_price:
                return None
            anchor = min(order.limit_price, candle.close) if order.side is Side.BUY else max(order.limit_price, candle.close)
        else:
            anchor = candle.close
        direction = 1 if order.side is Side.BUY else -1
        return max(0.01, anchor * (1 + direction * self.config.slippage_rate))

    def _commission(self, price: float, quantity: int) -> float:
        return max(self.config.min_commission, price * quantity * self.config.commission_rate)

    def _tax(self, side: Side, price: float, quantity: int) -> float:
        if side is Side.SELL:
            return price * quantity * self.config.sell_tax_rate
        return 0.0

    def _affordable_quantity(self, cash: float, price: float) -> int:
        effective_price = price * (1 + self.config.commission_rate)
        lots = int(cash / (effective_price * self.config.lot_size))
        return lots * self.config.lot_size

    def _reject(self, order: Order, message: str) -> None:
        order.status = OrderStatus.REJECTED
        order.message = message
        return None
