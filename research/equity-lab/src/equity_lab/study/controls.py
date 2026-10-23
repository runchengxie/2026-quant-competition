"""Fixed turnover controls, using the existing self-financing price model."""

import math

import pandas as pd

from ..signals.momentum import generate_momentum_signal
from .ablation import build_targets, evaluate_ablation
from .accounting import account_periods, summarize, validate_prices

ARMS = {
    "ew_daily": ("equal_weight", "baseline"),
    "ew_monthly": ("equal_weight", "monthly"),
    "ew_monthly_buffer20": ("equal_weight", "monthly"),
    "mom20_daily": ("momentum_20d", "baseline"),
    "mom20_monthly": ("momentum_20d", "monthly"),
    "mom20_monthly_buffer20": ("momentum_20d", "monthly"),
}


def build_control_targets(bars: dict, arm_id: str) -> dict:
    if arm_id not in ARMS:
        raise ValueError("UNKNOWN_EQUITY_CONTROL")
    validate_prices(bars)
    if len(bars["dates"]) < 253 or len(bars["close"]) > 10:
        raise ValueError("INVALID_CONTROLS_HISTORY_OR_POOL")
    strategy, variant = ARMS[arm_id]
    dates, closes = bars["dates"], bars["close"]
    if variant == "baseline":
        products = sorted(closes)
        signals = {}
        if strategy == "momentum_20d":
            frame = pd.DataFrame(
                [
                    {"code": p, "date": day, "close": closes[p][i]}
                    for p in products
                    for i, day in enumerate(dates)
                ]
            )
            frame = generate_momentum_signal(frame, lookback_days=20, min_momentum=0)
            signals = {(r.code, r.date): int(r.signal) for r in frame.itertuples()}
        targets = []
        for decision in range(251, len(dates) - 1):
            selected = (
                products
                if strategy == "equal_weight"
                else [p for p in products if signals[(p, dates[decision])] > 0]
            )
            targets.append({p: 1 / len(selected) for p in selected} if selected else {})
        return dict(
            targets=targets,
            decision_flags=[True] * len(targets),
            diagnostics={"skipped_scheduled_decisions": 0},
        )

    scheduled = build_targets(bars, strategy, "monthly")
    if not arm_id.endswith("buffer20"):
        return scheduled | {"diagnostics": {"skipped_scheduled_decisions": 0}}

    quantities, targets, flags = {}, [], []
    skipped = 0
    for offset, is_scheduled in enumerate(scheduled["decision_flags"]):
        decision = 251 + offset
        values = {p: q * closes[p][decision] for p, q in quantities.items()}
        total = math.fsum(values.values())
        current = {p: v / total for p, v in values.items()} if total else {}
        target, trade = current, False
        if is_scheduled:
            proposed = scheduled["targets"][offset]
            distance = math.fsum(
                abs(proposed.get(p, 0) - current.get(p, 0))
                for p in set(proposed) | set(current)
            )
            distance += abs(
                (1 - math.fsum(proposed.values())) - (1 - math.fsum(current.values()))
            )
            # Float roundoff at an exact 20% boundary must not invert the rule.
            trade = (
                offset == 0
                or not proposed
                or distance >= 0.2
                or math.isclose(distance, 0.2, rel_tol=0, abs_tol=1e-12)
            )
            if trade:
                target = proposed
                quantities = {
                    p: weight / closes[p][decision] for p, weight in target.items()
                }
            else:
                skipped += 1
        targets.append(target)
        flags.append(trade)
    return dict(
        targets=targets,
        decision_flags=flags,
        diagnostics={
            "skipped_scheduled_decisions": skipped,
            "buffer_l1": 0.20,
            "includes_cash": True,
        },
    )


def evaluate_control(
    bars: dict, arm_id: str, *, fee_bps: float, quote_currency: str
) -> dict:
    if arm_id not in ARMS or quote_currency != "USD":
        raise ValueError("INVALID_EQUITY_CONTROL")
    if not arm_id.endswith("buffer20"):
        strategy, variant = ARMS[arm_id]
        return evaluate_ablation(
            bars, strategy, variant, fee_bps=fee_bps, quote_currency=quote_currency
        ) | {"diagnostics": {"skipped_scheduled_decisions": 0}}
    generated = build_control_targets(bars, arm_id)
    prices = {
        "dates": bars["dates"][251:],
        "close": {p: v[251:] for p, v in bars["close"].items()},
    }
    net = account_periods(
        prices, generated["targets"], fee_bps=fee_bps, quote_currency=quote_currency
    )
    gross = account_periods(
        prices, generated["targets"], fee_bps=0, quote_currency=quote_currency
    )
    if any(
        not flag and period["turnover"] != 0
        for flag, period in zip(
            generated["decision_flags"], net["periods"], strict=True
        )
    ):
        raise ValueError("OFF_SCHEDULE_CONTROL_TRADE")
    return dict(
        net=net,
        gross=gross,
        metrics=summarize(net, gross, periods_per_year=252),
        diagnostics=generated["diagnostics"],
    )
