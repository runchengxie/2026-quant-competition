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
machines.

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
provided. Each file is written through a same-directory temporary file and an
atomic replace; the target and lineage files should still be treated as one
versioned handoff and transferred together.

The loader validates the target payload through `packages.contracts.TargetSet`.
It rejects malformed JSON, non-object lineage, market or strategy mismatches,
duplicate symbols, invalid quantities and unsupported symbols before the
execution layer sees the artifact.
