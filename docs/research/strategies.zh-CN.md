# 策略详解

股票与加密日线策略、B0 至 B3 做市模拟已经可以用于离线研究，各自的数据要求和记账假设不同。小时线 DEX 信号只通过了合成数据检查，真实数据验证仍然受阻。

<a id="hourly-dex-factors"></a>
## 小时线 DEX 因子，真实数据尚未接通

四个固定的小时线诊断已实现，并通过合成数据测试。2026-10-22 的真实采集在首次认证检查时返回 HTTP403，随后停止。目前没有真实因子 IC、分组收益或回测结果。它们独立于下文的日频策略和 B0 至 B3 做市模拟。

在 `t = interval_end` 时，`momentum_24h` 为 `C[t]/C[t-24]-1`，`momentum_168h` 为 `C[t]/C[t-168]-1`。`volume_ratio_24h_7d` 将 `t-23..t` 的成交额总和除以 `t-191..t-24` 的日均成交额，后者是这 168 小时总和除以七。`momentum_volume_24h` 在该比率大于 1 时保留正的 24 小时动量，否则为零。缺失窗口和零成交额基准仍为空。

未来收益标签为 `C[t+h]/C[t]-1`，`h=6,24`。特征和标签都要求完整的小时网格，未来行情不能改变过去的特征。协议在采集前固定信号、期限、当前资产身份和三个 30 天切片，不进行参数搜索。研究源码的准确字节由哈希绑定，复现需要保留源码或字节一致的安装文件。

单资产时间序列的排名 IC，是平均排名之间的 Pearson 相关性。整体至少需要 30 对样本，每个固定切片至少 20 对。信号或标签恒定时返回空值并给出原因。`all_valid` 包含标签重叠的样本。`non_overlapping` 按距离协议起点的 UTC 小时偏移对期限取模，不代表样本在统计上独立。

横截面诊断要求同一有效时点至少九个不同底层资产。三组按归一化平均排名 `(rank-0.5)/n` 划分，不拆散并列值，每组至少三个资产，否则分组结果为空。分组平均未来收益及高组减低组的差值是未扣费的描述性标签。组合构建、实际成交、扣费收益、显著性及样本外验证仍需另做实验。 分组收益和 IC 分别统计有效时点数。同一时点各资产未来收益相同时，保留有效分组收益，但不计入 IC。`ic_valid_timestamps`、`ic_excluded_reasons` 和 `ic_reason` 分别记录 IC 样本数、排除原因和空值原因，不把无法计算的 IC 填成零。

