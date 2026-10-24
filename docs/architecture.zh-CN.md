# 研究与执行边界

[English](architecture.md)

项目继续放在一个仓库里，队员拿到代码就能独立安装和运行，无需其他 `quant-*` 仓库。模块按量化工作流程划分职责。研究产出证据，经过单独审查的目标文件才可以进入以 Paper 为默认环境的执行流程。

比赛专属的离线研究和数据准备由本仓库维护，共享生产数据仍归外部权威所有者。团队入口只配置外部路径，不搜索相邻仓库源码。

## 一个仓库里的工作流模块

仓库包含多个可安装的包，各自保留 lockfile。代码放在一起，离线研究仍可以使用独立环境，也无需连接券商。下表对应已有代码，每一步都有具体归属。

| 职责 | 当前代码归属 | 产物与边界 |
| --- | --- | --- |
| 下载数据 | `src/competition_tools/datasets/*_acquisition.py` 及各服务商 transport | 请求有明确上限，外部 manifest 不可覆盖。凭据保存在源码外。 |
| 校验与标准化数据 | datasets 的质量检查与存储模块、`equity_lab/data`、`crypto_mm/daily/inputs.py` | 消费前检查标的身份、日期、单位和缺失记录。保留原始输入，各模型说明自己的缺失值处理方式。 |
| 形成因子与信号 | `equity_lab/signals`、`equity_lab/predictive`、`crypto_mm/factors` | 输出带时间信息的特征或分数。未来收益标签属于评估，不能进入更早的决策。 |
| 搭建投资组合 | `equity_lab/portfolio/construction.py`，特定研究的规则仍由股票 study 和加密 daily 模块维护 | 根据分数与约束计算权重。这是内部职责边界，尚非通用配置接口，也不是订单。 |
| 策略回测 | `equity_lab/backtest`、股票 study 模块、`crypto_mm/daily` 及独立做市模拟器 | 按各模型的时间与费用假设回放权重或报价。日线无法提供做市队列证据。 |
| 验收与发布研究 | `src/competition_tools/evaluation`、验收工具及 `site` | 根工具调用研究包 CLI，读取带版本的产物。网页只接收经过审查、字段明确的汇总。 |
| 下单与对账 | `src/apps/execution_runner`、`src/adapters/ibkr`、`src/packages/reconciliation`、`src/packages/audit` | 已审查目标通过预检和安全检查，券商事件与成交进入日志及对账流程。 |
| 解释业绩来源 | 各包 reporting、`equity_lab/international/six_market_run.py`、`platform_compare/accounting` | 已有收益与费用诊断，以及特定模型下的市场、汇率和股息贡献。通用因子归因与 Brinson 归因尚未实现。 |

研究会反复调整信号和组合规则，再用回测检查。评估说明模型下发生了什么，策略能否进入下一阶段需要另行判断。执行流程保留自己的检查和状态。

```text
下载 → 校验与标准化 → 因子与信号 → 组合规则 → 回测
                         ↑          ↑        │
                         └──── 研究迭代 ─────┘
回测 → 评估及限定范围的业绩解释 → 经审查的公开汇总

单独审查的 targets.json + lineage.json
  → 执行预检与安全检查 → 券商适配器 → 事件与成交 → 对账
```

提取后的股票权重规则保留 `BacktestConfig` 和 `run_equal_weight_backtest` 的导入路径、默认值及计算顺序。换手仍按原来的目标权重差计算，拆分不会使它具备按实际持仓漂移记账或自融资核算的能力。引擎继续负责信号滞后、收益和费用。加密日线与做市规则保留各自的模型。

后续遇到两个真实使用方需要同一套计算语义，再提取共享实现。修改边界前先补契约与兼容性测试。服务商差异留在 adapter，组合规则不反向导入回测，执行代码不导入研究包。可选的 Quant 系列接入需要固定接口与对照证据。本次没有新增 runtime 依赖，也没有拆分仓库。

## 当前职责

行内代码中的路径均相对于仓库根目录。CLI 实现位于 `src/competition_tools/team`，安装后通过 `python -m competition_tools.team` 使用。首次安装使用外部引导环境，步骤见团队快速开始。运维包装脚本放在 `scripts/windows`。`research` 包含独立打包的研究项目，`config` 保存运行配置和模板，`schemas` 定义 artifact 契约。

