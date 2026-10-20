# 独立记账对照

[English](accounting-comparison.md)

可选的 `research/platform-compare` 使用比赛项目自有的 USD 价格账本，将保留的策略决策与现金、股数模型对照。它不安装任何 quant 框架包，默认引擎和公开的 24 条历史结果不变。对照仍为合成软件诊断，不认证真实回测或券商执行。

## 已接通的边界

| 生产者 | 原有策略 | 保留的决策 |
| --- | --- | --- |
| `equity-lab` | `equal_weight`、`momentum_20d` | 经过原有一周期信号滞后及换手限制后的日频目标 |
| 根月频引擎 | `pure_momentum`、`momentum_volatility` | 原月度选择调用产生的真实权重，显式补齐未选标的的零目标 |
| `platform-compare` | 不生成信号 | 把决策、观测和明确的时钟映射到 owner API |
| 根对照工具 | 不导入 provider Python | 在独立环境验证 owner 文件，再核对允许的汇总字段及绑定 |

股票导出要求完整对齐的交易日网格，拒绝重复行、非有限值和非零股息。已经规划好的目标不会再滞后一日，最后一天没有下一交易日时不虚构成交。原浮点汇总保持一致。月频观察接口为可选项，不改变返回对象或默认行为。月频排名在 US 下仅属于已测试的合成诊断配置，不代表新验证的美股实盘策略。

## 环境和命令

使用 Python 3.12 和三个源码外的独立环境，从本机工作区配置解析路径或显式传入。环境、样例和输出不能放在源码中。provider 与股票研究环境的 pandas 版本彼此独立。

```powershell
$env:UV_PROJECT_ENVIRONMENT = $rootEnvironment
uv sync --locked --extra test
$env:UV_PROJECT_ENVIRONMENT = $equityEnvironment
uv sync --project research/equity-lab --locked --group dev
$env:UV_PROJECT_ENVIRONMENT = $providerEnvironment
uv sync --project research/platform-compare --locked --group dev

& $rootPython -m competition_tools.check_accounting_comparison --output-root $newSyntheticDirectory --leaf-python $equityPython --provider-python $providerPython
```

命令生成八组用例，调用真正的原策略生产者和本地账本，再用第二个进程验证每个输出包。输出目录必须尚不存在，其中保留私有的完整对照和汇总 `summary.json`，不会自动发布到 Pages，也不会改动原输入字节或既有报告。CI 的 accounting job 执行相同边界。

有明确时钟凭证的保留文件可通过下面的命令对照：

```powershell
& $rootPython -m competition_tools.accounting_comparison --legacy $legacyJson --clocks $clockJson --provider-python $providerPython --request $requestJson --dataset-root $datasetRoot --bundle $ownerBundle
```

可选包也可运行或重新验证 owner 输出，见[输入契约和命令](../../research/platform-compare/README.zh-CN.md)。

## 契约和模型差异

`competition.legacy_decisions.v1` 保留生产者、策略及频率、市场、合成标记、输入与原配置指纹、按交易日期标记的目标和原汇总，不声称外部生产者经过认证。`competition.decision_clocks.v1` 将相同输入和配置身份绑定到明确的 UTC 研究时钟和成交时间。缺少时钟返回 `CLOCK_METADATA_REQUIRED`，对照 CLI 对无效输入输出脱敏的阻塞结果。

来源日期必须早于成交日期，信息截止、信号、决策、订单、成交和估值顺序须满足因果约束。这组日频 HK/US 适配要求 UTC 时钟日期与提供的交易日标签一致，跨午夜政策需要另行适配。真实交易日期本身不足以完成验证，时钟凭证和报告中的决策不能矛盾。

必须核对 owner 请求的输入、配置、决策序列和 manifest 身份，以及初始资金、佣金和滑点假设。owner publisher 独立对账其财务表，reader 校验文件哈希。验证还通过本地账本 API 和 publisher 完整重放请求并比较全部诊断结果，防止修改 manifest 标签后冒充另一计算。只有在文件清单验证后，才把 owner 输出的有限 Decimal 指数形式转成规范字符串；输入金额仍遵守较严格的语法。额外的未列入清单的汇总文件不能证明 owner 结果。

原始权重和净值保持不变。浮点目标序列化为十进制后，若总权重超出一的部分不超过 `0.000000000001`，映射只从最大目标减去这部分误差，同权重时按 instrument ID 决定。更大的超额直接拒绝。`weight_mapping_policy=decimal_budget_residue.v1` 和 `weight_mapping_adjustments` 记录每次调整的成交日期、标的、原总权重及扣减量。

