from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import uuid4


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    NEW = "new"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    REJECTED = "rejected"
    CANCELED = "canceled"


MarketRegime = Literal["bull", "bear", "range", "panic", "recovery"]


@dataclass(frozen=True)
class Candle:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    industry: str
    regime: MarketRegime
    event_label: str | None = None

    @property
    def intraday_range(self) -> float:
        return (self.high - self.low) / max(self.open, 0.01)


@dataclass
class Order:
    symbol: str
    side: Side
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime | None = None
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    message: str = ""


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: Side
    quantity: int
    price: float
    fee: float
    tax: float
    timestamp: datetime

    @property
    def cash_delta(self) -> float:
        gross = self.quantity * self.price
        if self.side is Side.BUY:
            return -(gross + self.fee)
        return gross - self.fee - self.tax


@dataclass
class Position:
    symbol: str
    quantity: int = 0
    sellable_quantity: int = 0
    avg_cost: float = 0.0

    def market_value(self, price: float) -> float:
        return self.quantity * price


@dataclass(frozen=True)
class AccountSnapshot:
    timestamp: datetime
    cash: float
    market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float
    max_drawdown: float
