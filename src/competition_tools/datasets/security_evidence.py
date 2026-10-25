"""Describe retained exploratory identity/action evidence without certifying it."""

import math
from collections import Counter, defaultdict
from datetime import date


def _day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("INVALID_SECURITY_EVIDENCE_DATE")
    return value


def audit_security_evidence(daily_records, master, intervals, events):
    groups, boundaries = defaultdict(list), defaultdict(list)
    for row in intervals:
        start, end = _day(row["first_date"]), _day(row["last_date"])
        if end < start:
            raise ValueError("INVALID_SECURITY_INTERVAL")
        key = row["Ticker"], row["ResearchKey"]
        boundaries[key].append((start, end))
    for rows in boundaries.values():
        ordered = sorted(rows)
        if any(left[1] >= right[0] for left, right in zip(ordered, ordered[1:])):
            raise ValueError("OVERLAPPING_SECURITY_INTERVALS")
    classes = {row["symbol"]: row["classification"] for row in master}
    if len(classes) != len(master):
        raise ValueError("DUPLICATE_SECURITY_MASTER")
    event_keys, splits = set(), []
    for row in events:
        key = row["symbol"], _day(row["event_date"]), row["event_type"]
        if key in event_keys or str(row["apply_automatically"]).lower() != "false":
            raise ValueError("UNSAFE_OR_DUPLICATE_ACTION_SEED")
        event_keys.add(key)
        if row["event_type"] in ("forward_split", "reverse_split"):
            ratio = float(row["new_shares_per_old_share"])
            if not math.isfinite(ratio) or ratio <= 0:
                raise ValueError("INVALID_SPLIT_SEED")
            splits.append((row["symbol"], row["event_date"], ratio))
    seen, unresolved_days, unmatched, missing_master, jumps = set(), 0, 0, 0, 0
    for row in daily_records:
        day, identity, ticker = _day(row["date"]), row["candidate_id"], row["ticker"]
        key = day, identity
        if key in seen or not isinstance(identity, str) or not identity:
            raise ValueError("INVALID_SECURITY_OBSERVATION")
        seen.add(key)
        unresolved_days += identity.startswith("unresolved:")
        unmatched += not any(start <= day <= end for start, end in boundaries.get((ticker, identity), []))
        missing_master += ticker not in classes
        groups[identity].append(row)
    split_matches = 0
    for rows in groups.values():
        rows.sort(key=lambda r: r["date"])
        for previous, current in zip(rows, rows[1:]):
            try:
                ratio = float(current["open"]) / float(previous["close"])
                if not math.isfinite(ratio) or ratio <= 0:
                    continue
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            jumps += abs(math.log(ratio)) >= math.log(1.5)
            split_matches += any(symbol == current["ticker"] and day == current["date"]
                                 and abs(math.log(ratio * shares)) < math.log(1.25)
                                 for symbol, day, shares in splits)
    return dict(schema="competition.security_evidence_audit.v1", candidate_days=len(seen),
                identity_segments=len(groups), unresolved_identity_segments=sum(k.startswith("unresolved:") for k in groups),
                unresolved_candidate_days=unresolved_days, unmatched_interval_days=unmatched,
                missing_master_days=missing_master, source_classifications=dict(sorted(Counter(classes.values()).items())),
                source_seed_events=len(events), source_split_seeds=len(splits), seed_split_boundary_matches=split_matches,
                large_raw_boundary_jumps=jumps, independently_verified_type_days=0,
                corporate_action_coverage="incomplete", availability_verified=False,
                formal_performance_ready=False, prices_modified=False)
