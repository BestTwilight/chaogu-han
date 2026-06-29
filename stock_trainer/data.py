from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import exp
from random import Random

from stock_trainer.models import Candle, MarketRegime


@dataclass(frozen=True)
class SymbolProfile:
    symbol: str
    industry: str
    start_price: float
    beta: float
    idiosyncratic_vol: float
    liquidity: int


DEFAULT_SYMBOLS = [
    SymbolProfile("TECH_A", "technology", 42.0, 1.25, 0.020, 2_400_000),
    SymbolProfile("CONSUMER_B", "consumer", 68.0, 0.85, 0.014, 1_500_000),
    SymbolProfile("BANK_C", "finance", 9.8, 0.55, 0.008, 6_800_000),
    SymbolProfile("ENERGY_D", "energy", 23.5, 1.05, 0.018, 2_000_000),
    SymbolProfile("MEDICAL_E", "healthcare", 51.0, 0.95, 0.017, 1_200_000),
]


REGIME_SCHEDULE: list[tuple[int, MarketRegime]] = [
    (0, "range"),
    (40, "bull"),
    (95, "panic"),
    (115, "recovery"),
    (155, "bear"),
    (205, "range"),
]


REGIME_DRIFT = {
    "bull": 0.0016,
    "bear": -0.0011,
    "range": 0.0001,
    "panic": -0.0032,
    "recovery": 0.0019,
}


REGIME_VOL = {
    "bull": 0.009,
    "bear": 0.014,
    "range": 0.007,
    "panic": 0.028,
    "recovery": 0.017,
}


def generate_training_market(
    days: int = 260,
    seed: int = 7,
    start: datetime | None = None,
    symbols: list[SymbolProfile] | None = None,
) -> dict[str, list[Candle]]:
    """Generate deterministic market data with regimes, sector linkage and events.

    This is not a substitute for historical data. It is a local scenario engine
    that gives the simulator economic structure before a data vendor is wired in.
    """

    rng = Random(seed)
    profiles = list(symbols or DEFAULT_SYMBOLS)
    industries = sorted({profile.industry for profile in profiles})
    current = start or datetime(2020, 1, 2, 15, 0)
    dates = _trading_days(current, days)
    prices = {profile.symbol: profile.start_price for profile in profiles}
    vol_state = REGIME_VOL["range"]
    industry_momentum: dict[str, float] = {}
    candles: dict[str, list[Candle]] = {profile.symbol: [] for profile in profiles}

    for day_index, timestamp in enumerate(dates):
        regime = _regime_for(day_index)
        market_shock = rng.gauss(REGIME_DRIFT[regime], vol_state)
        vol_state = _clamp(0.88 * vol_state + 0.12 * (abs(market_shock) * 1.8 + REGIME_VOL[regime]), 0.004, 0.060)

        for industry in industries:
            previous = industry_momentum.get(industry, 0.0)
            industry_momentum[industry] = _clamp(0.72 * previous + rng.gauss(0.0, vol_state * 0.45), -0.045, 0.045)

        for profile in profiles:
            event_return, event_label = _event_for(rng, regime, day_index, profile)
            mean_reversion = _valuation_pressure(prices[profile.symbol], profile.start_price)
            stock_noise = _clamp(rng.gauss(0.0, profile.idiosyncratic_vol + vol_state * 0.35), -0.075, 0.075)
            daily_return = (
                profile.beta * market_shock
                + industry_momentum[profile.industry]
                + stock_noise
                + event_return
                + mean_reversion
            )
            limited_return = max(min(daily_return, 0.098), -0.098)
            open_gap = _clamp(rng.gauss(limited_return * 0.25, vol_state * 0.28), -0.065, 0.065)
            open_price = max(0.5, prices[profile.symbol] * exp(open_gap))
            close_price = max(0.5, prices[profile.symbol] * exp(limited_return))
            range_width = _clamp(abs(rng.gauss(vol_state * 1.8, vol_state * 0.6)) + abs(limited_return) * 0.8, 0.006, 0.190)
            high = max(open_price, close_price) * (1 + range_width * rng.uniform(0.25, 0.85))
            low = min(open_price, close_price) * (1 - range_width * rng.uniform(0.20, 0.75))
            low = max(0.5, low)
            volume_multiplier = 1 + min(5.0, abs(limited_return) * 18 + abs(event_return) * 22)
            volume = int(profile.liquidity * volume_multiplier * rng.uniform(0.75, 1.35))

            candle = Candle(
                symbol=profile.symbol,
                timestamp=timestamp,
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close_price, 2),
                volume=max(100, volume),
                industry=profile.industry,
                regime=regime,
                event_label=event_label,
            )
            candles[profile.symbol].append(candle)
            prices[profile.symbol] = close_price

    return candles


def _trading_days(start: datetime, days: int) -> list[datetime]:
    result: list[datetime] = []
    cursor = start
    while len(result) < days:
        if cursor.weekday() < 5:
            result.append(cursor)
        cursor += timedelta(days=1)
    return result


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _regime_for(day_index: int) -> MarketRegime:
    active = REGIME_SCHEDULE[0][1]
    for start_day, regime in REGIME_SCHEDULE:
        if day_index >= start_day:
            active = regime
    return active


def _valuation_pressure(price: float, anchor: float) -> float:
    relative = price / anchor
    if relative > 1.8:
        return -0.0015 * (relative - 1.8)
    if relative < 0.55:
        return 0.0018 * (0.55 - relative)
    return 0.0


def _event_for(
    rng: Random,
    regime: MarketRegime,
    day_index: int,
    profile: SymbolProfile,
) -> tuple[float, str | None]:
    if day_index < 10:
        return 0.0, None
    probability = 0.020 if regime != "panic" else 0.045
    if rng.random() > probability:
        return 0.0, None
    labels = [
        ("earnings_beat", 0.045),
        ("earnings_miss", -0.052),
        ("policy_tailwind", 0.032),
        ("shareholder_sale", -0.030),
        ("sector_news", 0.024),
    ]
    label, base = rng.choice(labels)
    industry_tilt = 1.25 if profile.industry in {"technology", "energy"} else 0.9
    return base * industry_tilt * rng.uniform(0.75, 1.35), label
