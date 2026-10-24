"""Evaluate fixed control policies through the existing daily cash ledger."""

from crypto_mm.portfolio.daily import LEGACY, STRICT as STRICT, build_control_targets
from .ablation import evaluate_ablation
from .study_accounting import validate_prices, account_periods, summarize


def replay_observation(
    bars: dict, arm_id: str, *, score_start: str, fee_bps: float, quote_currency: str
) -> dict:
    """Extend a single self-financing account by replaying its immutable prefix."""
    validate_prices(bars)
    if (
        arm_id not in {"trend200_vol40_strict", "ew_trend_gross_matched", "ew_legacy"}
        or len(bars["dates"]) < 253
        or bars["dates"][252] != score_start
        or type(fee_bps) not in (int, float)
        or fee_bps not in (0, 10, 25)
    ):
        raise ValueError("INVALID_OBSERVATION_REPLAY")
    return evaluate_control(
        bars, arm_id, fee_bps=fee_bps, quote_currency=quote_currency
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
