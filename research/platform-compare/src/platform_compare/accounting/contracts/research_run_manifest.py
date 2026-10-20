from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .research_clock import ResearchClock, validate_research_clock

RESEARCH_RUN_MANIFEST_SCHEMA_VERSION = "research.backtest-run.v1"
QUANT_RUN_MANIFEST_SCHEMA_VERSION = RESEARCH_RUN_MANIFEST_SCHEMA_VERSION
RESEARCH_EVIDENCE_TIERS = frozenset({"diagnostic", "execution_aware"})
PROVENANCE_FIELDS = (
    "data_vintage",
    "calendar_version",
    "strategy_version",
    "engine_version",
    "execution_policy",
    "cost_model",
    "random_seed",
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _required_text(value: object, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _sha256(value: object, field: str) -> str:
    text = _required_text(value, field)
    if _SHA256.fullmatch(text) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _aware_datetime(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _required_text(value, field)
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    sha256: str
    path: str | None = None

    def __post_init__(self) -> None:
        _required_text(self.artifact_id, "artifact_ref.artifact_id")
        _sha256(self.sha256, "artifact_ref.sha256")
        if self.path is not None:
            _required_text(self.path, "artifact_ref.path")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ArtifactRef:
        return _artifact_ref_from_mapping(payload, "artifact_ref")

    def to_mapping(self) -> dict[str, str]:
        result = {"artifact_id": self.artifact_id, "sha256": self.sha256}
        if self.path is not None:
            result["path"] = self.path
        return result


@dataclass(frozen=True)
class ProducerVersion:
    repository: str
    commit: str
    version: str | None = None

    def __post_init__(self) -> None:
        _required_text(self.repository, "producer.repository")
        _required_text(self.commit, "producer.commit")
        if self.version is not None:
            _required_text(self.version, "producer.version")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ProducerVersion:
        return cls(
            repository=_required_text(payload.get("repository"), "producer.repository"),
            commit=_required_text(payload.get("commit"), "producer.commit"),
            version=_optional_text(payload.get("version")),
        )

    def to_mapping(self) -> dict[str, str]:
        result = {"repository": self.repository, "commit": self.commit}
        if self.version is not None:
            result["version"] = self.version
        return result


def _artifact_ref_from_mapping(payload: Mapping[str, Any], field: str) -> ArtifactRef:
    path = _optional_text(payload.get("path"))
    return ArtifactRef(
        artifact_id=_required_text(payload.get("artifact_id"), f"{field}.artifact_id"),
        sha256=_sha256(payload.get("sha256"), f"{field}.sha256"),
        path=path,
    )


def _mapping_list(value: object, field: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    if not all(isinstance(item, Mapping) for item in value):
        raise ValueError(f"each {field} item must be an object")
    return list(value)


def _provenance(value: object, *, required: bool) -> dict[str, str]:
    if value is None:
        if required:
            raise ValueError("provenance is required for execution_aware runs")
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("provenance must be an object")
    result = {str(key): _required_text(item, f"provenance.{key}") for key, item in value.items()}
    if required:
        missing = [field for field in PROVENANCE_FIELDS if field not in result]
        if missing:
            raise ValueError(f"provenance missing required fields: {', '.join(missing)}")
    return result


def _artifact_refs(value: object, field: str) -> tuple[ArtifactRef, ...]:
    refs = tuple(_artifact_ref_from_mapping(item, field) for item in _mapping_list(value, field))
    ids = [item.artifact_id for item in refs]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{field} contains duplicate artifact_id")
    return refs


def _producer_versions(value: object) -> tuple[ProducerVersion, ...]:
    items = tuple(
        ProducerVersion.from_mapping(item) for item in _mapping_list(value, "producer_versions")
    )
    repositories = [item.repository for item in items]
    if len(repositories) != len(set(repositories)):
        raise ValueError("producer_versions contains duplicate repository")
    return items


def _component_refs(value: object) -> dict[str, ArtifactRef]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("component_refs must be an object")
    result: dict[str, ArtifactRef] = {}
    for role, payload in value.items():
        role_name = _required_text(role, "component_refs role")
        if not isinstance(payload, Mapping):
            raise ValueError(f"component_refs.{role_name} must be an object")
        result[role_name] = _artifact_ref_from_mapping(payload, f"component_refs.{role_name}")
    return result


@dataclass(frozen=True)
class ResearchRunManifest:
    run_id: str
    strategy_ref: str
    research_purpose: str
    evidence_tier: str
    clock: ResearchClock
    configuration_sha256: str
    producer_versions: tuple[ProducerVersion, ...]
    data_refs: tuple[ArtifactRef, ...]
    signal_refs: tuple[ArtifactRef, ...]
    portfolio_result_ref: ArtifactRef
    created_at: datetime
    benchmark_ref: ArtifactRef | None = None
    evidence_refs: tuple[ArtifactRef, ...] = ()
    component_refs: Mapping[str, ArtifactRef] | None = None
    provenance: Mapping[str, str] | None = None
    schema_version: str = RESEARCH_RUN_MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RESEARCH_RUN_MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"unsupported research run manifest schema {self.schema_version!r}")
        _required_text(self.run_id, "run_id")
        _required_text(self.strategy_ref, "strategy_ref")
        _required_text(self.research_purpose, "research_purpose")
        if self.evidence_tier not in RESEARCH_EVIDENCE_TIERS:
            raise ValueError(f"unsupported evidence_tier {self.evidence_tier!r}")
        _sha256(self.configuration_sha256, "configuration_sha256")
        _aware_datetime(self.created_at, "created_at")
        normalized = _provenance(self.provenance, required=self.evidence_tier == "execution_aware")
        object.__setattr__(self, "provenance", normalized)
        normalized_components = dict(self.component_refs or {})
        for role, artifact in normalized_components.items():
            _required_text(role, "component_refs role")
            if not isinstance(artifact, ArtifactRef):
                raise ValueError(f"component_refs.{role} must be an artifact reference")
        object.__setattr__(self, "component_refs", normalized_components)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ResearchRunManifest:
        schema_version = _required_text(payload.get("schema_version"), "schema_version")
        if schema_version != RESEARCH_RUN_MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"unsupported research run manifest schema {schema_version!r}")
        evidence_tier = _required_text(payload.get("evidence_tier"), "evidence_tier")
        if evidence_tier not in RESEARCH_EVIDENCE_TIERS:
            raise ValueError(f"unsupported evidence_tier {evidence_tier!r}")
        clock_payload = payload.get("clock")
        if not isinstance(clock_payload, Mapping):
            raise ValueError("clock must be an object")
        portfolio_payload = payload.get("portfolio_result_ref")
        if not isinstance(portfolio_payload, Mapping):
            raise ValueError("portfolio_result_ref must be an object")
        benchmark_payload = payload.get("benchmark_ref")
        if benchmark_payload is not None and not isinstance(benchmark_payload, Mapping):
            raise ValueError("benchmark_ref must be an object")

        return cls(
            schema_version=schema_version,
            run_id=_required_text(payload.get("run_id"), "run_id"),
            strategy_ref=_required_text(payload.get("strategy_ref"), "strategy_ref"),
            research_purpose=_required_text(payload.get("research_purpose"), "research_purpose"),
            evidence_tier=evidence_tier,
            clock=validate_research_clock(
                clock_payload, require_execution=evidence_tier == "execution_aware"
            ),
            configuration_sha256=_sha256(
                payload.get("configuration_sha256"), "configuration_sha256"
            ),
            producer_versions=_producer_versions(payload.get("producer_versions")),
            data_refs=_artifact_refs(payload.get("data_refs"), "data_refs"),
            signal_refs=_artifact_refs(payload.get("signal_refs"), "signal_refs"),
            portfolio_result_ref=_artifact_ref_from_mapping(
                portfolio_payload, "portfolio_result_ref"
            ),
            benchmark_ref=(
                _artifact_ref_from_mapping(benchmark_payload, "benchmark_ref")
                if isinstance(benchmark_payload, Mapping)
                else None
            ),
            evidence_refs=_artifact_refs(payload.get("evidence_refs", []), "evidence_refs"),
            component_refs=_component_refs(payload.get("component_refs")),
            created_at=_aware_datetime(payload.get("created_at"), "created_at"),
            provenance=_provenance(
                payload.get("provenance"), required=evidence_tier == "execution_aware"
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "strategy_ref": self.strategy_ref,
            "research_purpose": self.research_purpose,
            "evidence_tier": self.evidence_tier,
            "clock": self.clock.to_mapping(),
            "configuration_sha256": self.configuration_sha256,
            "producer_versions": [item.to_mapping() for item in self.producer_versions],
            "data_refs": [item.to_mapping() for item in self.data_refs],
            "signal_refs": [item.to_mapping() for item in self.signal_refs],
            "portfolio_result_ref": self.portfolio_result_ref.to_mapping(),
            "evidence_refs": [item.to_mapping() for item in self.evidence_refs],
            "created_at": self.created_at.isoformat(),
            "provenance": dict(self.provenance or {}),
        }
        if self.benchmark_ref is not None:
            result["benchmark_ref"] = self.benchmark_ref.to_mapping()
        if self.component_refs:
            result["component_refs"] = {
                role: artifact.to_mapping()
                for role, artifact in sorted(self.component_refs.items())
            }
        return result


# ``ResearchRunManifest`` remains the compatibility name; new cross-repository
# producers should use the domain name below without introducing a second schema.
QuantRunManifest = ResearchRunManifest
