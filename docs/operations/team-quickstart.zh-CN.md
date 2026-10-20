# 运行团队离线演示

[English](team-quickstart.md)

克隆本仓库并安装 Python 3.12 和 `uv`。默认离线流程不需要 `quant-*` 仓库、框架包、券商连接或数据服务凭据。在仓库根目录运行以下命令，将绝对路径替换为自己的外部目录，Windows 可使用 `D:/data/team-demo`。

```sh
python team.py --help
python team.py init --config /absolute/private/team.toml --data-root /absolute/data/team-demo
python team.py setup --config /absolute/private/team.toml --profile offline
python team.py doctor --config /absolute/private/team.toml
python team.py demo equity --config /absolute/private/team.toml --output-root /absolute/data/equity-demo-001
python team.py demo crypto --config /absolute/private/team.toml --output-root /absolute/data/crypto-demo-001
```

`init` 创建 `competition.team.v1` TOML 配置，拒绝覆盖已有文件。配置键只有 `schema_version`、`data_root` 和 `environment_root`。环境默认放在 `<data_root>/2026-quant-competition/environments`，可用 `init --environment-root` 更改。路径必须是绝对路径，且不能位于 Git 源码目录、关联 worktree 或指向源码的符号链接中。Windows 使用当前用户 ACL，POSIX 使用 `0600` 权限。配置只保存路径，不保存凭据。参见[配置模板](../../config/team.example.toml)。

`setup` 按已提交锁文件分别安装 `root`、`equity-lab` 和 `crypto-mm` 三个环境。子进程清除继承的 `PYTHONPATH` 和 `PYTHONHOME`，显式接收 `DATA_ROOT`，不搜索相邻仓库。安装后的模块入口为 `python -m competition_tools.team`；在源码目录外运行 `setup` 时，传入 `--repository-root /absolute/checkout/2026-quant-competition`。

`doctor` 只在本地检查解释器文件是否存在，不验证依赖完整性、凭据、数据权限或策略就绪状态。使用已安装根环境运行 `python -m competition_tools.check_team_delivery --config FILE`，可另行检查已安装分发包中是否含有框架依赖。两者都不导入服务商模块或进行认证。

演示必须使用新的外部输出目录。它调用原有子项目命令，将子进程日志保存在 `logs/`，并写入带 `synthetic: true` 的 `team-run.json`。失败或中断后保留部分产物供排查，重试时选择新目录。股票使用 `equal_weight`。加密生成虚构盘口、成交和资金费率数据，审计后运行 `2026-03-19` 的 `B0` 回放。这些示例只验证软件，不能说明投资表现。

命令返回 `competition.team_result.v1` JSON，包含 `action`、`status`、`issue_codes`、`projects` 和 `synthetic`。退出码 `0` 表示完成，`2` 表示阻塞或失败。结果不包含原始子进程日志或私有路径。本地日志可能包含路径，分享前需要检查。演示的 `synthetic` 为 true，其他操作为 null。

## 可选环境与验证

`setup --profile framework` 只安装独立锁定的[记账适配器](../research/accounting-comparison.zh-CN.md)，包含固定版本公开框架包。`setup --profile broker-data` 只安装根包的 `ibkr` extra，不登录或下单。`setup --profile website` 需要 Node.js 24/npm，为 `site` 运行 `npm ci`。默认离线安装不包含这些环境。

默认 CI 检查根包和两个研究包，并在无框架依赖的环境中运行团队演示。独立的 `platform-comparison.yml` 检查适配器及记账相关改动，也支持手动运行。参见[开发检查](../../README.md#development-checks)。原有输入验收、来源限制和执行安全规则仍然适用。这个入口不下载全市场数据、不登记策略、不将研究接入下单，也不启用 Gateway 自动化。历史公开结果快照保持不变。

新增的 `src/competition_tools/team/` 代码使用目录内 MIT `LICENSE`，根目录已有代码和第三方包保留原许可。

使用显式 `run international` 或可选 `run next-open` 命令运行[国际实验](../research/international-experiments.zh-CN.md).
## 数据准备与历史评估

独立外部规格、预算、不可覆盖的receipt及实际来源支持见[数据准备](../research/datasets.zh-CN.md)。`team.py data plan`、`data acquire`、`data inspect`不改变团队配置schema。`team.py evaluate`只在独立环境中运行加密日线矩阵，股票和做市矩阵仍使用既有API。结果与限制见[新评估证据](../research/data-expansion-and-evaluation.zh-CN.md)。这些命令均不启动Gateway或下单。
