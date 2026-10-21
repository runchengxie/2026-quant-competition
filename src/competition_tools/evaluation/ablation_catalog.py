"""Fixed ablation catalog and explicitly supplied retrospective provenance."""

import copy
import json
from pathlib import Path, PurePosixPath
from competition_tools.datasets.daily_storage import safe_path
from competition_tools.datasets.storage import digest
from .study_identity import canonical_hash
from .study_plan import COSTS, STRATEGIES


def variant_spec(market: str, strategy: str, variant_id: str) -> dict:
    if market not in STRATEGIES or strategy not in STRATEGIES[market]:
        raise ValueError("UNKNOWN_ABLATION_VARIANT")
    parameters = {}
    role = "retrospective_ablation"
    if variant_id == "baseline":
        pass
    elif (
        market in {"US", "HK"}
        and strategy in {"equal_weight", "momentum_20d", "sma_cross"}
        and variant_id in {"weekly", "monthly"}
    ):
        parameters = {"schedule": variant_id, "initial_entry": True}
    elif market == "crypto" and strategy == "trend_200d":
        if variant_id == "hysteresis_2pct":
            parameters = {"band": 0.02}
        elif variant_id == "vol_target_40pct":
            parameters = {
                "lookback_days": 20,
                "annual_target": 0.4,
                "annual_periods": 365,
            }
        elif variant_id == "fixed_exposure_60pct":
            parameters = {"multiplier": 0.6}
            role = "post_hoc_diagnostic"
        else:
            raise ValueError("UNKNOWN_ABLATION_VARIANT")
    else:
        raise ValueError("UNKNOWN_ABLATION_VARIANT")
    return {
        "variant_id": variant_id,
        "variant_parameters": parameters,
        "evidence_role": role,
    }


def catalog() -> dict:
    return {
        m: [
            {"strategy": s, **variant_spec(m, s, v)}
            for s in STRATEGIES[m]
            for v in (
                ["baseline", "weekly", "monthly"]
                if m != "crypto" and s in {"equal_weight", "momentum_20d", "sma_cross"}
                else [
                    "baseline",
                    "hysteresis_2pct",
                    "vol_target_40pct",
                    "fixed_exposure_60pct",
                ]
                if m == "crypto" and s == "trend_200d"
                else ["baseline"]
            )
        ]
        for m in COSTS
    }


def validate_ablation_spec(spec: dict) -> dict:
    try:
        if (
            set(spec) != {"schema", "manifests", "costs", "variants", "origin"}
            or spec["schema"] != "competition.evaluation_spec.v3"
        ):
            raise ValueError
        if spec["costs"] != COSTS or any(
            type(n) is not int for ns in spec["costs"].values() for n in ns
        ):
            raise ValueError
        if (
            not isinstance(spec["manifests"], list)
            or not 1 <= len(spec["manifests"]) <= 3
            or any(not isinstance(p, str) or not p for p in spec["manifests"])
            or len(set(spec["manifests"])) != len(spec["manifests"])
        ):
            raise ValueError
        if (
            not isinstance(spec["variants"], dict)
            or not spec["variants"]
            or not set(spec["variants"]) <= set(COSTS)
        ):
            raise ValueError
        for m, items in spec["variants"].items():
            if not isinstance(items, list) or not items:
                raise ValueError
            seen = set()
            for item in items:
                if set(item) != {"strategy", "variant_id"}:
                    raise ValueError
                pair = (item["strategy"], item["variant_id"])
                variant_spec(m, *pair)
                if pair in seen:
                    raise ValueError
                seen.add(pair)
            if not {(s, "baseline") for s in STRATEGIES[m]} <= seen:
                raise ValueError
        origin = spec["origin"]
        if set(origin) != {
            "probe_protocol",
            "diagnostic_protocol",
            "evidence_manifest",
        } or any(not isinstance(v, str) or not v for v in origin.values()):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ValueError("INVALID_ABLATION_SPEC") from None
    return copy.deepcopy(spec)


def load_origin_evidence(origin: dict) -> dict:
    try:
        paths = {k: safe_path(Path(v)) for k, v in origin.items()}
        if set(paths) != {"probe_protocol", "diagnostic_protocol", "evidence_manifest"}:
            raise ValueError
        manifest = json.loads(paths["evidence_manifest"].read_text(encoding="utf-8"))
        records = {}
        for r in manifest["files"]:
            rel = PurePosixPath(r["path"])
            if (
                rel.is_absolute()
                or ".." in rel.parts
                or "\\" in r["path"]
                or ":" in r["path"]
                or r["path"] in records
            ):
                raise ValueError
            p = safe_path(paths["evidence_manifest"].parent / r["path"])
            if p.stat().st_size != r["bytes"] or digest(p) != r["sha256"]:
                raise ValueError
            records[r["path"]] = r
        protocols = []
        for key in ["probe_protocol", "diagnostic_protocol"]:
            p = paths[key]
            rel = p.relative_to(paths["evidence_manifest"].parent).as_posix()
            if rel not in records:
                raise ValueError
            value = json.loads(p.read_text(encoding="utf-8"))
            if value.get("accepted_research") is not False:
                raise ValueError
            protocols.append(value)
        if (
            protocols[0].get("retrospective") is not True
            or protocols[1].get("post_hoc") is not True
            or protocols[1].get("parent_protocol_sha256")
            != digest(paths["probe_protocol"])
        ):
            raise ValueError
        return {
            **{k + "_sha256": digest(v) for k, v in paths.items()},
            "stage": "retrospective",
            "retrospective": True,
            "accepted_research": False,
        }
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("INVALID_ORIGIN_EVIDENCE") from None


CATALOG_SHA256 = canonical_hash(catalog())
