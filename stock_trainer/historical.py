from __future__ import annotations

from csv import DictReader
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from random import Random

from stock_trainer.models import Candle, MarketRegime


REQUIRED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


class HistoricalDataError(ValueError):
    pass


@dataclass(frozen=True)
class HistoricalSeries:
    source_symbol: str
    industry: str
    candles: list[Candle]


@dataclass(frozen=True)
class BlindHistoricalMarket:
    market_data: dict[str, list[Candle]]
    aliases: dict[str, str]
    source_ranges: dict[str, tuple[str, str]]


def list_historical_csvs(data_dir: Path) -> list[Path]:
    if not data_dir.exists():
        return []
    return sorted(path for path in data_dir.glob("*.csv") if path.is_file())


def load_historical_series(path: Path) -> HistoricalSeries:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise HistoricalDataError(f"{path.name} 缺少字段: {', '.join(sorted(missing))}")
        rows = list(reader)

    candles: list[Candle] = []
    source_symbol = path.stem
    industry = "historical"
    previous_close: float | None = None
    for row_number, row in enumerate(rows, start=2):
        try:
            timestamp = _parse_date(row["date"])
            open_price = float(row["open"])
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
            volume = int(float(row["volume"]))
        except (TypeError, ValueError) as exc:
            raise HistoricalDataError(f"{path.name} 第 {row_number} 行数据无法解析") from exc
        if min(open_price, high, low, close) <= 0 or volume < 0:
            raise HistoricalDataError(f"{path.name} 第 {row_number} 行价格或成交量非法")
        if low > min(open_price, close) or high < max(open_price, close):
            raise HistoricalDataError(f"{path.name} 第 {row_number} 行 high/low 与开收盘不一致")
        source_symbol = row.get("symbol") or source_symbol
        industry = row.get("industry") or industry
        regime = _infer_regime(close, previous_close)
        previous_close = close
        candles.append(
            Candle(
                symbol=source_symbol,
                timestamp=timestamp,
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=volume,
                industry=industry,
                regime=regime,
            )
        )

    candles.sort(key=lambda candle: candle.timestamp)
    if len(candles) < 2:
        raise HistoricalDataError(f"{path.name} 至少需要 2 行行情")
    return HistoricalSeries(source_symbol=source_symbol, industry=industry, candles=candles)


def create_blind_historical_market(
    data_dir: Path,
    days: int = 180,
    seed: int = 7,
    symbols_count: int = 5,
) -> BlindHistoricalMarket:
    rng = Random(seed)
    paths = list_historical_csvs(data_dir)
    if not paths:
        raise HistoricalDataError(f"没有找到历史行情 CSV，请放入 {data_dir}")

    series = [load_historical_series(path) for path in paths]
    eligible = [item for item in series if len(item.candles) >= days]
    if not eligible:
        raise HistoricalDataError(f"没有长度达到 {days} 根 K 线的历史行情 CSV")

    rng.shuffle(eligible)
    selected = eligible[: max(1, min(symbols_count, len(eligible)))]
    virtual_dates = _trading_days(datetime(2020, 1, 2, 15, 0), days)
    market_data: dict[str, list[Candle]] = {}
    aliases: dict[str, str] = {}
    source_ranges: dict[str, tuple[str, str]] = {}

    for index, item in enumerate(selected):
        alias = f"STOCK_{chr(ord('A') + index)}"
        start = rng.randint(0, len(item.candles) - days)
        segment = item.candles[start : start + days]
        market_data[alias] = [
            Candle(
                symbol=alias,
                timestamp=virtual_dates[offset],
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                industry=item.industry,
                regime=candle.regime,
                event_label=None,
            )
            for offset, candle in enumerate(segment)
        ]
        aliases[alias] = item.source_symbol
        source_ranges[alias] = (segment[0].timestamp.date().isoformat(), segment[-1].timestamp.date().isoformat())

    return BlindHistoricalMarket(market_data=market_data, aliases=aliases, source_ranges=source_ranges)


def _parse_date(value: str) -> datetime:
    value = value.strip()
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            parsed = datetime.strptime(value, pattern)
            return parsed.replace(hour=15)
        except ValueError:
            continue
    raise ValueError(f"unsupported date: {value}")


def _infer_regime(close: float, previous_close: float | None) -> MarketRegime:
    if previous_close is None:
        return "historical"
    change = close / previous_close - 1
    if change <= -0.055:
        return "panic"
    if change >= 0.035:
        return "bull"
    if change <= -0.025:
        return "bear"
    if change >= 0.018:
        return "recovery"
    return "range"


def _trading_days(start: datetime, days: int) -> list[datetime]:
    result: list[datetime] = []
    cursor = start
    while len(result) < days:
        if cursor.weekday() < 5:
            result.append(cursor)
        cursor += timedelta(days=1)
    return result
