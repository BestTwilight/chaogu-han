from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from stock_trainer.analytics import TrainingReport, build_report
from stock_trainer.broker import BrokerConfig, MatchingEngine, Portfolio
from stock_trainer.clock import MarketClock
from stock_trainer.data import generate_training_market
from stock_trainer.historical import create_blind_historical_market
from stock_trainer.models import AccountSnapshot, Candle, Fill, Order


@dataclass
class TradingSimulator:
    market_data: dict[str, list[Candle]]
    portfolio: Portfolio = field(default_factory=Portfolio)
    broker_config: BrokerConfig = field(default_factory=BrokerConfig)

    def __post_init__(self) -> None:
        if not self.market_data:
            raise ValueError("market_data cannot be empty")
        lengths = {len(candles) for candles in self.market_data.values()}
        if len(lengths) != 1:
            raise ValueError("all symbols must share the same timeline length")
        first_symbol = next(iter(self.market_data))
        timeline = [candle.timestamp for candle in self.market_data[first_symbol]]
        self.clock = MarketClock(timeline)
        self.matching_engine = MatchingEngine(self.broker_config)
        self.snapshots: list[AccountSnapshot] = []
        self.equity_high_watermark = self.portfolio.cash
        self._capture_snapshot()

    @classmethod
    def with_generated_market(cls, days: int = 260, seed: int = 7, cash: float = 100_000.0) -> TradingSimulator:
        return cls(generate_training_market(days=days, seed=seed), portfolio=Portfolio(cash=cash))

    @classmethod
    def with_historical_market(
        cls,
        data_dir: str,
        days: int = 180,
        seed: int = 7,
        cash: float = 100_000.0,
        symbols_count: int = 5,
    ) -> TradingSimulator:
        market = create_blind_historical_market(
            data_dir=Path(data_dir),
            days=days,
            seed=seed,
            symbols_count=symbols_count,
        )
        return cls(market.market_data, portfolio=Portfolio(cash=cash))

    @property
    def now(self) -> datetime:
        return self.clock.now

    def current_candles(self) -> dict[str, Candle]:
        index = self.clock.index
        return {symbol: candles[index] for symbol, candles in self.market_data.items()}

    def current_price(self, symbol: str) -> float:
        return self.current_candles()[symbol].close

    def submit_order(self, order: Order) -> Fill | None:
        candle = self.current_candles().get(order.symbol)
        if candle is None:
            raise KeyError(f"unknown symbol: {order.symbol}")
        self.portfolio.begin_session(candle.timestamp.date())
        fill = self.matching_engine.execute(order, candle, self.portfolio)
        self._capture_snapshot()
        return fill

    def step(self, bars: int = 1) -> dict[str, Candle]:
        self.clock.step(bars)
        self.portfolio.begin_session(self.now.date())
        self._capture_snapshot()
        return self.current_candles()

    def run_to_end(self) -> None:
        while not self.clock.is_finished:
            self.step()

    def report(self) -> TrainingReport:
        return build_report(self.snapshots, self.portfolio.fills)

    def _capture_snapshot(self) -> AccountSnapshot:
        prices = self.current_candles()
        market_value = 0.0
        unrealized = 0.0
        for symbol, position in self.portfolio.positions.items():
            price = prices[symbol].close
            market_value += position.market_value(price)
            unrealized += (price - position.avg_cost) * position.quantity
        total_equity = self.portfolio.cash + market_value
        self.equity_high_watermark = max(self.equity_high_watermark, total_equity)
        drawdown = 1 - total_equity / self.equity_high_watermark if self.equity_high_watermark else 0.0
        snapshot = AccountSnapshot(
            timestamp=self.now,
            cash=round(self.portfolio.cash, 2),
            market_value=round(market_value, 2),
            total_equity=round(total_equity, 2),
            realized_pnl=round(self.portfolio.realized_pnl, 2),
            unrealized_pnl=round(unrealized, 2),
            max_drawdown=round(drawdown, 6),
        )
        self.snapshots.append(snapshot)
        return snapshot
