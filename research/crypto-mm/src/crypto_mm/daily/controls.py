"""Fixed policy and exposure controls, separate from the legacy simulations."""

import math
from datetime import date
from statistics import stdev

from .ablation import build_targets, evaluate_ablation
from .study_accounting import validate_prices, account_periods, summarize

LEGACY = {
    "ew_legacy": ("equal_weight", "baseline"),
    "trend200_legacy": ("trend_200d", "baseline"),
    "trend200_vol40_legacy": ("trend_200d", "vol_target_40pct"),
    "trend200_fixed60_legacy": ("trend_200d", "fixed_exposure_60pct"),
}
STRICT = {
    "trend200_vol40_strict",
    "ew_fixed60",
    "ew_vol40_strict",
    "ew_trend_gross_matched",
}


def _selected(closes, products, decision):
    selected = []
    for product in products:
        average = sum(closes[product][decision - 199 : decision + 1]) / 200
        if not math.isfinite(average):
            raise ValueError("INVALID_CONTROL_TREND_AVERAGE")
        if closes[product][decision] > average:
            selected.append(product)
    return selected


def _strict_targets(bars, *, trend):
    closes = bars["close"]
    products = sorted(closes)
    targets, zero = [], 0
    for decision in range(251, len(bars["dates"]) - 1):
        selected = _selected(closes, products, decision) if trend else products
        if not selected:
            targets.append({})
            continue
        returns = [
            sum(closes[p][j] / closes[p][j - 1] - 1 for p in selected) / len(selected)
            for j in range(decision - 19, decision + 1)
        ]
        if not all(math.isfinite(r) for r in returns):
            raise ValueError("INVALID_CONTROL_VOLATILITY")
        volatility = stdev(returns) * math.sqrt(365)
        if not math.isfinite(volatility):
            raise ValueError("INVALID_CONTROL_VOLATILITY")
        if volatility == 0:
            zero += 1
            targets.append({})
        else:
            scale = min(1.0, 0.40 / volatility)
            targets.append({p: scale / len(selected) for p in selected})
    return targets, zero


def build_control_targets(bars: dict, arm_id: str) -> dict:
    if arm_id not in LEGACY and arm_id not in STRICT:
        raise ValueError("UNKNOWN_CRYPTO_CONTROL")
    validate_prices(bars)
    dates, closes = bars["dates"], bars["close"]
    if len(dates) < 253 or len(closes) > 20:
        raise ValueError("INVALID_CONTROLS_HISTORY_OR_POOL")
    if any(
        (date.fromisoformat(b) - date.fromisoformat(a)).days != 1
        for a, b in zip(dates, dates[1:])
    ):
        raise ValueError("INCOMPLETE_CONTROL_GRID")
    products = sorted(closes)
    diagnostics = {"zero_volatility_decisions": 0}
    if arm_id in {"trend200_vol40_legacy", "trend200_fixed60_legacy"}:
        strategy, variant = LEGACY[arm_id]
        return build_targets(bars, strategy, variant) | {"diagnostics": diagnostics}
    if arm_id in {"trend200_vol40_strict", "ew_vol40_strict", "ew_trend_gross_matched"}:
        targets, zero = _strict_targets(bars, trend=arm_id != "ew_vol40_strict")
        diagnostics["zero_volatility_decisions"] = zero
        if arm_id == "ew_trend_gross_matched":
            targets = [
                {p: sum(target.values()) / len(products) for p in products}
                if target
                else {}
                for target in targets
            ]
            diagnostics["exposure_source_arm"] = "trend200_vol40_strict"
    elif arm_id == "ew_fixed60":
        targets = [{p: 0.6 / len(products) for p in products} for _ in dates[252:]]
    elif arm_id == "ew_legacy":
        quantities = {p: 1 / len(products) / closes[p][251] for p in products}
        targets = []
        for decision in range(251, len(dates) - 1):
            marked = {p: q * closes[p][decision] for p, q in quantities.items()}
            total = sum(marked.values())
            targets.append({p: v / total for p, v in marked.items()})
    else:
        targets = []
        for decision in range(251, len(dates) - 1):
            selected = _selected(closes, products, decision)
            targets.append({p: 1 / len(selected) for p in selected} if selected else {})
    return dict(
        targets=targets, decision_flags=[True] * len(targets), diagnostics=diagnostics
    )


def evaluate_control(
    bars: dict, arm_id: str, *, fee_bps: float, quote_currency: str
) -> dict:
    if quote_currency != "USDT":
        raise ValueError("INVALID_CRYPTO_CONTROL_CURRENCY")
    if arm_id in LEGACY:
        strategy, variant = LEGACY[arm_id]
        return evaluate_ablation(
            bars, strategy, variant, fee_bps=fee_bps, quote_currency=quote_currency
        ) | {"diagnostics": {"zero_volatility_decisions": 0, "legacy_policy": True}}
    generated = build_control_targets(bars, arm_id)
    prices = dict(
        dates=bars["dates"][251:], close={p: v[251:] for p, v in bars["close"].items()}
    )
    net = account_periods(
        prices, generated["targets"], fee_bps=fee_bps, quote_currency=quote_currency
    )
    gross = account_periods(
        prices, generated["targets"], fee_bps=0, quote_currency=quote_currency
    )
    return dict(
        net=net,
        gross=gross,
        metrics=summarize(net, gross, periods_per_year=365),
        diagnostics=generated["diagnostics"],
    )
