"""The complete finite grid is fixed before new results are inspected."""

from ..study_identity import canonical_hash

STOCKS = frozenset("AAPL MSFT AMZN GOOGL META NVDA JPM JNJ XOM PG".split())
POOLS = dict(exclude_nvda=sorted(STOCKS - {"NVDA"}), exclude_three=sorted(STOCKS - {"NVDA", "GOOGL", "META"}), fixed_six=sorted("AAPL MSFT JPM JNJ XOM PG".split()))
CRYPTO_ARMS = ("trend200_vol40_strict", "ew_trend_gross_matched")
CATALOG_SHA256 = canonical_hash(dict(pools=POOLS, US_costs=[20, 40], crypto_arms=CRYPTO_ARMS, crypto_costs=[35, 50], role="retrospective_diagnostic"))


def diagnostic_grid(parent_jobs: list[dict]) -> list[dict]:
    selected = [j for j in parent_jobs if (j["market"] == "US" and j["arm_id"] == "ew_monthly" and j["fee_bps"] in (20, 40)) or (j["market"] == "crypto" and j["arm_id"] in CRYPTO_ARMS and j["fee_bps"] == 25)]
    identities = [(j["market"], j["arm_id"], j["fee_bps"], j["fold"]["start"]) for j in selected]
    us_dates = {j["fold"]["start"] for j in selected if j["market"] == "US"}
    cr_dates = {j["fold"]["start"] for j in selected if j["market"] == "crypto"}
    expected = {("US", "ew_monthly", fee, day) for day in us_dates for fee in (20, 40)} | {("crypto", arm, 25, day) for day in cr_dates for arm in CRYPTO_ARMS}
    if len(us_dates) != 11 or len(cr_dates) != 12 or len(identities) != len(set(identities)) or set(identities) != expected:
        raise ValueError("INCOMPLETE_OR_DUPLICATE_ROBUSTNESS_PARENT_GRID")
    rows = []
    for job in selected:
        if job["market"] == "US":
            rows.extend(dict(input_job=job, pool_id=pool, fee_bps=job["fee_bps"]) for pool in POOLS)
        else:
            rows.extend(dict(input_job=job, pool_id="existing_eight", fee_bps=fee) for fee in (35, 50))
    return rows