`competition.dex_factor_result.v1` 绑定协议、manifest 和输入哈希，并记录样本数与限制。来源文件变化会使结果失效。公开投影排除原始数据、账户信息和私有路径。未确认公开权限时，`competition.public_dex_factors.v1` 使用 `status=readiness_only`，不包含指标。配置和命令见[数据访问说明](datasets.zh-CN.md#dexpaprika-hourly-pilot)。

## 日频策略对照

这些固定日频策略用于离线研究，执行验证仍待完成。解读结果前，请先阅读[研究方法](real-data-study.zh-CN.md)和[数据契约](datasets.zh-CN.md)。首页将各策略链接到本指南，并且只在相同市场、费用及计分窗口下进行对比。

## 共同假设与证据范围

本节的日频假设不适用于上面的小时线诊断。

2026-10-21 冻结研究包含 318 个已完成的策略、窗口与费用组合。每个窗口先预热 252 期，再对股票计分 63 个交易期，对加密货币计分 90 个日频周期。各窗口独立从现金开始。资产池按当前名单固定，历史时点的指数成分仍待补齐。美股池有十个标的，港股十个，加密货币八个。数据身份、覆盖范围、复权和选择偏差的限制见研究说明，不能从策略名称推断。

信号使用前一日收盘信息，持仓获得下一期收盘到收盘的变化。模型仅做多、使用现金。初始建仓扣费，期末不强制平仓。股票按每年 252 期、加密货币按 365 期年化。除预设费用外，模型未计入股息、税费、融资、离散手数、容量和独立验证的执行滑点。这里的策略不连接券商，也不能证明符合比赛资格。

固定单边费用为美股 20/40 bps、港股 30/60 bps、加密货币 0/10/25 bps。零费用是对照。首页默认采用非零的 20/30/10 bps。费用摘要在每档预设费用都覆盖的相同窗口上比较，也保留零费用对照。缺少基准值的窗口不计入正超额占比的分母，零超额不算胜出。这些数值仅作描述统计，显著性和新样本外表现仍待检验。

<a id="buy-hold"></a>
## 买入持有 `buy_hold`

股票研究按标识排序选取最多十个标的，初始等权配置，此后权重随价格漂移，不会每天重新等权。主要风险包括市场下跌、权重漂移后的集中度，以及当前选定资产池的偏差。窗口净收益为正，本身不能证明跑赢基准。

实现见[股票研究](../../research/equity-lab/src/equity_lab/study/run.py)。与 `equal_weight` 比较时，应固定市场、窗口和费用，再观察再平衡的影响。

<a id="equal-weight"></a>
## 等权组合 `equal_weight`

股票版本每天决策时，对按标识排序的最多十个标的重新等权。加密货币版本则对固定现货池初始等权，此后持有并允许权重漂移。同一标识在这两个独立实验中的配置规则不同。加密货币 `equal_weight` 也是指定基准，因此相对自身的超额收益为零。

股票再平衡可能增加换手和费用拖累。两种实现都不能防止普遍的市场下跌，应在同一市场内比较。实现见[股票](../../research/equity-lab/src/equity_lab/study/run.py)和[加密货币日频研究](../../research/crypto-mm/src/crypto_mm/daily/study.py)。

<a id="momentum-20d"></a>
## 二十期正动量 `momentum_20d`

股票模型筛选截至前一日收盘、过去二十个交易期收益严格为正的标的，按标识排序取最多十个并等权配置，无符合标的时持有现金。标的按标识选取，收益高低只用于正负过滤，目标仓位可能每天变化。

信号在零附近波动时可能反复切换并增加费用。过滤器也可能滞后于突然反转，错过下跌后的反弹。应结合换手、费用敏感性及最差窗口查看中位收益。实现见[信号](../../research/equity-lab/src/equity_lab/signals/momentum.py)和[配置](../../research/equity-lab/src/equity_lab/study/run.py)。

<a id="sma-cross"></a>
## 均线过滤 `sma_cross`

股票模型按前一日收盘，筛选二十期均线严格高于六十期均线的标的，按标识排序取最多十个并等权配置，无符合标的时持有现金。模型按日频状态过滤，日内交叉时点的成交仍待模拟。

横盘可能引发反复调仓，滞后信号也可能错过反弹初期。应在两档股票费用下，与买入持有和等权基线比较。实现见[信号](../../research/equity-lab/src/equity_lab/signals/sma.py)和[配置](../../research/equity-lab/src/equity_lab/study/run.py)。

<a id="benchmark-buy-hold"></a>
## 股票基准 `benchmark_buy_hold`

它持有预先指定的单标的股票参考资产，仅用作比较基线。窗口收益继续公开，逐日归一化曲线因与价格关联而有意不公开。因此对比表可以显示基准结果，但图表中没有对应曲线。

该基准并不重建选定股票池，其相对自身的超额收益为零。基准和资产池定义见[研究证据](real-data-study.zh-CN.md)。

<a id="momentum-63d"></a>
## 加密货币六十三期正动量 `momentum_63d`

日频现货模型筛选前一日收盘高于六十三个日频周期前收盘的资产并等权配置，无符合资产时持有现金。这是正收益过滤，不做排名、做空或衍生品交易。

阈值附近的频繁切换可能增加费用，波动和急剧反转也可能主导结果。应查看同窗口对比及匹配窗口的费用摘要。实现见[加密货币日频研究](../../research/crypto-mm/src/crypto_mm/daily/study.py)。

<a id="trend-200d"></a>
## 加密货币二百期趋势过滤 `trend_200d`

日频现货模型筛选前一日收盘严格高于过去二百期均价的资产并等权配置，无符合资产时持有现金。该原始对照不按波动率缩放仓位，也不使用调仓缓冲。下方独立的版本化消融路径增加固定叠加规则，保留原始对照不变。

过滤器可能滞后于反转，也可能在均线附近反复进出。较低仓位不保证较小回撤，应查看最差窗口和较高费用下的结果，不能只选一条有利曲线。实现见[加密货币日频研究](../../research/crypto-mm/src/crypto_mm/daily/study.py)。


<a id="formal-ablation"></a>
## 正式消融研究规则

独立的 `competition.evaluation_spec.v3` 路径支持复现已固定的调仓频率和风险控制实验，沿用 `self_financing_daily.v1`、独立现金起点、原费用、预热和计分长度。原有 v1 任务和已发布的 318 条研究结果保持不变。新任务和结果采用 v2 身份，绑定规则参数与来源。正式重跑仍然属于回溯证据。

| 市场 | 基础信号 | `variant_id` | 规则 |
| --- | --- | --- | --- |
| US/HK | `equal_weight`、`momentum_20d`、`sma_cross` | `weekly` | 每个 ISO 周首个实际出现的决策收盘时点 |
| US/HK | 同上三个信号 | `monthly` | 每个自然月首个实际出现的决策收盘时点 |
| crypto | `trend_200d` | `hysteresis_2pct` | 高于 1.02 × SMA200 时进入，低于 0.98 × SMA200 时退出，区间内保持状态 |
| crypto | `trend_200d` | `vol_target_40pct` | 当前入选等权组合此前 20 个完整日收益，用样本标准差 × sqrt(365) 估计波动，乘数为 min(1, 0.40 / 波动率) |
| crypto | `trend_200d` | `fixed_exposure_60pct` | 原始趋势目标权重乘以 0.60 |

股票在首个计分决策时点建仓，其他决策使用前一收盘信号。非调仓日持有实际份额和现金，不会重新平衡昨日权重。加密滞回规则从首个完整 200 期均值起预热状态。波动率计算不使用未来收益，零波动时乘数为 1，无入选标的时持有现金。所有规则均不加杠杆。60% 规则在有持仓的调仓时点将现金目标设为 40%，随后按市价计算的仓位可能超过 60%。

所有原始策略都保留显式 `baseline` 对照。调仓规则及前两种加密叠加规则标为 `retrospective_ablation`，参数在各自探索前固定，但此前已经查看过历史研究结果。60% 对照是在查看该轮探索后选定，始终标为 `post_hoc_diagnostic`。重新冻结、筛选和翻译均不能改变证据角色。这些结果不代表统计显著性、最优参数或未见样本表现。

v3 配置必须包含 `schema`、`manifests`、`costs`、`variants`、`origin`。每个选中市场都必须包含全部原始策略的 `baseline` 对照，再显式列出额外规则。`origin` 传入仓库外的 `probe_protocol`、`diagnostic_protocol`、`evidence_manifest` 路径。诊断协议必须记录父协议哈希，清单必须核验两个协议及其列出的证据文件。未知字段和参数覆盖会被拒绝，程序不会自动搜寻私人路径。

```sh
python -m competition_tools.team evaluate --config /external/team.toml --spec /external/ablation-spec.json --output-root /external/new-ablation
python -m competition_tools.evaluation.ablation_publication --aggregate /external/new-ablation/run/study-results.json --output /external/new-public-ablation.json
python -m competition_tools.check_ablation_delivery --config /external/team.toml --output-root /external/new-synthetic-ablation
```

使用已提交的源码和全新的仓库外输出路径。最后一条命令会创建明确标注为合成数据的输入和来源证据，不需要私人研究归档。根工具和两个叶子环境都必须指向当前检出。私有运行目录保留源码快照，开发 worktree 删除后仍可核验。新计划最多 768 个任务，共用 3600 秒期限，每批最多 384 个。原计划仍限制为 384 个。失败或阻塞任务保留空指标和明确原因，不自动重试。

[消融研究展示区](https://runchengxie.github.io/2026-quant-competition/zh-CN/#ablation)使用独立的 `competition.public_ablation.v1` 汇总，按相同市场、币种、信号、规则和费用分组。配对变化先比较同一窗口、同一费用下的原始对照，再汇总配对差值。缺失对照保持为空。图表与筛选不重新记账，不公开原始输入价格，也不增加每日曲线。

<a id="forward-observation"></a>
## 前瞻观察之前

[新对照实验](strategy-controls.zh-CN.md)使用独立协议完成了 420 项回顾任务，项目所有者确认取得展示授权后，420项汇总结果与224组配对现已公开。六个美股及加密候选已在历史运行前写入[手动观察登记](observation-registry.zh-CN.md)。截至 2026-10-23 的快照，尚未接受真实后续观察，仍需完整的新预热数据和经过审阅的可用性证据。旧缓存尾部仍属于回顾数据。[成交模型](us-execution-evidence.zh-CN.md)另需兼容的原始价格、公司行动、交易单位及上市范围证据。本次没有启用采集器、调度、券商登录或下单路径，详见[当前准备清单](forward-observation-readiness.zh-CN.md)。

## 复现与检查

先按[队员快速开始](../operations/team-quickstart.zh-CN.md)准备可编辑安装的源码和锁定的离线环境。真实数据重放需要获得授权的不可变数据 manifest、仓库外的团队配置及 v2 研究规格。根命令运行各 manifest 所支持的固定策略矩阵，没有单策略参数。新的源码提交或不同输入会形成新的研究身份，不会得到原始 artifact 哈希的精确复刻。

```sh
python -m competition_tools.team evaluate --help
python -m competition_tools.team evaluate --config /external/team.toml --spec /external/study-spec.json --output-root /external/new-study
python -m competition_tools.evaluation.study_publication --aggregate /external/new-study/run/study-results.json --output /external/new-public-study.json
```

以上路径应位于源码仓库外，输出使用新路径。公开仓库不分发授权原始数据。可以另用合成数据交付检查验证 CLI 契约，但不能将其视为真实数据表现。

```sh
python -m competition_tools.check_study_delivery --config /external/team.toml --output-root /external/new-synthetic-contract
```

[打开业绩看板](https://runchengxie.github.io/2026-quant-competition/zh-CN/#performance)，在相同费用及准确窗口下比较策略，再通过匹配窗口的费用摘要观察费用依赖。历史窗口不会拼成连续复利账户，原有公开快照保留原始运行，新对照使用独立协议和发布检查。
