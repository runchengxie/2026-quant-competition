# Project data directory

[简体中文](data-root-migration.zh-CN.md) · [Team quickstart](team-quickstart.md)

The canonical project directory is `DATA_ROOT/global-market-research`. `DATA_ROOT` still means the workspace data root. Existing installations containing only `DATA_ROOT/2026-quant-competition` continue to use that directory until a recorded migration is completed. Fresh installations use the canonical name.

If both directories exist, default selection fails with `AMBIGUOUS_PROJECT_DATA_ROOT`. Select an exact sibling explicitly through `GLOBAL_MARKET_RESEARCH_DATA_ROOT`, optional workspace TOML `project_data_root`, or a team v2 configuration. Do not merge two directories or use a junction to suppress this error. Input and Gateway reparse protections remain active.

Team v1 retains `schema_version`, `data_root` and `environment_root`; its `data_root` is the workspace root. Team v2 adds `project_data_root`. Create an explicit config with:

```sh
python -m competition_tools.team init --config /absolute/team.toml --data-root /absolute/data --project-data-root /absolute/data/global-market-research
```

Windows uses drive-qualified paths. Initialization remains exclusive and refuses existing configuration. Root orchestration passes the selected root to independently installed research children. The three stdlib storage clients deliberately share the same tested file/environment contract without importing sibling packages; their source parity is checked in CI.

Migration is an inventoried operational change. Record regular-file hashes, links, mutable path settings, scheduled task actions, runtimes and downstream references first. Stop if any required writer or unknown consumer cannot be accounted for. The reviewed local cutover changes location fields only; it does not start tasks, connect to brokers, change triggers/accounts or authorize new downloads.

Historical artifact bytes, `competition.*` schemas, provider identities and scientific protocols retain their old names. A closed `.storage-migration.json` receipt binds the exact old/new sibling roots, `phase="completed"` and the sealed inventory SHA256. Known reservation location fields can then resolve to the preserved relative location without rewriting the receipt. This location mapping provides no data-owner authentication or scientific promotion.

Acquisition authorization and research-reservation writes check both sibling locations under a shared workspace-level lock. Existing or uncertain markers remain consumed regardless of selected root, output path or code changes. An interrupted shared lock blocks further attempts until independently reconciled; it is never automatically treated as a fresh budget.

Retain archived environments and intentionally invalid test links as evidence. A moved environment must be verified or rebuilt before operational use. Source digests change when path clients change: old protocols retain their source snapshots; new research needs a separately frozen source/protocol reservation. See [artifact retention](artifact-retention.md).
