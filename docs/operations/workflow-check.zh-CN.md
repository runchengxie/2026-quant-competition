# 检查离线工作流程

[English](workflow-check.md)

这个检查用虚构输入跑通股票与加密流程，再核对输出。成功记录说明这些已安装模块能在样例中衔接，历史策略表现和券商准备情况仍需各自的证据。

## 运行并核验

先按[团队快速开始](team-quickstart.zh-CN.md)安装独立的 offline profile。在与安装代码匹配、改动已提交的源码检出中运行，当前环境需要安装根项目。输入、输出和环境都放在源码外，输出目录必须尚不存在。

```sh
python -m competition_tools.check_workflow_boundaries --source-root .
python -m competition_tools.check_workflow_delivery --config /absolute/team.toml --output-root /absolute/new-workflow-run --source-root .
python -m competition_tools.evaluation.run_record --run-root /absolute/new-workflow-run
```

将 `/absolute/...` 换成你自己的路径，Windows 需要带盘符的绝对路径。这个模式需要源码检出，才能把证据绑定到研究环境实际安装的代码。原有 `team demo` 命令保持原样。

运行器分别启动一次配置中的股票与加密解释器，不请求服务商数据，也不下单。每个子进程的超时为 180 秒。共享处理预算为 600 秒，在阶段之间和最终写入前检查。文件哈希与保存使用同步文件调用，因此它无法硬中断阻塞的文件 I/O。失败尝试会保留为失败或未完成状态，不会自动重试。

## 两条流程检查什么

股票任务使用 24 个虚构日期标签、两个虚构股票代码和一条缺失记录。它先整理行情表，形成短长均线信号，再分配权重，用现有分数权重引擎分别跑 20 bps 模型成本与零成本回放。日期只是演示网格，尚非交易所日历。

加密任务使用 270 天虚构价格，其中 252 天用于准备指标，共两个虚构产品。严格趋势与波动控制规则形成目标权重。首次及之后每个周一的决策交给现有自融资账本，分别计算 35 bps 模型成本和零成本对照，其他日期保留数量与现金。计价单位继续是 USDT。做市模拟器保留独立的事件模型。

两个研究包都会生成 `competition.workflow_leaf_result.v1`，保留可检查的表格或账本，记录实际 Python 与安装包版本，以及已安装源码的摘要。[schema](../../schemas/research/workflow-leaf-result.v1.schema.json)定义了这个新契约。根工具接受结果前，会比较任务、保留源码、产物哈希和嵌入数据。根项目生产模块不导入研究包 Python。

## 解释价格收益与模型成本

`explanations/equity-lab.json` 和 `explanations/crypto-mm.json` 使用 `competition.performance_explanation.v1`，保留各自的记账模型与货币。每期和总额都必须核对一致，金额容差为 `1e-10 × max（1，相关净值）`。无效数值、缺失记录、模型或货币不匹配，以及无法核平的金额都会使检查失败。报告保留最大的金额核对误差。

| 字段 | 含义 |
| --- | --- |
| `instruments[].price_pnl` | 各标的带正负号的价格贡献，单位与账户一致 |
| `instruments[].return_contribution` | 价格贡献除以初始净值 |
| `modeled_costs` | 沿扣费后账户路径扣除的模型成本 |
| `net_pnl` | 最终净值减初始净值，须等于价格贡献减模型成本 |
| `counterfactual_cost_drag_return` | 零成本回放收益率减扣费后回放收益率 |

扣费会改变后续可投入的资金，因此收益差不一定等于累计成本除以初始净值。这些解释核对模型里的金额关系，尚不能证明因果性的因子效果、Brinson 归因、真实成交或场所费用。`competition_tools.evaluation.contributions` 中的纯函数 `explain_fractional` 和 `explain_self_financing` 也可以检查兼容的输入产物。调用方需要绑定策略与对照身份，本运行器通过任务和源码记录完成这项绑定。

## 追踪实验记录

子进程运行前，`experiment-plan.json` 固定参数、成本和输入哈希，记录源码提交、保留原始字节的源码归档及锁文件哈希。验证后，`experiment-result.json` 绑定实际环境信息和输出哈希。新记录使用包内相对路径，完整目录迁移后仍能核验，无需保留原来的源码检出位置。

`delivery.json` 描述已检查的输出，状态为 `outputs_verified`。整次运行完成的依据，是通过核验且状态为 `completed` 的 `experiment-result.json`。交付失败时 CLI 返回非零状态。如果计划或输入发生变化，导致无法完成最终记录，运行会保留为未完成，并在 `record_issue` 中说明状态。重试时请使用新目录，保留旧记录。

可复用的 `init_run`、`freeze_run`、`finish_run`、`verify_run` 位于 `competition_tools.evaluation.run_record`。它们只创建新记录，可以发现输入、保留源码、锁文件或输出的变化。哈希校验不认证服务商或作者身份。锁文件记录预定环境，另外保存的安装版本记录实际运行环境。历史实验继续使用各自已有的计划和凭证，默认演示标记保持原样。

完整目录保存在公开源码之外。本检查使用合成数据，记录用于证明工程流程可运行。它们不会变成目标文件或已验收研究，也不更新已发布的科学结果快照。

## 持续检查模块边界

CI 运行同一个静态导入检查器。它解析普通导入、相对导入和简单动态导入。信号注册器的固定命名空间会与禁止的目标比较，纯计算层无法确定去向的动态导入会失败。根代码不能导入独立安装的研究包，数据和组合规则层不能导入回测或券商机制。

检查器读取源码，不执行源码。它用于发现架构回归，尚非安全沙箱，也不能证明任意运行时代码的行为。测试包含允许的导入和相似名称，保留正常使用方式。CI 还会用已安装的 offline profile 实际运行两个生产者和根消费者的交接检查。
