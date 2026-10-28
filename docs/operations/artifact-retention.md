# Retaining task artifacts

[简体中文](artifact-retention.zh-CN.md) · [Documentation](../README.md)

Close each task with an explicit inventory under configured `DATA_ROOT/2026-quant-competition/retention/<review-date>/`. Keep the inventory private. Public Git contains this policy and reproduction instructions, never private artifacts, machine paths or strategy parameters. Resolve workspace roots from the explicitly supplied workspace configuration or environment; a task worktree uses the owning repository's permanent data root.

## Retention decisions

| Class | Default decision | Evidence required |
| --- | --- | --- |
| Original inputs and acquisition receipts | Retain | Preserve provenance and the authoritative owner; shared data stays with its provider |
| Versioned research outputs, protocols, manifests and ledgers | Retain | Preserve versions and the input/output relationship, including superseded results |
| Validation logs, acceptance evidence and recovery materials | Retain | Keep delivery records and everything needed to interpret or restore retained evidence |
| Broker environments and operational state | Retain | Separate operational review; this policy grants no broker or production changes |
| Unknown contents or an unresolved consumer | Retain pending review | Record the unknown and a next review trigger; names and age do not prove completion |
| Task-only virtual environments and locked frontend dependencies | Conditional retirement candidate | Task completion evidence, owner commit, lockfile, rebuild command, package/version record and checks below |
| Genuine task-only uv cache | Conditional retirement candidate | Establish actual uv cache ownership and scope, then check consumers and use supported uv maintenance commands |

A directory named `cache` can contain inputs or unique research evidence. Never classify it as disposable by name. A task's merge or dated directory alone does not establish that its artifacts have no consumers. Current research environments and broker-related environments remain retained until a separate review establishes otherwise.

## Task closeout

1. Record task ID, owning repository and commit, completion evidence, artifact paths, category, decision, rationale, consumer references and review trigger. For rebuildable dependencies, record the lockfile identity and exact setup command before considering retirement.
2. Inventory links, junctions, manifests and `current`/`latest` aliases, including ordinary files with those names. Resolve their targets and downstream references. Never traverse an unknown link for cleanup; an unresolved reference means retain.
3. Before dependency retirement, check running processes, scheduled tasks, launchers, active worktrees and downstream users. Record the time and scope of these checks. Unavailable or incomplete checks mean retain pending review. Do not stop processes or change jobs as part of inventory.
4. Keep retained evidence separate from rebuildable dependencies in future task directories. Use task-specific output paths; publish shared pointers only through the coordinated publication workflow. Create no duplicate authoritative datasets.
5. Record any separately authorized retirement with exact paths, before/after results and rebuild instructions. Update the private inventory, preserving prior receipts. Retention review itself performs no deletion, relocation, automated expiry or scheduling.

Use a small CSV or JSON inventory plus a short report. Suggested fields are `path`, `owner_commit`, `category`, `decision`, `basis`, `consumers`, `rebuild`, `unknowns`, `review_trigger`, and `reviewed_at`. A review trigger can be task acceptance, a consumer migration or the next reproduction request; it is never an automatic deletion date. Keep a root-level inventory covering all top-level entries and a task-level inventory with explicit exceptions. Directory-level retention covers descendants unless a separately reviewed exception says otherwise.

The private report should distinguish observed facts, prior cleanup receipts and unresolved questions. Do not re-delete already retired dependencies or infer current state solely from an old receipt. This policy adds no trading or research behavior and establishes no live-broker readiness.
