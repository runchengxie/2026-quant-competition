# Paper Gateway login helper

[简体中文](gateway-login.zh-CN.md)

This Windows helper validates a separately installed IBC release and prepares a private Paper-only launcher. It supports manual mobile authentication. It does not log in during `check`, `dry-run` or `status`. These commands do not probe an API or historical-data service. Their `authentication`, `api` and `historical_data` fields remain `not_checked`. A running Gateway or any Java process blocks preflight conservatively.

This is IB Gateway and its TWS API, not Client Portal Gateway. No order call is present. `ReadOnlyLogin=no` preserves normal authentication. `ReadOnlyApi=yes` enforces the intended API setting. Neither proves the connected account or runtime configuration before a supervised test.

## Prerequisites and limits

Use Windows, PowerShell 7, Python 3.12 and a stable installation of this repository's root package. IBC upstream was [archived in September 2026](https://github.com/IbcAlpha/IBC). The pinned [Windows release 3.24.2](https://github.com/IbcAlpha/IBC/releases/tag/3.24.2) has SHA256 `ba8e95f61f3c7c252620baef41e550c6aab98f6034179156e11a9a1623fdd892`. Retain its archive and an unmodified extracted directory outside source. The helper verifies every extracted file against this archive, including scripts and JARs. It does not download or install anything.

Gateway major version `1050` is the only accepted layout. Its separately reviewed local executable SHA256 must be configured. Directory/version/hash checks do not establish compatibility with IBC. Actual authentication, account identity, API read-only behavior and historical data remain unverified until supervised deployment. Use the offline Gateway distribution with the required JARs and bundled Java runtime. The helper does not validate every Gateway library.

The [upstream Windows launcher](https://github.com/IbcAlpha/IBC/blob/3.24.2/resources/StartGateway.bat) has mutable startup variables. Its service script also retries some failures and renames installation executables. `prepare` creates a private derivative runtime from the verified archive, removes restart jumps and the executable-renaming section, and configures Paper mode, separate settings and private logs. The original archive and installation stay unchanged. Each subsequent check verifies the generated runtime bytes. Unrecognized upstream layouts fail closed. Derived IBC files remain third-party GPL material, outside this repository.

This bounded launcher disables automatic restarts. [Official restart guidance](https://www.ibkrguides.com/traderworkstation/auto-restart-considerations.htm) describes daily reuse and weekly authentication constraints. That is a separate rollout. Mobile confirmation and expired-session renewal still require a person. There is no MFA retry loop or session takeover.

## Private configuration

Pass the machine-local `workspace.toml` explicitly. It defines `code_root`, `data_root` and `config_root`. The helper uses `tomllib` and does not discover credential stores. Under those resolved roots use:

| Purpose | Location |
| --- | --- |
| Launcher JSON, private INI, separate settings, generated launcher/runtime | `CONFIG_ROOT/deployments/2026-quant-competition/ibgateway-paper/` |
| Original IBC archive and extracted release | An external owner-protected tools directory |
| Logs | `DATA_ROOT/2026-quant-competition/operations/ibgateway-paper/` |

Copy [launcher.example.json](../../config/ibgateway-paper/launcher.example.json) and [ibc.example.ini](../../config/ibgateway-paper/ibc.example.ini) privately. Replace every placeholder with an absolute path. Keep `activation_authorized=false`, `retry_limit=0` and a timeout of 30–300 seconds. Credentials are omitted from source templates. If desired, enter `IbLoginId` and `IbPassword` only in the private INI yourself. Never put them in launcher JSON, shell arguments, task XML or a chat. Empty credentials leave manual entry to the Gateway UI.

The INI must explicitly set Paper, API read-only, normal login, no FIX, a manual or secondary existing-session policy and no relogin after MFA timeout. The MFA exit interval must be positive and no greater than the configured timeout. Automatic restart times, remote command-server access, `IbDir` and trusted-IP overrides are rejected. Duplicate keys, relative paths, reparse points and batch metacharacters in paths are rejected. Paths containing parentheses are unsupported by this launcher.

Before storing secrets, restrict the deployment directory, INI, settings, logs and tool paths to your Windows owner SID and optional SYSTEM. The helper checks allow entries and owner identity, including inherited ACL entries. It never repairs ACLs during a check. For a newly created, empty directory you own, review the following in PowerShell before using it:

```powershell
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
icacls $privateDirectory /inheritance:r /grant:r "*${ownerSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F'
icacls $privateDirectory
```

`/grant:r` replaces grants for the named identities only. Remove any remaining unrelated allow entries after reviewing them, then recheck. Apply the same owner protection to the directory's existing files as needed. Do not run this against unrelated folders or an active shared Gateway installation. Logs are private diagnostics and must not be published.

## Non-launching checks

Use an explicit Python executable from a stable installed root environment. Help requires no private configuration:

```powershell
& $pythonPath -m competition_tools.gateway_launcher --help
& $pythonPath -m competition_tools.gateway_launcher check --config $launcherJson --workspace $workspaceToml
& $pythonPath -m competition_tools.gateway_launcher dry-run --config $launcherJson --workspace $workspaceToml
& $pythonPath -m competition_tools.gateway_launcher status --config $launcherJson --workspace $workspaceToml
```

All three commands validate local prerequisites without writing files, launching Gateway, changing settings or opening a socket. `preflight_passed` is a configuration result only. Missing files produce `REQUIRED_PATH_MISSING`; unsafe permissions produce `UNSAFE_ACL`; an existing Gateway/Java process produces `EXISTING_GATEWAY_OR_JAVA`. Errors use stable codes without input paths or INI values. No successful local installation/login is implied by these examples.

When separately preparing a deployment, `prepare` creates the previously absent configured launcher and its `runtime/` directory. It refuses to overwrite them. Review partial preparation after an error manually. The source includes no install, stop, restart or cleanup command.

## Separate supervised activation

Activation requires the user's approval to install IBC, privately enter credentials and replace the current Gateway. Preserve manual startup. Prepare only a reviewed deployment and set `activation_authorized=true` after that approval. Run the stable deployed wrapper in an existing desktop session:

```powershell
& $deployedWrapper -Action start -PythonPath $pythonPath -ConfigPath $launcherJson -WorkspacePath $workspaceToml
```

The wrapper revalidates the specification before starting the hidden console helper. The Gateway UI remains available. Complete mobile authentication manually. Child output stays in owner-protected log files. Exit codes are propagated. An observation timeout returns code 3 without killing or restarting the child, and does not establish whether authentication succeeded. Check the private desktop before any later attempt. Confirm Paper identity and read-only API locally, then test historical data independently. No orders are authorized.

`Export-PaperGatewayTask` in `operations/windows/PaperGateway.psm1` can write an unregistered, disabled task XML artifact for review. It requires explicit stable absolute paths and an owner SID. It uses `InteractiveToken`, `LeastPrivilege`, a six-minute task limit and no retry policy. It must reference a stable deployed wrapper, never a worktree. It does not register or enable a task. A logged-on desktop is required. Automatic Windows login and stored task passwords are unsupported.

Rollback is manual: disable only a separately approved scheduled task, stop the helper through the normal UI with user approval, and return to the unchanged manual Gateway startup. Do not remove shared tools, credentials or settings automatically.

## Verification

Linux CI runs the pure Python contracts. The dedicated Windows job also runs native PowerShell tests with synthetic children, covering non-launching checks, redaction, interactive-session gating, private output and child failures. Tests do not install IBC, authenticate an account or call broker orders. These remain deployment checks. See [release checks](release-checks.md).