对照保留两种净值及差额、owner 现金和持仓价值、费用、成交额、取整方式、汇率假设和观测数量，并明确列出现金／股数结算、数量漂移、整手、汇率、换手及费用基准、时序差异。不以收益相等作为验收条件。分数权重代理不会像现金／股数模型一样产生数量漂移，owner 还会根据扣费后的可用资金缩放买入。月频代理汇总不包含预热现金观测，而 owner 保留完整的合成估值网格。这些属于不同模型，不能当成简单的数值一致性失败。

## 合成验证

固定样例含两个虚构标的，从 2026-01-16 起共 32 个按日标签。初始 USD 资金为 10,000，佣金 1 bps，滑点 2 bps。HK 使用虚构 HKD/USD 0.125、每手 100／200 股和整数取整，US 使用 USD 和分数股。下一日 09:00 UTC 的成交标记特意复用前一个合成收盘价，16:00 UTC 估值。这是受控的人工假设，不是真实开盘价。月频冒烟配置采用 lookback 2 和 volatility window 2，生产默认值未变。这个小样例中的两个月频策略选择了相同目标。

2026-10-19 实际重跑八组用例的最终结果如下，数值四舍五入到 4 位小数。它们只验证软件行为，不能作为市场表现、研究验收或晋级建议。US 分数股样例的微小剩余现金在表中显示为零，完整结果保留在私有输出中。

| Market | Strategy | Legacy NAV | Owner NAV (USD) | Cash (USD) | Costs (USD) | Difference (USD) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| HK | equal_weight | 11879.0662 | 11541.1231 | 1241.1231 | 2.6269 | -337.9431 |
| HK | momentum_20d | 10581.5260 | 10479.1125 | 2872.8625 | 2.1375 | -102.4135 |
| HK | pure_momentum | 10812.3879 | 10798.2750 | 4248.2750 | 1.7250 | -14.1129 |
| HK | momentum_volatility | 10812.3879 | 10798.2750 | 4248.2750 | 1.7250 | -14.1129 |
| US | equal_weight | 11879.0662 | 11878.7076 | 0.0000 | 3.3097 | -0.3586 |
| US | momentum_20d | 10581.5260 | 10581.4205 | 0.0000 | 3.0863 | -0.1054 |
| US | pure_momentum | 10812.3879 | 10832.9826 | 3998.2000 | 1.8000 | 20.5947 |
| US | momentum_volatility | 10812.3879 | 10832.9826 | 3998.2000 | 1.8000 | 20.5947 |

## 真实输入与隐私

此适配器版本只接受合成输入。在接入独立核验真实来源和时序证据的适配器前，`synthetic=false` 会返回 `REAL_INPUT_EVIDENCE_UNVERIFIED`。哈希和调用者标记不能认证数据来源。

目前找到的历史日线只有交易日标签，缺少所需的可验证可用时间、成交时钟、完整每手信息和因果汇率，继续阻塞。旧的 20 只股票盘点文档不能充当不可变数据凭证。不会把合成时钟附到真实数据，也不会用样例代替缺失数据。

本次公开导出审计还从当前读者文档移除不必要的比赛方和合作宣传描述及私有入组流程。公开规则来源链接和已经公开的 GitHub 仓库身份保留以便追溯，因此属于减少披露，不代表完全匿名。凭据、个人联系方式、账户和报表数据、私有路径及授权原始行情应放在源码外。历史 PR 引用可能仍保留曾经公开的材料，本任务不重写历史，也不承诺清除缓存；私有审计报告会记录剩余范围。

账本来源与许可见[包说明](../../research/platform-compare/README.zh-CN.md)。下表保留 2026-10-19 的原框架历史基线，不能将历史文件改标为本地引擎结果。新请求及结果使用 v2，并记录比赛项目自己的引擎身份。

## 解耦验证（2026-10-20）

迁移前后八组汇总、全部诊断内容及 64 张 Parquet 财务表完全一致。五市场 next-open 的 36 个成本情景、288 张财务表和全部诊断内容完全一致，成本敏感性 CSV 逐字节一致。根测试 562 项、独立记账测试 173 项通过；wheel 在源码目录外、未安装外部框架且阻断框架导入的环境通过 5 项检查。这些均为软件验证，不增加真实数据或交易有效性结论。
