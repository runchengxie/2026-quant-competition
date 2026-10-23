"""USD-only, event-free next-session modeled price accounting."""

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from exchange_calendars import get_calendar

from ..accounting.contracts import ArtifactRef, ResearchClock
from ..accounting.usd_ledger_models import (
    USDInstrument,
    USDModeledExecutionPrice,
    USDPriceObservation,
    USDRebalanceDecision,
    USDReplayConfig,
    USDReplayRequest,
)
from ..next_open.calendar import (
    CALENDAR_PACKAGE_VERSION,
    _scheduled_session,
    first_open_after,
)
from .inputs import USNextSessionInputs

MODEL_ID = "us-next-session-price-nav.v1"
POLICY_ID = "us-next-session-after-information-availability.v1"


def _time(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("AWARE_INFORMATION_TIME_REQUIRED")
    return parsed.astimezone(timezone.utc)


def build_us_replay_request(
    inputs: USNextSessionInputs, *, fee_bps: Decimal
) -> USDReplayRequest:
    if (
        not isinstance(fee_bps, Decimal)
        or not fee_bps.is_finite()
        or fee_bps < 0
        or fee_bps >= 10000
    ):
        raise ValueError("INVALID_FEE_SCENARIO")
    calendars = {"US": get_calendar("XNYS")}
    calendar_ref = f"exchange_calendars:{CALENDAR_PACKAGE_VERSION}:XNYS"
    spec = inputs.schedule
    instruments = tuple(
        USDInstrument(k, "equity", "USD", v["lot_size"], calendar_ref)
        for k, v in spec["instruments"].items()
    )
    prices, opens, decisions, times = [], [], [], set()
    refs = {
        k: ArtifactRef(f"us-price:{k}", spec["files"][k]["sha256"])
        for k in inputs.assets
    }
    for instrument, frame in inputs.assets.items():
        for row in frame.itertuples(index=False):
            session = _scheduled_session("US", row.date, calendars)
            prices.append(
                USDPriceObservation(
                    instrument,
                    session.scheduled_close_at,
                    session.scheduled_close_at,
                    Decimal(str(row.close)),
                    "currency_per_share",
                    refs[instrument],
                    "assumed_date_lag",
                    calendar_ref,
                    False,
                )
            )
            times.add(session.scheduled_close_at)
    seen, prior = set(), None
    for item in spec["schedule"]:
        if (
            set(item)
            != {"decision_id", "signal_at", "available_at", "decision_at", "weights"}
            or not isinstance(item["decision_id"], str)
            or not item["decision_id"]
            or item["decision_id"] in seen
        ):
            raise ValueError("INVALID_DECISION_ID_OR_FIELDS")
        seen.add(item["decision_id"])
        signal, available, decision = (
            _time(item[k]) for k in ("signal_at", "available_at", "decision_at")
        )
        if not signal <= available <= decision or (
            prior is not None and decision <= prior
        ):
            raise ValueError("NONCAUSAL_INFORMATION_CLOCK")
        prior = decision
        if not isinstance(item["weights"], dict) or set(item["weights"]) - set(
            inputs.assets
        ):
            raise ValueError("INVALID_TARGET_INSTRUMENTS")
        weights = {}
        for k in inputs.assets:
            weight = item["weights"].get(k, 0)
            if (
                type(weight) not in (int, float)
                or not math.isfinite(weight)
                or weight < 0
            ):
                raise ValueError("INVALID_TARGET_WEIGHT")
            weights[k] = Decimal(str(weight))
        if sum(weights.values()) > 1:
            raise ValueError("TARGET_EXCEEDS_CASH")
        execution_times = {}
        for instrument, frame in inputs.assets.items():
            session = first_open_after("US", available, tuple(frame["date"]), calendars)
            if decision >= session.scheduled_open_at:
                raise ValueError("DECISION_MISSED_FIRST_ELIGIBLE_OPEN")
            row = frame.loc[frame["date"] == session.session_date].iloc[0]
            execution_times[instrument] = session.scheduled_open_at
            opens.append(
                USDModeledExecutionPrice(
                    instrument,
                    session.session_date,
                    session.scheduled_open_at,
                    Decimal(str(row["open"])),
                    "currency_per_share",
                    refs[instrument],
                    calendar_ref,
                    MODEL_ID,
                )
            )
            times.add(session.scheduled_open_at)
        first, last = min(execution_times.values()), max(execution_times.values())
        clock = ResearchClock(
            "UTC",
            signal,
            available,
            decision,
            max(times),
            POLICY_ID,
            calendar_ref,
            first,
            first,
            last,
        )
        decisions.append(
            USDRebalanceDecision(item["decision_id"], clock, weights, execution_times)
        )
    return USDReplayRequest(
        instruments,
        tuple(prices),
        (),
        tuple(decisions),
        tuple(sorted(times)),
        USDReplayConfig(
            Decimal(100000),
            spec["sizing_mode"],
            fee_bps,
            Decimal(0),
            Decimal(0),
            timedelta(days=7),
            timedelta(days=7),
            {},
            allow_assumed_availability=True,
            allow_modeled_execution_prices=True,
        ),
        tuple(opens),
    )
