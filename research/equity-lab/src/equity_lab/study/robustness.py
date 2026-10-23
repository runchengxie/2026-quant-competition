"""Prespecified exclusion diagnostics over the existing monthly account model."""

from .controls import evaluate_control

STOCKS = frozenset("AAPL MSFT AMZN GOOGL META NVDA JPM JNJ XOM PG".split())
POOLS = {
    "full_pool": STOCKS,
    "exclude_nvda": STOCKS - {"NVDA"},
    "exclude_three": STOCKS - {"NVDA", "GOOGL", "META"},
    "fixed_six": frozenset("AAPL MSFT JPM JNJ XOM PG".split()),
}


def evaluate_robustness(bars: dict, pool_id: str, *, fee_bps: int) -> dict:
    if (
        pool_id not in POOLS
        or type(fee_bps) is not int
        or fee_bps not in (20, 40)
        or set(bars.get("close", {})) != STOCKS
    ):
        raise ValueError("INVALID_EQUITY_ROBUSTNESS_IDENTITY")
    selected = dict(
        dates=bars["dates"], close={p: bars["close"][p] for p in sorted(POOLS[pool_id])}
    )
    return evaluate_control(
        selected, "ew_monthly", fee_bps=fee_bps, quote_currency="USD"
    )
