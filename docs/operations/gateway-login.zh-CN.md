# Paper Gateway 登录辅助脚本

[English](gateway-login.md)

这套 Windows 脚本检查单独安装的 IBC，并准备私有的 Paper 启动器。手机二次验证仍由人完成。`check`、`dry-run` 和 `status` 只检查本地配置，不登录、不连接 API 或历史行情服务。返回的 `authentication`、`api` 和 `historical_data` 均为 `not_checked`。发现正在运行的 Gateway 或任何 Java 进程时，检查会保守地阻止启动。

这里使用的是 IB Gateway 及其 TWS API，与 Client Portal Gateway 不同。脚本没有下单调用。`ReadOnlyLogin=no` 保留正常登录验证，`ReadOnlyApi=yes` 指定只读 API。真正连接的账户身份和运行时设置，仍需在有人监督的部署测试中确认。

## 环境和限制

需要 Windows、PowerShell 7、Python 3.12，以及稳定安装的本仓库根包。IBC 上游已于 [2026 年 9 月归档](https://github.com/IbcAlpha/IBC)。固定使用 [Windows 3.24.2](https://github.com/IbcAlpha/IBC/releases/tag/3.24.2)，压缩包 SHA256 为 `ba8e95f61f3c7c252620baef41e550c6aab98f6034179156e11a9a1623fdd892`。请在源码目录外保留原始压缩包和未经修改的解压目录。检查会逐一比较脚本、JAR 等文件的字节。辅助脚本不会下载或安装软件。

仅接受 Gateway 主版本 `1050` 的目录结构，并要求配置经过本地审查的可执行文件 SHA256。目录、版本和哈希检查不代表 IBC 兼容性已经验证。真实登录、Paper 账户身份、API 只读行为和历史行情仍需单独测试。应使用包含所需 JAR 和 Java 运行环境的离线 Gateway 安装。本脚本不校验 Gateway 的每一个库。

[上游 Windows 启动脚本](https://github.com/IbcAlpha/IBC/blob/3.24.2/resources/StartGateway.bat) 包含可修改的变量，服务脚本还会重试某些失败并重命名安装文件。`prepare` 从已校验的压缩包生成私有运行副本，移除重启跳转和可执行文件重命名段，指定 Paper、独立设置目录和私有日志。原始压缩包和安装目录保持原样。之后每次检查都会校验生成文件，无法识别的上游结构会被拒绝。生成的 IBC 文件仍属于第三方 GPL 内容，存放在本仓库外。

这套有界启动器禁用自动重启。[IBKR 官方重启说明](https://www.ibkrguides.com/traderworkstation/auto-restart-considerations.htm) 涉及每日会话复用和每周重新验证，需另行部署测试。手机确认和过期登录仍需要人处理。脚本不循环发送验证请求，也不接管其他会话。

## 私有配置

必须显式传入本机 `workspace.toml`。其中定义 `code_root`、`data_root` 和 `config_root`，使用 `tomllib` 读取，不搜索凭据存储。按这些根目录配置：

| 用途 | 位置 |
| --- | --- |
| 启动 JSON、私有 INI、独立设置、生成的启动器和运行副本 | `CONFIG_ROOT/deployments/2026-quant-competition/ibgateway-paper/` |
| 原始 IBC 压缩包和解压目录 | 源码外、由当前用户保护的工具目录 |
| 日志 | `DATA_ROOT/2026-quant-competition/operations/ibgateway-paper/` |

将 [launcher.example.json](../../config/ibgateway-paper/launcher.example.json) 和 [ibc.example.ini](../../config/ibgateway-paper/ibc.example.ini) 复制到私有目录，替换所有绝对路径占位符。保留 `activation_authorized=false`、`retry_limit=0`，超时设为 30–300 秒。源码模板不含登录凭据。如需自动填入，请自行在私有 INI 中添加 `IbLoginId` 和 `IbPassword`，不要写入启动 JSON、命令行、任务 XML 或聊天。未配置凭据时，在 Gateway 界面手动输入。

INI 必须明确指定 Paper、只读 API、正常登录、关闭 FIX、手动或 secondary 会话策略，以及二次验证超时后不重新登录。配置中的 MFA 退出间隔必须为正数且不大于观察超时。禁用重新登录后，上游可能不使用这个退出间隔；包装脚本只限制观察时长，不保证结束 Gateway。禁止设置自动重启时间、远程命令服务、`IbDir` 和可信 IP 覆盖项。只接受模板中的设置，以及名称完全匹配的 `IbLoginId`、`IbPassword`、`FIXLoginId`、`FIXPassword`。IBC 按 Java Properties 语法解析并记录未知字段，因此拒绝未知字段、转义或不规范的键、续行和重复键。也拒绝相对路径、重解析点和批处理元字符路径。本启动器不支持含圆括号的路径。

保存秘密前，请把部署目录、INI、设置、日志和工具路径的允许访问权限限制为当前 Windows 用户 SID 和可选的 SYSTEM。检查包含继承权限的允许条目和所有者，不在检查过程中自动修复 ACL。对于自己新建的空目录，可先审查下面的 PowerShell 示例：

```powershell
$ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
icacls $privateDirectory /inheritance:r /grant:r "*${ownerSid}:(OI)(CI)F" '*S-1-5-18:(OI)(CI)F'
icacls $privateDirectory
```

`/grant:r` 只替换指定身份的授权。审查后移除其他允许条目，再次检查。已有文件也需按实际情况限制权限。不要对无关目录或正在使用的共享 Gateway 安装执行这些操作。日志属于私有诊断内容，不能公开发布。

## 不启动进程的检查

显式指定稳定安装的根项目环境中的 Python。帮助命令不需要私有配置：

```powershell
& $pythonPath -m competition_tools.gateway_launcher --help
& $pythonPath -m competition_tools.gateway_launcher check --config $launcherJson --workspace $workspaceToml
& $pythonPath -m competition_tools.gateway_launcher dry-run --config $launcherJson --workspace $workspaceToml
& $pythonPath -m competition_tools.gateway_launcher status --config $launcherJson --workspace $workspaceToml
```

后三条命令只验证本地前提，不写文件、不启动 Gateway、不修改设置、不打开网络连接。`preflight_passed` 只表示配置检查通过。缺少文件返回 `REQUIRED_PATH_MISSING`，权限不安全返回 `UNSAFE_ACL`，已有 Gateway 或 Java 进程返回 `EXISTING_GATEWAY_OR_JAVA`。错误只包含稳定代码，不包含输入路径或 INI 值。示例不代表本机已安装或登录成功。

另行准备部署时，`prepare` 会新建配置后的启动器和 `runtime/` 目录，拒绝覆盖已有内容。出错后需手动审查可能留下的部分文件。源码不提供安装、停止、重启或清理命令。

## 单独确认后启用

实际安装 IBC、填写凭据以及替换当前 Gateway，需要用户另行同意。保留手动启动方式。只在审查过的部署中准备文件，并在获得启用授权后设置 `activation_authorized=true`。在已经登录的桌面会话里调用稳定部署的脚本：

```powershell
& $deployedWrapper -Action start -PythonPath $pythonPath -ConfigPath $launcherJson -WorkspacePath $workspaceToml
```

脚本先在私有日志目录独占创建 `launch.lease`，持锁重新检查配置，再启动隐藏的控制台辅助进程，Gateway 自身的界面仍供用户完成验证。子进程输出仅写入受保护的日志，退出码会传递给调用方。观察超时返回代码 3，不结束或重启子进程，也不推断认证成功与否。超时或无法确定启动结果时会保留 `launch.lease`，阻止再次启动。请先人工检查私有桌面和进程状态，再手动删除这一份锁文件。子进程正常退出时会释放锁。请在本地确认 Paper 身份及 API 只读，再分别检查历史行情。这里没有下单授权。

`operations/windows/PaperGateway.psm1` 中的 `Export-PaperGatewayTask` 可生成未注册、默认禁用的任务 XML，供审查使用。需要显式的稳定绝对路径和用户 SID，使用 `InteractiveToken`、`LeastPrivilege`、六分钟任务时限，不设置重试。必须引用稳定部署路径，不能引用 worktree。它不会注册或启用任务，需要已登录的桌面，不支持 Windows 自动登录或保存任务密码。

回退由人执行：只禁用单独批准的计划任务，经用户同意后通过正常界面退出辅助程序，再恢复未改动的手动 Gateway 启动方式。不要自动删除共享工具、凭据或设置。

## 验证范围

Linux CI 运行纯 Python 契约测试，专门的 Windows CI 还使用临时假程序测试 PowerShell，覆盖非启动检查、脱敏、桌面会话限制、私有输出和子进程失败。测试不安装 IBC、不认证账户、不下单，这些仍属于部署验证。参见[发布检查](release-checks.md)。
