"""Broker-neutral handoff for targets produced by the external Nira system.

The execution repository deliberately consumes files rather than importing
Nira or research-workspace.  The canonical handoff is a contract-compatible
``targets.json`` plus an optional sibling ``lineage.json``.  For convenience,
``lineage`` may also be embedded in the target file or in a small envelope.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.contracts import TargetSet, TargetValidationError


class HandoffValidationError(ValueError):
    """Raised when a Nira handoff cannot be safely consumed."""


@dataclass(frozen=True, slots=True)
class NiraTargetHandoff:
    """Validated target set and the lineage metadata that produced it."""

    target_set: TargetSet
    lineage: dict[str, Any]
    target_path: Path | None = None
    lineage_path: Path | None = None

    @classmethod
    def from_payload(
        cls,
        target_payload: Mapping[str, Any],
        lineage: Mapping[str, Any] | None = None,
        *,
        target_path: Path | None = None,
        lineage_path: Path | None = None,
    ) -> NiraTargetHandoff:
        """Build a handoff from wire payloads and validate its target contract."""

        if not isinstance(target_payload, Mapping):
            raise HandoffValidationError("target payload must be an object")
        if lineage is not None and not isinstance(lineage, Mapping):
            raise HandoffValidationError("lineage must be an object")

        target_data, embedded_lineage = _extract_target_and_lineage(target_payload)
        resolved_lineage = _resolve_lineage_sources(
            ("embedded", embedded_lineage),
            ("provided", lineage),
        ) or {}
        _validate_lineage_consistency(resolved_lineage, target_data)

        try:
            target_set = TargetSet.from_dict(target_data)
        except TargetValidationError as exc:
            raise HandoffValidationError(str(exc)) from exc

        return cls(
            target_set=target_set,
            lineage=resolved_lineage,
            target_path=target_path,
            lineage_path=lineage_path,
        )

    def to_target_dict(self) -> dict[str, Any]:
        """Return only the schema-compatible target payload."""

        return self.target_set.to_dict()

    def to_lineage_dict(self) -> dict[str, Any]:
        """Return a copy of lineage metadata without execution-side additions."""

        return dict(self.lineage)


def load_target_artifact(
    targets_path: str | os.PathLike[str],
    *,
    lineage_path: str | os.PathLike[str] | None = None,
) -> NiraTargetHandoff:
    """Load and validate an external target artifact.

    ``targets_path`` may contain a raw target contract, a contract with an
    embedded ``lineage`` object, or ``{"target_set": ..., "lineage": ...}``.
    If no lineage is embedded and the conventional sibling ``lineage.json``
    exists, it is consumed automatically.  Missing lineage is represented by
    an empty mapping so older target-only producers remain readable.
    """

    target_file = Path(targets_path)
    target_payload = _read_json_object(target_file, "target payload")
    target_data, embedded_lineage = _extract_target_and_lineage(target_payload)

    selected_lineage_path = Path(lineage_path) if lineage_path is not None else None
    if selected_lineage_path is None:
        conventional_path = target_file.with_name("lineage.json")
        if conventional_path.is_file():
            selected_lineage_path = conventional_path

    external_lineage = None
    if selected_lineage_path is not None:
        external_lineage = _read_json_object(selected_lineage_path, "lineage")

    resolved_lineage = _resolve_lineage_sources(
        ("embedded", embedded_lineage),
        ("external", external_lineage),
    )

    return NiraTargetHandoff.from_payload(
        target_data,
        resolved_lineage,
        target_path=target_file,
        lineage_path=selected_lineage_path,
    )


def write_target_artifact(
    handoff: NiraTargetHandoff,
    targets_path: str | os.PathLike[str],
    *,
    lineage_path: str | os.PathLike[str] | None = None,
    overwrite: bool = False,
) -> tuple[Path, Path | None]:
    """Publish normalized target and lineage files as a recoverable pair.

    Existing files are protected by default because target and lineage files
    are execution evidence.  Set ``overwrite=True`` only when intentionally
    publishing a replacement artifact.  Both files are staged before either
    destination is changed.  If publication fails, destinations already
    changed by this call are removed or restored from same-directory backups.
    """

    if not isinstance(handoff, NiraTargetHandoff):
        raise TypeError("handoff must be a NiraTargetHandoff")

    target_file = Path(targets_path)
    lineage_file = Path(lineage_path) if lineage_path is not None else None
    if lineage_file is None and handoff.lineage:
        lineage_file = target_file.with_name("lineage.json")
    if lineage_file is not None and lineage_file == target_file:
        raise HandoffValidationError("target and lineage paths must be different")
    if lineage_file is not None and not handoff.lineage:
        raise HandoffValidationError(
            "lineage output path was provided but lineage metadata is empty"
        )
    if not overwrite:
        existing = [path for path in (target_file, lineage_file) if path and path.exists()]
        if existing:
            raise FileExistsError(
                "refusing to overwrite existing artifact: "
                + ", ".join(str(path) for path in existing)
            )

    publications = [(target_file, handoff.to_target_dict())]
    if lineage_file is not None:
        publications.append((lineage_file, handoff.to_lineage_dict()))
    _publish_json_files(publications)
    return target_file, lineage_file


def _extract_target_and_lineage(
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], Mapping[str, Any] | None]:
    envelope_lineage: Mapping[str, Any] | None = None
    has_envelope_lineage = "lineage" in payload
    if "target_set" in payload:
        unknown = set(payload) - {"target_set", "lineage"}
        if unknown:
            raise HandoffValidationError(
                f"unknown handoff field: {sorted(unknown)!r}"
            )
        raw_target = payload["target_set"]
        if not isinstance(raw_target, Mapping):
            raise HandoffValidationError("target_set must be an object")
        target_data = dict(raw_target)
        if has_envelope_lineage:
            envelope_lineage = payload["lineage"]
            if not isinstance(envelope_lineage, Mapping):
                raise HandoffValidationError("lineage must be an object")
    else:
        target_data = dict(payload)

    has_embedded_lineage = "lineage" in target_data
    embedded_lineage = target_data.pop("lineage", None)
    if has_embedded_lineage and not isinstance(embedded_lineage, Mapping):
        raise HandoffValidationError("lineage must be an object")
    resolved_lineage = _resolve_lineage_sources(
        ("envelope", envelope_lineage),
        ("embedded", embedded_lineage if has_embedded_lineage else None),
    )
    return target_data, resolved_lineage


def _resolve_lineage_sources(
    *sources: tuple[str, Mapping[str, Any] | None],
) -> dict[str, Any] | None:
    resolved: dict[str, Any] | None = None
    canonical: str | None = None
    resolved_label: str | None = None
    for label, source in sources:
        if source is None:
            continue
        source_canonical = _canonical_json(source)
        if canonical is not None and source_canonical != canonical:
            raise HandoffValidationError(
                f"conflicting lineage sources: {resolved_label} and {label}"
            )
        if resolved is None:
            resolved = dict(source)
            canonical = source_canonical
            resolved_label = label
    return resolved


def _canonical_json(payload: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise HandoffValidationError("lineage must contain JSON values") from exc


def _validate_lineage_consistency(
    lineage: Mapping[str, Any], target_data: Mapping[str, Any]
) -> None:
    try:
        json.dumps(lineage, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise HandoffValidationError("lineage must contain JSON values") from exc

    strategy_id = lineage.get("strategy_id")
    target_strategy_id = target_data.get("strategy_id")
    if strategy_id is not None and strategy_id != target_strategy_id:
        raise HandoffValidationError("lineage strategy_id does not match target strategy_id")

    market = lineage.get("market")
    target_market = target_data.get("market")
    if market is not None and market != target_market:
        raise HandoffValidationError("lineage market does not match target market")


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HandoffValidationError(f"cannot read {label}: {path}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HandoffValidationError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(payload, Mapping):
        raise HandoffValidationError(f"{label} must be an object")
    return dict(payload)


def _publish_json_files(
    publications: list[tuple[Path, Mapping[str, Any]]],
) -> None:
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path | None] = {}
    published: list[Path] = []
    retained_backups: set[Path] = set()
    try:
        for path, payload in publications:
            staged[path] = _stage_json(path, payload)
        for path, _ in publications:
            backups[path] = _backup_file(path) if path.exists() else None
        for path, _ in publications:
            os.replace(staged[path], path)
            del staged[path]
            published.append(path)
    except BaseException as publish_error:
        rollback_errors: list[tuple[Path, OSError]] = []
        for path in reversed(published):
            backup = backups.get(path)
            try:
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    os.replace(backup, path)
                    backups[path] = None
            except OSError as rollback_error:
                rollback_errors.append((path, rollback_error))
        if rollback_errors:
            retained_backups = {
                backup
                for path, _ in rollback_errors
                if (backup := backups.get(path)) is not None
            }
            recovery_paths = [
                str(backup)
                for backup in retained_backups
                if backup.exists()
            ]
            details = ", ".join(str(path) for path, _ in rollback_errors)
            recovery = ", ".join(recovery_paths) or "none"
            raise HandoffValidationError(
                "artifact publication failed and rollback was incomplete for "
                f"{details}; retained recovery backups: {recovery}"
            ) from publish_error
        raise
    finally:
        _remove_files(staged.values())
        _remove_files(
            backup
            for backup in backups.values()
            if backup is not None and backup not in retained_backups
        )


def _stage_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return temporary_path
    except BaseException:
        if temporary_path is not None:
            _remove_files([temporary_path])
        raise


def _backup_file(path: Path) -> Path:
    backup_path: Path | None = None
    try:
        with path.open("rb") as source, tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".bak",
            delete=False,
        ) as destination:
            backup_path = Path(destination.name)
            shutil.copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        return backup_path
    except BaseException:
        if backup_path is not None:
            _remove_files([backup_path])
        raise


def _remove_files(paths: Iterable[Path]) -> None:
    for path in list(paths):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and publish Nira target artifacts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate targets and lineage")
    _add_input_arguments(validate)

    export = subparsers.add_parser("export", help="validate and atomically publish normalized files")
    _add_input_arguments(export)
    export.add_argument("--output-targets", required=True, type=Path)
    export.add_argument("--output-lineage", type=Path)
    export.add_argument("--overwrite", action="store_true")
    return parser


def _add_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--lineage", type=Path)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        handoff = load_target_artifact(args.targets, lineage_path=args.lineage)
        if args.command == "export":
            write_target_artifact(
                handoff,
                args.output_targets,
                lineage_path=args.output_lineage,
                overwrite=args.overwrite,
            )
            print(f"wrote validated targets: {args.output_targets}")
            if args.output_lineage:
                print(f"wrote lineage: {args.output_lineage}")
        else:
            print(
                json.dumps(
                    {
                        "status": "valid",
                        "strategy_id": handoff.target_set.strategy_id,
                        "market": handoff.target_set.market.value,
                        "as_of": handoff.target_set.as_of.isoformat(),
                        "target_count": len(handoff.target_set.targets),
                        "lineage_fields": sorted(handoff.lineage),
                    },
                    ensure_ascii=False,
                )
            )
    except (HandoffValidationError, FileExistsError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
