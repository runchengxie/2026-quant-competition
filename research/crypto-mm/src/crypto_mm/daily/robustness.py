"""Total-cost replays reuse fixed targets and recompute cash-funded holdings."""

from .controls import evaluate_control


def replay_robustness(bars: dict, arm_id: str, *, fee_bps: int) -> dict:
    if arm_id not in {"trend200_vol40_strict", "ew_trend_gross_matched"} or type(fee_bps) is not int or fee_bps not in (35, 50):
        raise ValueError("INVALID_CRYPTO_ROBUSTNESS_IDENTITY")
    return evaluate_control(bars, arm_id, fee_bps=fee_bps, quote_currency="USDT")
