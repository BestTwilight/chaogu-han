from __future__ import annotations

import unittest

from stock_trainer.models import Order, OrderStatus, Side
from stock_trainer.simulator import TradingSimulator


class TradingEngineTest(unittest.TestCase):
    def test_generated_market_is_deterministic(self) -> None:
        first = TradingSimulator.with_generated_market(days=30, seed=3)
        second = TradingSimulator.with_generated_market(days=30, seed=3)
        self.assertEqual(first.current_price("TECH_A"), second.current_price("TECH_A"))
        first.step(12)
        second.step(12)
        self.assertEqual(first.current_price("CONSUMER_B"), second.current_price("CONSUMER_B"))

    def test_generated_market_supports_full_training_year(self) -> None:
        simulator = TradingSimulator.with_generated_market(days=260, seed=7)
        simulator.run_to_end()
        self.assertEqual(simulator.clock.index, 259)
        self.assertGreater(simulator.current_price("TECH_A"), 0)

    def test_buy_order_updates_cash_and_position(self) -> None:
        simulator = TradingSimulator.with_generated_market(days=30, seed=4, cash=100_000)
        order = Order(symbol="TECH_A", side=Side.BUY, quantity=1000)
        fill = simulator.submit_order(order)
        self.assertIsNotNone(fill)
        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(simulator.portfolio.positions["TECH_A"].quantity, 1000)
        self.assertLess(simulator.portfolio.cash, 100_000)

    def test_t_plus_one_blocks_same_day_sell(self) -> None:
        simulator = TradingSimulator.with_generated_market(days=30, seed=5, cash=100_000)
        simulator.submit_order(Order(symbol="TECH_A", side=Side.BUY, quantity=1000))
        sell = Order(symbol="TECH_A", side=Side.SELL, quantity=1000)
        fill = simulator.submit_order(sell)
        self.assertIsNone(fill)
        self.assertEqual(sell.status, OrderStatus.REJECTED)
        simulator.step(1)
        fill = simulator.submit_order(Order(symbol="TECH_A", side=Side.SELL, quantity=1000))
        self.assertIsNotNone(fill)

    def test_report_contains_coach_notes(self) -> None:
        simulator = TradingSimulator.with_generated_market(days=40, seed=6, cash=100_000)
        simulator.submit_order(Order(symbol="BANK_C", side=Side.BUY, quantity=2000))
        simulator.step(5)
        simulator.submit_order(Order(symbol="BANK_C", side=Side.SELL, quantity=1000))
        simulator.run_to_end()
        report = simulator.report()
        self.assertGreaterEqual(report.trade_count, 2)
        self.assertTrue(report.coach_notes)


if __name__ == "__main__":
    unittest.main()