| 能力 | 代码或契约 |
| --- | --- |
| 独立安装、本地环境检查和合成演示 | `src/competition_tools/team`、[团队快速开始](operations/team-quickstart.zh-CN.md) |
| 目标交接及订单、事件契约 | `src/packages/contracts` |
| 市场标准化、执行检查、审计和对账 | `src/packages/market_model`、`src/apps/execution_runner/preflight.py`、`src/apps/execution_runner/safety.py`、`src/packages/audit`、`src/packages/reconciliation` |
| IBKR 映射及执行应用 | `src/adapters/ibkr`、`src/apps/execution_runner` |
| 外部 Nira 信号交接 | `src/strategies/nira`，版本化的 `targets.json`、`lineage.json` |
| 按日、分数权重股票研究 | `research/equity-lab`，独立依赖、lockfile 和报告 |
| 可见队列加密做市模拟 | `research/crypto-mm`，独立依赖、lockfile 和报告 |
| 可选研究验收 | `src/competition_tools/research_acceptance.py`、`experiment_acceptance.py`、`schemas/research/` |
| 已审查公开汇总及展示 | `site/src/data/strategy-validation.json`、`site/src/i18n/` 及 Astro 组件 |

执行代码不导入这些研究包。根验收工具消费 JSON/CSV 和 CLI 输出，不依赖研究包 Python 对象。研究报告成功不代表可执行命令。公开的执行 v1 target schema 支持 JP/US，运行时标准化还识别 HK，这一既有差异尚未解决。加密研究不会扩展执行契约。

股票包还维护独立的六市场国际诊断。五市场 next-open 回放只属于可选记账包。契约与模型限制见[国际实验](research/international-experiments.zh-CN.md)，两者都不替换默认轮动或执行交接。

## 数据流与身份

独立的[数据准备工具](research/datasets.zh-CN.md)在 `src/competition_tools/datasets` 中维护显式来源规格、有预算的下载和外部不可覆盖的 manifest。根评估工具启动独立安装的加密日线 CLI，并读取 JSON，不导入子项目模块，也不把日线当作订单簿事件输入。Pages 使用单独的 `strategy-expansion.v1.json` 展示新的事后汇总，原24条结果快照保持不变。

```text
外部数据集 + 显式清单
  → 研究包输入检查 → 版本化输入凭证
  → 根项目精确字节复查 + 保留的配置、摘要及观测
  → 软件诊断通过或实验被阻止
  → 公开汇总发布前单独审查
```

原始输入、私有配置、凭证、报告、模型和图表均保存在源码之外，使用配置指定的所有者数据目录。凭证将元信息及相对文件引用与原始字节哈希绑定。这可以检测变化，不提供独立服务商认证或原子快照隔离。输入检查、实验验收和执行交接属于不同契约，详见[验收指南](research/research-acceptance.zh-CN.md)。

执行流程如下。

```text
targets.json + lineage.json → OrderIntent → BrokerCommand
  → OrderEvent / Fill → 可重建 Projection → 对账
```

券商事件日志是事件事实来源。账户环境默认 Paper，但程序接口的 `dry_run` 默认 false，仍需显式设置 dry-run 并执行 Paper 预检及生命周期检查。新的研究工具不会调用此流程。

## 外部复用与交付边界

`research/platform-compare` 现在包含比赛自有的 USD 价格账本，HK/US 对照与五市场 next-open 均不再安装或导入 `quant-platform`、`research-contracts`。提取来源、许可证及历史兼容见[记账对照指南](research/accounting-comparison.zh-CN.md)。外部数据和 Nira 信号仍按明确文件契约消费，独立环境保留依赖版本隔离。

只读本机核验发现，所检查平台的默认 IBKR factory 导入了不可用的 `quant_execution_engine.broker.ibkr`。这与本仓库自己的 IBKR 实现分开。所检查的 `quant-backtest-runtime` 要求 Linux，未在 Windows 启用。提供方的部分测试通过，不代表提供方到券商的链路可运营。

当前验收尚不能核验所有者来源和受治理的留出集，因此始终阻止研究证据升级。完整研究股票池、公司行动、因果 FX、加密场所及产品和费用核验、所有者模型协议、真实数据记账前提及受监督的 Paper 生命周期仍待完成。已经看过的历史继续标为回顾性诊断，公开的 24 条结果也不代表接入已经完成。
