from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
import argparse
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from stock_trainer.models import Order, OrderType, Side
from stock_trainer.simulator import TradingSimulator
from stock_trainer.historical import HistoricalDataError, list_historical_csvs


DATA_DIR = ROOT / "data" / "historical"
session_mode = "generated"
session_seed = 7
session_message = "结构化模拟行情"
simulator = TradingSimulator.with_generated_market(days=260, seed=session_seed, cash=100_000)


class TrainerHandler(SimpleHTTPRequestHandler):
    server_version = "StockTrainer/0.1"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            symbol = parse_qs(parsed.query).get("symbol", [None])[0]
            self._send_json(_state_payload(symbol))
            return
        if parsed.path == "/api/report":
            self._send_json(simulator.report())
            return
        if parsed.path == "/api/datasets":
            self._send_json(_datasets_payload())
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        global simulator
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/step":
                bars = int(payload.get("bars", 1))
                simulator.step(max(1, bars))
                self._send_json(_state_payload(payload.get("symbol")))
                return
            if parsed.path == "/api/orders":
                order = Order(
                    symbol=str(payload["symbol"]),
                    side=Side(str(payload["side"])),
                    quantity=int(payload["quantity"]),
                    order_type=OrderType(str(payload.get("order_type", "market"))),
                    limit_price=_optional_float(payload.get("limit_price")),
                    reason=str(payload.get("reason", "")).strip(),
                    stop_loss=_optional_float(payload.get("stop_loss")),
                    target_price=_optional_float(payload.get("target_price")),
                    review_note=str(payload.get("review_note", "")).strip(),
                )
                fill = simulator.submit_order(order)
                self._send_json(
                    {
                        "order": order,
                        "fill": fill,
                        "state": _state_payload(order.symbol),
                    }
                )
                return
            if parsed.path == "/api/reset":
                _reset_simulator(payload)
                self._send_json(_state_payload(payload.get("symbol")))
                return
        except (HistoricalDataError, KeyError, ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json({"error": "unknown route"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_json(self, payload: Any, status: int = 200) -> None:
        encoded = json.dumps(_json_safe(payload), ensure_ascii=False, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _state_payload(selected_symbol: str | None = None) -> dict[str, Any]:
    symbols = list(simulator.market_data)
    symbol = selected_symbol if selected_symbol in simulator.market_data else symbols[0]
    index = simulator.clock.index
    current_candles = simulator.current_candles()
    positions = {}
    for item_symbol, position in simulator.portfolio.positions.items():
        price = current_candles[item_symbol].close
        positions[item_symbol] = {
            **asdict(position),
            "last_price": price,
            "market_value": round(position.quantity * price, 2),
            "unrealized_pnl": round((price - position.avg_cost) * position.quantity, 2),
        }
    return {
        "symbols": symbols,
        "selected_symbol": symbol,
        "time": simulator.now,
        "index": index,
        "total_bars": len(simulator.clock.timeline),
        "is_finished": simulator.clock.is_finished,
        "mode": session_mode,
        "seed": session_seed,
        "message": session_message,
        "candles": simulator.market_data[symbol][: index + 1],
        "current_candles": current_candles,
        "account": simulator.snapshots[-1],
        "snapshots": simulator.snapshots,
        "positions": positions,
        "fills": simulator.portfolio.fills,
        "trade_reviews": simulator.trade_reviews(),
    }


def _datasets_payload() -> dict[str, Any]:
    csvs = list_historical_csvs(DATA_DIR)
    return {
        "historical_available": bool(csvs),
        "historical_count": len(csvs),
        "data_dir": str(DATA_DIR),
        "files": [path.name for path in csvs],
    }


def _reset_simulator(payload: dict[str, Any]) -> None:
    global simulator, session_mode, session_seed, session_message
    mode = str(payload.get("mode", "generated"))
    days = int(payload.get("days", 260 if mode == "generated" else 180))
    seed = int(payload.get("seed", 7))
    cash = float(payload.get("cash", 100_000))
    if mode == "historical":
        simulator = TradingSimulator.with_historical_market(
            data_dir=str(DATA_DIR),
            days=days,
            seed=seed,
            cash=cash,
            symbols_count=int(payload.get("symbols_count", 5)),
        )
        session_mode = "historical"
        session_message = "历史盲测：真实日期和股票代码已隐藏"
    else:
        simulator = TradingSimulator.with_generated_market(days=days, seed=seed, cash=cash)
        session_mode = "generated"
        session_message = "结构化模拟行情"
    session_seed = seed


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"{value!r} is not JSON serializable")


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the local stock training web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="Open the app in the default browser.")
    args = parser.parse_args()

    host = args.host
    port = args.port
    httpd = ThreadingHTTPServer((host, port), TrainerHandler)
    url = f"http://{host}:{port}"
    print(f"Stock Trainer running at {url}")
    print("Press Ctrl+C to stop.")
    if args.open:
        webbrowser.open(url)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
