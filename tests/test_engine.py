from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from stock_trainer.historical import create_blind_historical_market, load_historical_series
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

    def test_order_plan_is_preserved_on_fill(self) -> None:
        simulator = TradingSimulator.with_generated_market(days=30, seed=4, cash=100_000)
        order = Order(
            symbol="TECH_A",
            side=Side.BUY,
            quantity=1000,
            reason="放量突破",
            stop_loss=38.5,
            target_price=48.0,
            review_note="跌破前低离场",
        )
        fill = simulator.submit_order(order)
        self.assertIsNotNone(fill)
        self.assertEqual(fill.reason, "放量突破")
        self.assertEqual(fill.stop_loss, 38.5)
        self.assertEqual(fill.target_price, 48.0)
        self.assertEqual(fill.review_note, "跌破前低离场")

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

    def test_load_historical_csv_and_anonymize_symbols(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            self._write_csv(data_dir / "600000.csv", "600000", 12.0)
            self._write_csv(data_dir / "000001.csv", "000001", 9.0)
            series = load_historical_series(data_dir / "600000.csv")
            self.assertEqual(series.source_symbol, "600000")
            market = create_blind_historical_market(data_dir, days=10, seed=9, symbols_count=2)
            self.assertEqual(set(market.market_data), {"STOCK_A", "STOCK_B"})
            self.assertIn("STOCK_A", market.aliases)
            self.assertEqual(len(market.market_data["STOCK_A"]), 10)
            self.assertEqual(market.market_data["STOCK_A"][0].timestamp.date().isoformat(), "2020-01-02")

    def test_simulator_can_use_historical_market(self) -> None:
        with TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            self._write_csv(data_dir / "300000.csv", "300000", 20.0)
            simulator = TradingSimulator.with_historical_market(str(data_dir), days=15, seed=2, cash=50_000)
            self.assertEqual(list(simulator.market_data), ["STOCK_A"])
            self.assertGreater(simulator.current_price("STOCK_A"), 0)

    def test_snapshots_track_equity_curve(self) -> None:
        simulator = TradingSimulator.with_generated_market(days=20, seed=10, cash=100_000)
        simulator.step(3)
        simulator.submit_order(Order(symbol="TECH_A", side=Side.BUY, quantity=1000))
        simulator.step(2)
        self.assertGreaterEqual(len(simulator.snapshots), 4)
        self.assertTrue(all(snapshot.total_equity > 0 for snapshot in simulator.snapshots))

    def _write_csv(self, path: Path, symbol: str, start_price: float) -> None:
        lines = ["date,symbol,industry,open,high,low,close,volume"]
        for index in range(30):
            price = start_price + index * 0.15
            lines.append(
                f"2023-01-{index + 1:02d},{symbol},finance,{price:.2f},{price + 0.30:.2f},{price - 0.20:.2f},{price + 0.10:.2f},{1000000 + index}"
            )
        path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
