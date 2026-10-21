# Run the offline team demo

[简体中文](team-quickstart.zh-CN.md)

Clone this repository and install Python 3.12 and `uv`. Default offline setup needs no `quant-*` checkout, framework package, broker connection or provider credentials. Run these commands from the repository root, replacing absolute paths with external directories you own. Windows paths such as `D:/data/team-demo` are supported.

Create and activate an external bootstrap environment first. On Windows PowerShell:

```powershell
$bootstrap = 'D:/data/team-bootstrap'
uv venv $bootstrap --python 3.12
uv pip install --python "$bootstrap/Scripts/python.exe" --no-deps -e .
& "$bootstrap/Scripts/Activate.ps1"
```

On POSIX shells:

```sh
uv venv /absolute/data/team-bootstrap --python 3.12
uv pip install --python /absolute/data/team-bootstrap/bin/python --no-deps -e .
. /absolute/data/team-bootstrap/bin/activate
```

The root package has no default runtime dependencies. The former root `team.py` wrapper has been removed. Use the module entry in the activated environment:

```sh
python -m competition_tools.team --help
python -m competition_tools.team init --config /absolute/private/team.toml --data-root /absolute/data/team-demo
python -m competition_tools.team setup --config /absolute/private/team.toml --profile offline
python -m competition_tools.team doctor --config /absolute/private/team.toml
python -m competition_tools.team demo equity --config /absolute/private/team.toml --output-root /absolute/data/equity-demo-001
python -m competition_tools.team demo crypto --config /absolute/private/team.toml --output-root /absolute/data/crypto-demo-001
```

`init` creates a new `competition.team.v1` TOML file and refuses overwrites. Exact keys are `schema_version`, `data_root` and `environment_root`. Environments default to `<data_root>/2026-quant-competition/environments`; override with `init --environment-root`. All paths must be absolute and outside Git checkouts, including linked worktrees and symlinks to source. Files receive current-user ACLs on Windows or mode `0600` on POSIX. Configuration contains paths, not credentials. See [the template](../../config/team.example.toml).

`setup` uses committed locks for separate `root`, `equity-lab` and `crypto-mm` environments. Child processes clear inherited `PYTHONPATH` and `PYTHONHOME` and receive explicit `DATA_ROOT`. No sibling checkout is searched. The installed module entry is `python -m competition_tools.team`. An editable installation retains its source location. For a wheel or other non-editable installation, pass `setup --repository-root /absolute/checkout/2026-quant-competition` explicitly.

`doctor` checks interpreter file existence locally. It does not validate dependency integrity, credentials, entitlements or strategy readiness. Using the installed root environment, `python -m competition_tools.check_team_delivery --config FILE` separately inspects installed distribution names for framework dependencies. Neither command imports providers or authenticates.

Each demo requires a new external output directory. It runs existing leaf commands, keeps child logs under `logs/` and writes `team-run.json` with `synthetic: true`. Failed/interrupted runs retain their partial directory for inspection; retry with a new destination. Equity uses `equal_weight`. Crypto generates fictional order books, trades and funding, audits them, then replays `B0` for `2026-03-19`. These examples validate software and do not measure investment performance.

Commands emit `competition.team_result.v1` JSON with `action`, `status`, `issue_codes`, `projects` and `synthetic`. Exit `0` means completed; `2` means blocked or failed. Envelopes exclude raw child logs and private paths. Local logs can contain paths, so review them before sharing. `synthetic` is true for demos and null for other actions.

## Optional profiles and validation

`setup --profile framework` installs only the separately locked [accounting package](../research/accounting-comparison.md), with a local ledger and no external framework packages. The profile name is retained for compatibility. `setup --profile broker-data` installs the root `ibkr` extra without logging in or submitting orders. `setup --profile website` requires Node.js 24/npm and runs `npm ci` for `site`. These explicit profiles are excluded from offline setup.

Default CI tests root and both leaves and runs team demos without framework dependencies. Separate `platform-comparison.yml` validates adapter/accounting changes and supports manual runs. See [development checks](../../README.md#development-checks). Input acceptance, provenance limits and execution safety rules still apply. This entry does not download full-market datasets, register strategies, connect research to orders or activate Gateway automation. The historical public result snapshot is unchanged.

New code under `src/competition_tools/team/` uses its scoped MIT `LICENSE`. Existing root code and third-party packages retain their licensing.

Use the explicit `run international` or optional `run next-open` command for [international experiments](../research/international-experiments.md).
## Data acquisition and retrospective evaluation

Use [dataset preparation](../research/datasets.md) for the separate external specification, budget caps, immutable receipts and actual provider support. `python -m competition_tools.team data plan`, `data acquire` and `data inspect` preserve the team configuration schema. `python -m competition_tools.team evaluate` dispatches only the daily crypto matrix in its own environment; equity and maker matrices use their existing APIs. See [new evidence and limitations](../research/data-expansion-and-evaluation.md). Gateway startup is off by default. Explicit IBKR acquisition can opt into the [Paper login precondition](gateway-login.md#optional-data-task-login-precondition); no command here submits orders.

For separate Paper account-prefix, contract and optional historical-read evidence, use [read-only acceptance](gateway-login.md#read-only-acceptance). This command requires no team configuration and never logs in or submits orders.

The optional `daily-data` profile installs locked Paper daily collection and exchange-calendar dependencies. See [bounded daily snapshots](../research/datasets.md#bounded-daily-equity-snapshots) for v2 specifications and immutable refresh; it does not log into Gateway.
