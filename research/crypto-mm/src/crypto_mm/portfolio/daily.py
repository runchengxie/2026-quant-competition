"""Existing daily target policies, independent of replay and maker execution.

Legacy and strict volatility policies deliberately retain their different
zero-volatility conventions. Targets are model weights, never broker orders.
"""

import math
from datetime import date
from statistics import stdev

from crypto_mm.data.daily_prices import validate_prices
from crypto_mm.signals.daily_trend import (
    hysteresis_states,
    select_trend_products as _selected,
)


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


def build_study_targets(bars: dict, strategy: str) -> list[dict]:
    if strategy not in {"equal_weight", "momentum_63d", "trend_200d"}:
        raise ValueError("INVALID_CRYPTO_STUDY")
    validate_prices(bars)
    dates, closes = bars["dates"], bars["close"]
    if len(dates) < 253 or not closes:
        raise ValueError("INSUFFICIENT_HISTORY")
    products = sorted(closes)
    if len(products) > 20 or any(len(v) != len(dates) for v in closes.values()):
        raise ValueError("INVALID_STUDY_PRICES")
    quantities = {p: 1 / len(products) / closes[p][251] for p in products}
    targets = []
    for index in range(252, len(dates)):
        decision = index - 1
        if strategy == "equal_weight":
            values = {p: q * closes[p][decision] for p, q in quantities.items()}
            target = {p: v / sum(values.values()) for p, v in values.items()}
        else:
            selected = (
                [p for p in products if closes[p][decision] > closes[p][decision - 63]]
                if strategy == "momentum_63d"
                else [
                    p
                    for p in products
                    if closes[p][decision]
                    > sum(closes[p][decision - 199 : decision + 1]) / 200
                ]
            )
            target = {p: 1 / len(selected) for p in selected} if selected else {}
        targets.append(target)
    return targets


def build_ablation_targets(bars: dict, strategy: str, variant_id: str) -> dict:
    if strategy != "trend_200d" or variant_id not in {
        "hysteresis_2pct",
        "vol_target_40pct",
        "fixed_exposure_60pct",
    }:
        raise ValueError("INVALID_CRYPTO_ABLATION")
    validate_prices(bars)
    dates, closes = bars["dates"], bars["close"]
    if len(dates) < 253:
        raise ValueError("INSUFFICIENT_HISTORY")
    products = sorted(closes)
    if len(products) > 20:
        raise ValueError("INVALID_STUDY_PRICES")
    states = (
        {p: hysteresis_states(closes[p]) for p in products}
        if variant_id == "hysteresis_2pct"
        else {}
    )
    targets = []
    for index in range(252, len(dates)):
        decision = index - 1
        selected = (
            [p for p in products if states[p][decision]]
            if states
            else [
                p
                for p in products
                if closes[p][decision]
                > sum(closes[p][decision - 199 : decision + 1]) / 200
            ]
        )
        scale = 0.6 if variant_id == "fixed_exposure_60pct" else 1.0
        if variant_id == "vol_target_40pct" and selected:
            observed = [
                sum(closes[p][j] / closes[p][j - 1] - 1 for p in selected)
                / len(selected)
                for j in range(decision - 19, decision + 1)
            ]
            if not all(math.isfinite(v) for v in observed):
                raise ValueError("INVALID_ABLATION_VOLATILITY")
            volatility = stdev(observed) * math.sqrt(365)
            if not math.isfinite(volatility):
                raise ValueError("INVALID_ABLATION_VOLATILITY")
            scale = min(1.0, 0.4 / volatility) if volatility > 0 else 1.0
        targets.append({p: scale / len(selected) for p in selected} if selected else {})
    return {"targets": targets, "decision_flags": [True] * len(targets)}


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
        return build_ablation_targets(bars, strategy, variant) | {
            "diagnostics": diagnostics
        }
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
