from __future__ import annotations

from dataclasses import asdict

from stock_trainer.models import Order, OrderType, Side
from stock_trainer.simulator import TradingSimulator

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - import guard for minimal installs
    raise RuntimeError("Install API dependencies with: pip install -e .[api]") from exc


app = FastAPI(title="Stock Trainer API", version="0.1.0")
simulator = TradingSimulator.with_generated_market()


class OrderRequest(BaseModel):
    symbol: str
    side: Side
    quantity: int = Field(gt=0)
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None


@app.get("/state")
def state() -> dict:
    return {
        "time": simulator.now.isoformat(),
        "candles": {symbol: asdict(candle) for symbol, candle in simulator.current_candles().items()},
        "account": asdict(simulator.snapshots[-1]),
        "positions": {symbol: asdict(position) for symbol, position in simulator.portfolio.positions.items()},
    }


@app.post("/step")
def step(bars: int = 1) -> dict:
    candles = simulator.step(bars)
    return {
        "time": simulator.now.isoformat(),
        "candles": {symbol: asdict(candle) for symbol, candle in candles.items()},
        "account": asdict(simulator.snapshots[-1]),
    }


@app.post("/orders")
def submit_order(request: OrderRequest) -> dict:
    try:
        order = Order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
        )
        fill = simulator.submit_order(order)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "order": asdict(order),
        "fill": asdict(fill) if fill else None,
        "account": asdict(simulator.snapshots[-1]),
    }


@app.get("/report")
def report() -> dict:
    return asdict(simulator.report())
