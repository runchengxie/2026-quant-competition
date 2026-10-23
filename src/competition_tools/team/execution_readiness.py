"""Inventory cached daily data evidence without creating execution permission."""

from pathlib import Path

from ..datasets.daily_storage import safe_path
from ..datasets.storage import digest, write_json
from ..evaluation.controls.contracts import read_json
from .processes import envelope


def audit_execution_inputs(spec: dict) -> dict:
    if (
        not isinstance(spec, dict)
        or set(spec) != {"schema", "manifests"}
        or spec["schema"] != "competition.us_execution_readiness_spec.v1"
        or not isinstance(spec["manifests"], list)
        or not 1 <= len(spec["manifests"]) <= 16
    ):
        raise ValueError("INVALID_EXECUTION_READINESS_SPEC")
    datasets, seen = [], set()
    for record in spec["manifests"]:
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ValueError("INVALID_MANIFEST_RECEIPT")
        path = safe_path(Path(record["path"]))
        before = digest(path)
        if before != record["sha256"] or before in seen:
            raise ValueError("MANIFEST_HASH_MISMATCH_OR_DUPLICATE")
        seen.add(before)
        manifest = read_json(path)
        metadata = manifest.get("spec", {})
        if not isinstance(metadata, dict):
            raise ValueError("INVALID_MANIFEST_SPEC")
        # Daily dataset contracts contain no reviewed per-signal availability,
        # first-RTH-open or corporate-action coverage evidence. Caller-added
        # metadata cannot upgrade these facts to a verified execution input.
        checks = [
            dict(
                code="USD_QUOTE_DECLARED",
                status="passed"
                if metadata.get("quote_currency") == "USD"
                else "blocked",
            ),
            dict(
                code="US_MARKET_DECLARED",
                status="passed" if metadata.get("market") == "US" else "blocked",
            ),
            dict(
                code="RAW_EXECUTION_PRICES_REQUIRED",
                status="passed" if metadata.get("price_basis") == "raw" else "blocked",
            ),
            dict(code="FIRST_REGULAR_OPEN_EVIDENCE_UNVERIFIED", status="blocked"),
            dict(code="AVAILABILITY_EVIDENCE_UNVERIFIED", status="blocked"),
            dict(code="CORPORATE_ACTION_MODEL_UNVERIFIED", status="blocked"),
            dict(code="LOT_AND_LISTING_EVIDENCE_UNVERIFIED", status="blocked"),
        ]
        if digest(path) != before:
            raise ValueError("MANIFEST_HASH_CHANGED")
        datasets.append(dict(manifest_sha256=before, checks=checks))
    return dict(
        schema="competition.us_execution_readiness.v1",
        status="blocked",
        scope="cached_daily_manifest_evidence_inventory",
        datasets=datasets,
        model_id="us-next-session-price-nav.v1",
        return_basis="usd_price_nav",
        orders_submitted=0,
        execution_eligible=False,
        total_return=False,
    )


def execute(config, spec_path: Path, output_root: Path) -> dict:
    value = audit_execution_inputs(read_json(safe_path(spec_path)))
    output = safe_path(output_root)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "readiness.json", value)
    return envelope(
        "execution-readiness",
        issues=["US_EXECUTION_EVIDENCE_BLOCKED"],
        projects=[value],
    )
