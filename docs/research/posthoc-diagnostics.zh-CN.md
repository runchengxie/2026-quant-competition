# 已保存评分的事后诊断

该可选流程生成一份**基于已暴露历史的新私有事后报告**。原树模型研究、已审核的公开快照、其中不可用的不确定性结论，以及科学验收门槛均保持原样。流程不授权拟合、取数、回放、券商访问、目标导出或研究升级。外部所有者、时点数据、报价与 Paper 证据仍然受阻。

固定检验族为 16 个已保存模型区块，各自与 1/5/10/20 个交易日的固定评分前瞻标签交叉，共 64 项。模型包括 Ridge、Elastic Net、浅树与 momentum20，各有两个训练期限和两个已暴露窗口。每个区块保留自身完整的 40 个交易日，不拼接窗口或净值。

五分组边界取决策候选集中全部有限评分的线性 20/40/60/80 分位数，先分组，再检查未来标签。相同分数归入首个大于等于它的上边界。不同分数少于五个或边界重复时，分组保持不可用。每日保留候选数、有限评分数、有效标签覆盖率、各组数量、原始前瞻收益均值及最高组减最低组的描述值。这些收益不是可投资组合损益，也不进入检验族。每日 RankIC 要求至少 30 个可用候选且分数与标签均非常数；有可用标签的候选若缺少评分，该日 IC 不可用。

标签从下一交易日原始开盘价到指定期限的原始收盘价。该未来定价区间内的各日必须有有效正价格、相同且非空的 ticker 身份，且无已知公司行动边界。决策日 OHLC 或已完成的行动在定价区间之外，不会使该未来收益失效。缺少观察或标签尾部时保持不可用。新统计开始前，严格重建的全部 5/20 日标签必须逐项匹配绑定的原标签，包括不可用项。差异会终止新报告，不会悄悄更换样本。

统计观察单位是每日一次横截面 RankIC，估计量为每日等权均值。推断要求完整、连续的交易日片段，并同时满足 n≥30、n≥4h、n≥4max(5,h)。缺失、非有限或常数每日 IC 都有明确不可用原因。因此 40 日区块的 20 日标签推断不可用。描述性 IC 均值可以使用有效日期，但另报有效日数；推断不删除缺失日期。

Bartlett Newey-West 滞后为 h−1，采用 n/(n−1) 有限样本修正。正态诊断 95% 区间采用 z=1.959963984540054，双侧 p=erfc(|均值|/SE/√2)。非循环移动区块自助法长度为 max(5,h)，抽样 2,000 次，每项均重置 Python `random.Random(20261031)`。每次从 0 到 n−区块长度均匀抽取 ceil(n/长度) 个起点，拼接后截取前 n 个观察并求均值。百分位区间采用线性插值，不计算自助法 p 值。Holm 校正覆盖完整 64 项，不可用项内部按 p=1 补齐，输出仍为不可用。该校正不涵盖项目的自适应搜索，也不构成独立发现、因果关系或未来业绩证据。

## 冻结、运行与核验

使用已审核、已提交且干净的源码，以及分别安装的根包和叶包环境。根 CLI 只依赖标准库，通过文件和独立 Python 进程调用 equity 叶包；叶包使用已有 NumPy/pandas。全部输出放在规范外部 `DATA_ROOT/global-market-research` 下，owner 和 output 都须为新的专属路径。不要直接使用已有 retention 文件夹作为新 owner。

```powershell
& $rootPython -m competition_tools.evaluation.posthoc_diagnostics prepare `
  --parent-protocol $retainedTreeProtocol --owner $newPrivateOwner `
  --output $newPrivateResult --source $reviewedSource
& $rootPython -m competition_tools.evaluation.posthoc_diagnostics run `
  --protocol "$newPrivateOwner/protocol.json" --python $leafPython
& $rootPython -m competition_tools.evaluation.posthoc_diagnostics verify `
  --protocol "$newPrivateOwner/protocol.json"
```

Prepare 完整核验原树研究和父级导出，从 CSV 读取数据，无需解码 parquet；冻结完整文件清单、原始输入哈希、原公开快照的语义与字节哈希、源码、锁文件、规范化证据以及有序的完整 64 项检验族。该步骤生成 `inputs.json` 和 `protocol.json`，不计算新的不确定性。Run 在子进程前后复核绑定。根包和生产者均在计算前建立持久、排他的尝试声明；失败保留部分输出，不能在同一输出目录重试。核验器从已验证导出独立重建输入，以标准库重新计算全部诊断，拒绝改动、额外字段或文件，并核对已有核验回执。真实历史计算必须在审核和源码冻结后开始；合成流程通过不意味着科学验收升级。

封闭 v1 模式位于 `schemas/research/posthoc-{inputs,diagnostics,diagnostics-protocol}.v1.schema.json`。端到端合成检查需显式设置 `POSTHOC_LEAF_PYTHON` 为独立 equity 环境的 Python，默认根测试不导入叶包。测试覆盖手算 HAC、固定区块重采样、并列分数与标签筛选、缺失值、严格身份和行动检查、完整族校正、文件篡改与排他尝试。本次变更不包含新的真实历史结果。
