# AGENTS.md

本仓库是香港量化比赛的执行与运行项目。研究、回测和原始数据采集不在本仓库复制维护。

## 项目边界

- `research-workspace` 和 Nira 负责研究、回测、因子和信号。
- 本仓库负责目标交接、市场标准化、风险控制、NautilusTrader 执行、IBKR Gateway、对账和比赛审计。
- AIVIX/Cryptoracle 只用于加密资产指标实验，不能作为港股或日股行情源。
- RQData 只作为 A 股、ETF 和基金等备用研究数据源，不能作为 Nira 的日本股票数据源。
- 不通过本地绝对路径 import `research-workspace` 或 Nira 源码。

## 目标交接

研究侧通过版本化的 `targets.json`、`lineage.json` 和 schema 交接。执行侧不得根据目录位置推断策略身份、市场或订单参数。

订单生命周期采用以下边界：

```text
targets.json → OrderIntent → BrokerCommand → OrderEvent / Fill → Projection
```

文件目标是命令和交接证据，订单事件日志是券商事实来源，projection 是可重建的当前状态，对账用于处理漏事件和重启恢复。

## Agent 协作流程

所有代码或文档改动必须遵循以下 worktree-first、PR-first 流程：

1. 先确认当前 checkout 的状态；不得直接在 `main` 上开始任务。
2. 从 `origin/main` 创建独立 worktree 和功能分支；worktree 放在项目的 `.worktrees/` 下，并确保该目录被 `.gitignore` 忽略。
3. 一个 Agent 只负责一个清晰、可验收的任务；并行 Agent 必须拥有不同 worktree、分支和不重叠的核心文件集合。
4. 新功能必须先写失败测试，再写最小实现；共享契约、配置、迁移和执行核心存在依赖时必须串行。
5. 在功能 worktree 内完成测试、静态检查、安全检查和人工审阅；不得把未验证的改动直接带回 `main`。
6. 在功能分支提交并推送，创建 PR；PR 必须经过 review 和 CI 检查后，才允许合并到 `main`。
7. 合并后确认 `main` 测试通过，再删除远端功能分支、本地功能分支和对应 worktree。
8. 清理完成后检查 `git worktree list`、`git branch -a` 和 `git status --short --branch`，确保没有残留分支、worktree 或未提交改动。

推荐分支命名：`feat/*`、`fix/*`、`chore/*`、`docs/*`。

执行核心、schema、配置和迁移任务存在依赖时必须串行；只读调查、文档和互不重叠的测试任务可以并行。

## 执行安全

- 默认只允许 Paper 账户和 Paper Gateway。
- 实盘必须有独立配置、显式保护开关和人工监督。
- 不提交 `.env`、`.env.*`、API key、账户信息、订单日志或运行产物。
- 下单前必须完成账户、合约、价格、数量、市场时段和风险检查。
- 未确认的订单状态不得推断为拒绝或成交，必须通过事件或对账确认。
- 测试默认使用 mock 或 Paper；不使用真实资金做自动化测试。

## 代码组织

- `packages/contracts`：目标、订单意图、订单事件和 schema。
- `packages/market_model`：市场、交易所、币种、手数和交易日历。
- `packages/risk`：执行前风险检查和 kill switch。
- `packages/audit`：事件日志、审计和比赛证据。
- `adapters/ibkr`：IBKR Gateway 合约、行情、订单和回报映射。
- `apps/execution_runner`：Windows 上的常驻执行进程。
- `strategies/nira`：读取外部 Nira 信号并导出目标，不复制 Nira 全部源码。

研究和执行使用稳定契约连接，不把整个 `research-workspace` 搬进来。

## 验证要求

- 修改契约、订单生命周期或券商适配器时必须运行对应单元测试。
- 修改执行链时必须额外验证 Paper 账户连接、合约识别、提交、撤单、成交、重启恢复和对账。
- 任何完成声明必须附真实命令结果，并明确哪些内容尚未经过真实券商验证。
