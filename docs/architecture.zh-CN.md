# 研究与执行边界

[English](architecture.md)

本仓库包含以 Paper 为默认环境的执行边界、比赛运维材料、三个独立离线研究包及中英文项目 Demo。外部量化能力仍由独立仓库维护，离线研究包不要求 submodule，也不导入这些提供方的源码。

比赛专属的离线研究和数据准备由本仓库维护，共享生产数据仍归外部权威所有者。团队入口只配置外部路径，不搜索相邻仓库源码。

## 当前职责

行内代码中的路径均相对于仓库根目录。`team.py` 用于尚未安装环境时从源码启动 CLI，实际实现已在 `src/competition_tools/team` 中，安装后可通过 `python -m competition_tools.team` 使用。运维包装脚本放在 `scripts/windows`。`research` 包含独立打包的研究项目，`config` 保存运行配置和模板，`schemas` 定义 artifact 契约。

| 能力 | 代码或契约 |
| --- | --- |
| 独立安装、本地环境检查和合成演示 | `team.py`、`src/competition_tools/team`、[团队快速开始](operations/team-quickstart.zh-CN.md) |
| 目标交接及订单、事件契约 | `src/packages/contracts` |
| 市场标准化、风控、审计和对账 | `src/packages/market_model`、`src/packages/risk`、`src/packages/audit`、`src/packages/reconciliation` |
| IBKR 映射及执行应用 | `src/adapters/ibkr`、`src/apps/execution_runner` |
| 外部 Nira 信号交接 | `src/strategies/nira`，版本化的 `targets.json`、`lineage.json` |
| 按日、分数权重股票研究 | `research/equity-lab`，独立依赖、lockfile 和报告 |
| 可见队列加密做市模拟 | `research/crypto-mm`，独立依赖、lockfile 和报告 |
| 可选研究验收 | `src/competition_tools/research_acceptance.py`、`experiment_acceptance.py`、`schemas/research/` |
| 已审查公开汇总及展示 | `site/src/data/strategy-validation.json`、`site/src/i18n/` 及 Astro 组件 |

执行代码不导入这些研究包。根验收工具消费 JSON/CSV 和 CLI 输出，不依赖研究包 Python 对象。研究报告成功不代表可执行命令。公开的执行 v1 target schema 支持 JP/US，运行时标准化还识别 HK，这一既有差异尚未解决。加密研究不会扩展执行契约。

股票包还维护独立的六市场国际诊断；五市场 next-open 回放只属于可选框架包。契约与模型限制见[国际实验](research/international-experiments.zh-CN.md)，两者都不替换默认轮动或执行交接。

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

执行流程保持为：

```text
targets.json + lineage.json → OrderIntent → BrokerCommand
  → OrderEvent / Fill → 可重建 Projection → 对账
```

券商事件日志是事件事实来源。账户环境默认 Paper，但程序接口的 `dry_run` 默认 false，仍需显式设置 dry-run 并执行 Paper 预检及生命周期检查。新的研究工具不会调用此流程。

## 外部复用与交付边界

`research/platform-compare` 已通过独立环境接入公开 `quant-platform` 提交 `28a32ba707ad72d1eb68cde5075663e1b3819ac7` 的记账 API。根工具保留原决策序列，消费经验证的 CLI 汇总，见[记账对照指南](research/accounting-comparison.zh-CN.md)。`quant-research` 和 `quant-deep-learning` 维护研究、模型协议，`quant-intel-platform` 维护其报告环境。其他提供方仍属于接入边界，本次未安装或接通。pandas 版本及模块命名冲突要求独立环境和版本化 artifact。本次不升级 gitlink、lockfile 或外部仓库。

只读本机核验发现，所检查平台的默认 IBKR factory 导入了不可用的 `quant_execution_engine.broker.ibkr`。这与本仓库自己的 IBKR 实现分开。所检查的 `quant-backtest-runtime` 要求 Linux，未在 Windows 启用。提供方的部分测试通过，不代表提供方到券商的链路可运营。

当前验收尚不能核验所有者来源和受治理的留出集，因此始终阻止研究证据升级。完整研究股票池、公司行动、因果 FX、加密场所及产品和费用核验、所有者模型协议、真实数据记账前提及受监督的 Paper 生命周期仍待完成。已经看过的历史继续标为回顾性诊断，公开的 24 条结果也不代表接入已经完成。
