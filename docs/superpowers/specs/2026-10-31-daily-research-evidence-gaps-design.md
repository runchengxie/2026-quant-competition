# Daily research evidence-gap report

## Intent and decision

Continue the P0 priority in the Quant-series inspiration audit. Provide a reproducible, offline explanation of why the existing IBKR daily snapshots cannot qualify as research evidence. Reuse existing verification; do not design an owner-authentication system without an identified owner protocol.

The implementation is a small stdlib-only API and CLI in `competition_tools.datasets.research_evidence`. It consumes one explicitly selected v2 daily manifest and its expected SHA256 and produces one new external report. The user approved this design for implementation on 2026-10-31.

## Approaches considered

1. Extend `team data inspect` and its existing coverage report. This would mix coverage and promotion requirements and change a contract used by existing callers. Keep it unchanged.
2. Add a focused research evidence-gap report reusing `verify_daily_manifest`. Recommended for the already selected P0 sequence: US/HK share the same v2 producer and need the same evidence inventory, while existing execution-readiness remains US-specific.
3. Implement a trusted owner adapter immediately. Deferred because current retained receipts do not supply independently authenticated identity, PIT membership, action coverage or holdout governance. Caller-added booleans cannot fill that gap.

The focused report is the approved scope for continued P0 work.

## Existing facts checked on 2026-10-31

At project revision `dff96ec57518e66f6608cebaf78d4f872d708167`, the existing verifier passed both retained `20261021-v2` daily snapshots. US has 66 payload files totaling 1,401,601 bytes; HK has 66 totaling 1,282,377 bytes. Both declare `fixed_current` and `accepted_research=false`. This verifies retained bytes and receipt consistency, not provider authenticity or historical availability. Source locations and exact manifest hashes stay in private evidence records.

`daily_spec.validate_daily_spec` currently permits only IBKR daily, split-adjusted prices and a fixed-current universe. `security_acceptance.audit_pool` audits review attestations and explicitly does not authenticate a provider. `team.execution_readiness` audits manifest metadata for a US execution model, without revalidating all payload files. `experiment_acceptance` blocks every research-evidence request on unsupported owner verification. These APIs remain unchanged.

## Proposed input, output and behavior

- API `audit_daily_research_evidence(manifest_path, expected_sha256)` accepts an absolute external manifest path and a lowercase 64-character SHA256. CLI requires `--manifest`, `--expected-sha256`, and `--output`.
- Support exactly `competition.dataset_manifest.v2` with the current IBKR daily spec. Restore the connection-file placeholder only in a private validation copy if needed to invoke the existing spec validator; never read connection configuration or reconstruct the original spec hash from that placeholder. Existing manifest/receipt consistency checks and exact-byte bindings retain their separate meanings. Other producers, schemas or malformed structures fail with stable errors. Databento remains outside this first implementation.
- Validate paths using existing external/symlink protections. Read JSON with duplicate-key and nonfinite-number rejection using an existing strict reader if its dependencies remain stdlib-only; otherwise use a local JSON loader. Bind the exact manifest and receipt bytes, verify the complete payload inventory through `verify_daily_manifest`, and recheck manifest/receipt digests after verification. This detects observed mutation; it does not promise atomic snapshot isolation.
- Report schema `competition.daily_research_evidence_gap.v1` has exact fields `schema`, `dataset_id`, `version`, `market`, `manifest_sha256`, `receipt_sha256`, `payload_files`, `payload_bytes`, `checks`, `status`, `accepted_research`, `execution_authorized`. Successful reports always have `status=blocked`, `accepted_research=false`, `execution_authorized=false`.
- Checks have exact fields `code` and `status` (`passed` or `blocked`). The fixed check list is `RETAINED_BYTES_VERIFIED` (passed), `POINT_IN_TIME_UNIVERSE_UNVERIFIED`, `HISTORICAL_SECURITY_IDENTITY_UNVERIFIED`, `CORPORATE_ACTION_COVERAGE_UNVERIFIED`, `HISTORICAL_AVAILABILITY_UNVERIFIED`, `OWNER_PROVENANCE_UNVERIFIED`, and `HOLDOUT_GOVERNANCE_UNVERIFIED` (all blocked). The current producer cannot verify these facts; added claim fields or true flags never make them pass. These are research requirements, not a claim that missing artifacts have been exhaustively searched for.
- Output contains no source paths, symbols, raw prices, provider credentials, performance metrics or candidate promotion. A closed JSON Schema documents the contract under `schemas/research/`.
- CLI returns 0 only after completing and saving the blocked inventory; this means the audit ran successfully. Invalid input or integrity errors return 2 with a stable code and no traceback/private path. The distinction is documented, matching existing diagnostic conventions.
- Require a new external output file; reject source-repository paths, input-tree descendants and existing destinations before expensive verification. Publish with exclusive creation, never the existing replacing `write_json` helper. On failure remove only this invocation's incomplete output; preserve all inputs and unrelated files. No directories are moved or retired.

## Evidence follow-up

Reader documentation maps the six blocked requirements to the records needed next: dated stable-security identity mappings, historical universe membership, corporate-action/price-basis coverage, independently evidenced availability, trusted owner publication protocol bound to input bytes, and a separately frozen candidate/holdout/exposure protocol. The first report is dataset-scoped; it cannot determine a strategy's holdout status. Governance therefore remains explicitly unverified, rather than inferred from a date range.

Do not add dependencies, sibling imports, paid requests, research replays, trusted hashes or owner registries. Do not change acceptance behavior, existing evidence contracts, scientific snapshots or broker configuration.

## Validation and implementation boundaries

Write failing tests first for a complete synthetic v2 fixture and the immutable output contract. Then cover payload mutation, receipt/manifest mismatch, unrecorded files, changed expected hash, invalid schema/spec, duplicate JSON keys, nonfinite values, symlinks/unsafe paths, existing output, input-tree output, and attempted claim-based upgrades. Tests must prove an output flag cannot become accepted research. Validate reports against the closed JSON Schema in tests; production remains stdlib-only.

Run focused dataset/acceptance/execution-readiness tests, Ruff, workflow boundaries and required repository CI. The two retained real manifests are used only for read-only verification and generating private reports after synthetic tests pass. Record hashes, code revision, commands, result counts and limitations outside public Git. Never rerun strategy fits or consume a research reservation.

Update the bilingual dataset and research-acceptance guides and the inspiration audit with the new command and its limited evidence stage. Obtain independent review and required checks, merge under standing authorization, verify main and Pages, and clean only this task's branches/worktree. Retain private reports and validation evidence.

Builder discretion covers internal helper names and error-code grouping. Any new producer support, research promotion, owner trust mechanism or broker behavior requires a separate design.
