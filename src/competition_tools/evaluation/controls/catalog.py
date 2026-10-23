"""Fixed policy identities; the historical ablation catalog stays unchanged."""

import copy

from ..study_identity import canonical_hash

ARMS = {
    "US": [
        "ew_daily",
        "ew_monthly",
        "ew_monthly_buffer20",
        "mom20_daily",
        "mom20_monthly",
        "mom20_monthly_buffer20",
    ],
    "crypto": [
        "ew_legacy",
        "trend200_legacy",
        "trend200_vol40_legacy",
        "trend200_fixed60_legacy",
        "trend200_vol40_strict",
        "ew_fixed60",
        "ew_vol40_strict",
        "ew_trend_gross_matched",
    ],
}
COSTS = {"US": [20, 40], "crypto": [0, 10, 25]}
BUDGET = {"jobs": 512, "seconds": 3600, "batch_jobs": 384}


def arm_spec(market: str, arm_id: str) -> dict:
    if market not in ARMS or arm_id not in ARMS[market]:
        raise ValueError("UNKNOWN_CONTROLS_ARM")
    parameters = {}
    if market == "US":
        parameters = {
            "signal": "momentum_20d" if arm_id.startswith("mom20") else "equal_weight",
            "schedule": "monthly" if "monthly" in arm_id else "daily",
        }
        if arm_id.endswith("buffer20"):
            parameters.update(
                buffer_l1=0.20, include_cash=True, scheduled_cash_exit=True
            )
    elif arm_id.endswith("strict") or arm_id == "ew_trend_gross_matched":
        parameters = dict(
            lookback_days=20,
            annual_target=0.4,
            annual_periods=365,
            leverage_cap=1.0,
            zero_volatility="cash",
            sample_ddof=1,
        )
        if arm_id == "ew_trend_gross_matched":
            parameters["exposure_source_arm"] = "trend200_vol40_strict"
    elif arm_id == "ew_fixed60":
        parameters = {"multiplier": 0.6}
    return copy.deepcopy(
        {
            "arm_id": arm_id,
            "parameters": parameters,
            "role": "post_hoc_diagnostic"
            if arm_id == "trend200_fixed60_legacy"
            else "retrospective_control",
        }
    )


CATALOG_SHA256 = canonical_hash(
    {m: [arm_spec(m, a) for a in arms] for m, arms in ARMS.items()}
)
