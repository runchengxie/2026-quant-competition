"""Offline DEX planning and conservative, account-wide included-credit checks."""

from datetime import datetime, timedelta, timezone

from .dex_spec import validate_dex_spec, utc_hour

CREDIT_SOURCE = "https://docs.dexpaprika.com/knowledge-base/credit-usage"
USAGE_SOURCE = "https://docs.dexpaprika.com/tutorials/check-credit-usage"
UNITS_SOURCE = "https://docs.dexpaprika.com/tutorials/token-ohlcv"


def plan_dex(spec):
    validate_dex_spec(spec)
    chunks = []
    cursor, end = utc_hour(spec["start"]), utc_hour(spec["end"])
    while cursor < end:
        stop = min(end, cursor + timedelta(hours=720))
        chunks.append(
            {
                "start": cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "interval": "1h",
                "limit": 1000,
            }
        )
        cursor = stop
    count = len(spec["assets"])
    # Initial/final usage, networks, usage checkpoint per asset, token metadata,
    # three OHLCV resources, and optional explicit pool snapshots. Two attempts each.
    resources = (
        3 + count * (2 + len(chunks)) + sum("pool_address" in a for a in spec["assets"])
    )
    return {
        "schema": "competition.dex_plan.v1",
        "dataset_id": spec["dataset_id"],
        "version": spec["version"],
        "assets": count,
        "chunks": chunks,
        "ohlcv_requests": count * len(chunks),
        "resources": resources,
        "worst_case_attempts": 2 * resources,
        "fits_budget": 2 * resources <= spec["budget"]["requests"],
        "unresolved": [
            "pro_entitlement",
            "included_credit_headroom",
            "response_contract",
            "publication_permission",
        ],
        "units": {"price": "USD", "volume": "USD"},
        "units_source": UNITS_SOURCE,
    }


def usage_preflight(transport, planned_attempts):
    value = transport.get_json("usage")
    blocked = {"status": "blocked", "reason": "CREDIT_CONTRACT_UNVERIFIED"}
    try:
        if (
            not isinstance(value, dict)
            or value["plan"] != "pro"
            or type(planned_attempts) is not int
            or planned_attempts < 0
        ):
            return blocked
        used, left = value["requests_used"], value["requests_left"]
        if type(used) is not int or type(left) is not int or min(used, left) < 0:
            return blocked
        start, end = (
            datetime.fromisoformat(value[k].replace("Z", "+00:00"))
            for k in ("period_started_at", "period_ends_at")
        )
        now = datetime.now(timezone.utc)
        if (
            start.utcoffset() != timedelta(0)
            or end.utcoffset() != timedelta(0)
            or not start <= now < end
        ):
            return blocked
        period = [start.isoformat(), end.isoformat()]
        previous = transport.credit_state
        if previous and (previous["period"] != period or used < previous["used"]):
            return {"status": "blocked", "reason": "CREDIT_USAGE_DISCONTINUITY"}
        remaining = min(left, max(0, 5_000_000 - used))
        transport.credit_state = {
            "period": period,
            "used": used,
            "remaining": remaining,
            "at_request": transport.requests,
        }
        return {
            "status": "allowed" if remaining >= planned_attempts else "blocked",
            "reason": None
            if remaining >= planned_attempts
            else "INCLUDED_CREDITS_EXHAUSTED",
            "plan": "pro",
            "period": period,
            "included_remaining": remaining,
            "credit_upper_bound_per_attempt": 1,
            "credit_source": CREDIT_SOURCE,
            "usage_source": USAGE_SOURCE,
            "scope": "account_wide_gauge_not_atomic_reservation",
        }
    except (KeyError, TypeError, ValueError, OverflowError):
        return blocked


def require_headroom(transport, remaining_attempts):
    state = transport.credit_state
    spent = transport.requests - state["at_request"] if state else 0
    if not state or state["remaining"] - spent < remaining_attempts:
        raise ValueError("INCLUDED_CREDITS_EXHAUSTED")
