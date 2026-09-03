# Nira target handoff

Nira remains an independent Linux research system. The competition repository
does not import Nira or `research-workspace`; it consumes a versioned file
contract that can be copied to the Windows runner.

## Canonical files

`targets.json` must match `schemas/targets.schema.json`:

```json
{
  "schema_version": "1.0",
  "strategy_id": "japanese-nira",
  "market": "JP",
  "as_of": "2026-09-03T00:00:00Z",
  "targets": [{"symbol": "1321.T", "weight": "1.0", "quantity": "1"}]
}
```

`lineage.json` is a JSON object containing the research provenance, for
example the Nira revision, signal artifact, data snapshot and run ID. The
handoff preserves its fields without interpreting research-specific paths.
If `lineage.json` is next to `targets.json`, the loader discovers it by
convention; an explicit path is preferred when files are transferred between
machines. When lineage is both embedded and supplied by an explicit or sibling
file, both sources are read. They are accepted only when their canonical JSON
values are identical (object key order does not matter); conflicting sources
are rejected before the target can reach execution.

## Linux producer / Windows consumer

The Linux process can construct a `NiraTargetHandoff` from its already-exported
Python dictionaries and call `write_target_artifact`. The Windows runner can
then validate the copied files before creating any order intent:

```powershell
$env:PYTHONPATH = "."
python -m strategies.nira.handoff validate `
  --targets .\artifacts\targets.json `
  --lineage .\artifacts\lineage.json
```

To publish normalized copies into a run directory, use `export` with explicit
output paths. Existing files are not overwritten unless `--overwrite` is
provided. Publication has the following transaction semantics:

1. Both JSON documents are fully serialized and flushed to temporary files in
   their respective destination directories before either destination changes.
2. Existing destination files are copied to same-directory recovery backups
   before replacement.
3. Each destination is replaced atomically at the file level. If any replace
   fails, every destination already changed by that call is removed (for a new
   publication) or restored from its backup (for an overwrite), and the
   original error is raised.
4. Temporary files and successful recovery backups are removed. If rollback
   itself cannot restore a destination, the surviving backup is retained and
   its path is included in `HandoffValidationError` for manual recovery.

This provides failure rollback for the pair but is not a lock-free atomic
snapshot for concurrent readers: there is a short interval between the two
file replacements. Producers should publish into a run-specific directory and
only hand that completed directory to the Windows consumer after this function
returns successfully. Target and lineage files must still be transferred
together as one versioned handoff.

The loader validates the target payload through `packages.contracts.TargetSet`.
It rejects malformed JSON, non-object lineage, market or strategy mismatches,
duplicate symbols, invalid quantities and unsupported symbols before the
execution layer sees the artifact.
