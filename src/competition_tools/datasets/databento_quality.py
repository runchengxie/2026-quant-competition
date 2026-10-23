"""Validate raw display-price CSV without filling missing market observations."""

from datetime import datetime
from decimal import Decimal, InvalidOperation


def inspect_rows(rows: list[dict], spec: dict, sessions: dict) -> dict:
    tables = {s: {} for s in spec["symbols"]}
    identities = {}
    for row in rows:
        try:
            symbol = row["symbol"]
            stamp = datetime.fromisoformat(row["ts_event"].replace("Z", "+00:00"))
            day = stamp.date().isoformat()
            if (
                symbol not in tables
                or stamp.tzinfo is None
                or stamp.utcoffset().total_seconds() != 0
                or stamp.hour
                or stamp.minute
                or stamp.second
                or stamp.microsecond
                or not spec["start"] <= day < spec["end"]
                or row["rtype"] != "35"
                or not row["instrument_id"].isdigit()
                or int(row["instrument_id"]) <= 0
            ):
                raise ValueError
            values = [Decimal(row[k]) for k in ("open", "high", "low", "close")]
            o, h, lo, c = values
            volume = Decimal(row["volume"])
            if (
                any(not v.is_finite() or v <= 0 for v in values)
                or not volume.is_finite()
                or volume < 0
                or volume != volume.to_integral_value()
                or not lo <= min(o, c) <= max(o, c) <= h
            ):
                raise ValueError
        except (KeyError, TypeError, ValueError, InvalidOperation, AttributeError):
            raise ValueError("INVALID_DATABENTO_ROW") from None
        if day in tables[symbol]:
            raise ValueError("DUPLICATE_SYMBOL_DATE")
        identity = (day, row["instrument_id"])
        if identity in identities and identities[identity] != symbol:
            raise ValueError("AMBIGUOUS_INSTRUMENT_IDENTITY")
        identities[identity] = symbol
        tables[symbol][day] = [day, *map(str, values), str(int(volume))]
    grid = sessions.get("sessions")
    issues = []
    if grid is None:
        issues.append("CALENDAR_UNVERIFIED")
    elif grid != sorted(set(grid)):
        raise ValueError("INVALID_SESSION_GRID")
    if not sessions.get("listing_verified", False):
        issues.append("LISTING_CALENDAR_UNVERIFIED")
    coverage = {}
    for symbol, table in tables.items():
        dates = sorted(table)
        missing = sorted(set(grid or []) - set(dates))
        extra = sorted(set(dates) - set(grid)) if grid is not None else []
        if not dates or missing or extra:
            issues.append("INCOMPLETE_COVERAGE")
        coverage[symbol] = {
            "rows": len(table),
            "start": dates[0] if dates else None,
            "end": dates[-1] if dates else None,
            "missing_sessions": missing,
            "extra_sessions": extra,
        }
    return {
        "price_basis": "raw",
        "accepted_research": False,
        "coverage": coverage,
        "issue_codes": sorted(set(issues)),
        "calendar": sessions,
        "corporate_actions": "unverified",
        "timing": {
            "bar_timestamp": "UTC interval start",
            "session_label": "UTC date",
            "assumed_final_publication_local": "20:15",
            "publication_timezone": "America/New_York",
            "actual_historical_availability_verified": False,
        },
        "normalized": {
            s: [table[d] for d in sorted(table)] for s, table in tables.items()
        },
    }
