"""Explicit Paper historical-data pilot; never starts Gateway or submits orders."""

import csv
import json
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

from .quality import validate_bars
from .storage import spec_hash, write_json
from .transport import DatasetBlocked


def collect_pilot(
    spec: dict, connection: dict, staging: Path, *, client, contract_factory, sleep
) -> dict:
    if (
        set(connection) != {"host", "port", "client_id"}
        or connection["host"] != "127.0.0.1"
        or connection["port"] != 4002
        or type(connection["client_id"]) is not int
    ):
        raise ValueError("EXPLICIT_PAPER_CONNECTION_REQUIRED")
    if len(spec["products"]) > 20 or not spec.get("contracts"):
        raise ValueError("EXPLICIT_PILOT_CONTRACTS_REQUIRED")
    product = spec["products"][0]
    definitions = [r for r in spec["contracts"] if r.get("product") == product]
    if len(definitions) != 1:
        raise ValueError("EXPLICIT_CONTRACT_REQUIRED")
    definition = definitions[0]
    if (
        set(definition) != {"product", "con_id", "exchange", "currency"}
        or type(definition["con_id"]) is not int
        or definition["con_id"] <= 0
        or definition["exchange"] not in {"SMART", "SEHK"}
        or definition["currency"] not in {"USD", "HKD"}
    ):
        raise ValueError("INVALID_CONTRACT_IDENTITY")
    coverage, gaps = {}, []
    try:
        client.connect(
            connection["host"],
            connection["port"],
            clientId=connection["client_id"],
            timeout=min(12, spec["budget"]["seconds"]),
            readonly=True,
        )
        contract = contract_factory(
            conId=definition["con_id"],
            exchange=definition["exchange"],
            currency=definition["currency"],
            secType="STK",
        )
        end = date.fromisoformat(spec["end"]) + timedelta(days=1)
        response = client.reqHistoricalData(
            contract,
            endDateTime=end.strftime("%Y%m%d 00:00:00 UTC"),
            durationStr="1 M",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
            timeout=min(60, spec["budget"]["seconds"]),
        )
        rows = [
            [
                str(r.date),
                str(r.open),
                str(r.high),
                str(r.low),
                str(r.close),
                str(r.volume),
            ]
            for r in response
        ]
        rows = [r for r in rows if spec["start"] <= r[0] <= spec["end"]]
        validate_bars(rows)
        if not rows:
            gaps.append({"product": product, "reason": "EMPTY_HISTORICAL_RESPONSE"})
        else:
            target = staging / "normalized" / f"{product}.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["date", "open", "high", "low", "close", "volume"])
                writer.writerows(rows)
            if target.stat().st_size > spec["budget"]["bytes"]:
                raise DatasetBlocked("BYTE_BUDGET")
            coverage[product] = {
                "rows": len(rows),
                "start": rows[0][0],
                "end": rows[-1][0],
            }
            gaps.append({"reason": "PILOT_ONLY_BULK_NOT_RUN"})
    finally:
        client.disconnect()
    return {
        "schema": "competition.dataset_receipt.v1",
        "source": "ibkr",
        "spec_hash": spec_hash(spec),
        "status": "partial",
        "coverage": coverage,
        "gaps": gaps,
        "available_at": None,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "normalization": "ibkr-trades-rth-pilot.v1",
        "requests": 1,
        "accepted_research": False,
    }


def acquire(spec: dict, staging: Path) -> dict:
    from competition_tools.team.paths import validate_external

    try:
        from ib_insync import IB, Contract
    except ImportError:
        raise DatasetBlocked("BROKER_DATA_PROFILE_REQUIRED") from None
    connection = json.loads(
        validate_external(Path(spec["credential_file"])).read_text(encoding="utf-8-sig")
    )
    import logging
    import time

    logging.getLogger("ib_insync").setLevel(logging.CRITICAL)
    try:
        value = collect_pilot(
            spec,
            connection,
            staging,
            client=IB(),
            contract_factory=Contract,
            sleep=time.sleep,
        )
    except (ConnectionError, OSError, TimeoutError):
        raise DatasetBlocked("BROKER_UNREACHABLE_OR_TIMEOUT") from None
    write_json(staging / "receipt.json", value)
    return value
