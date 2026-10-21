# 日频历史对比研究

本研究用不可变日线快照比较固定策略。它使用当前固定池回看历史，不是历史指数成分重建，也不是已获准执行的策略。原有引擎、24 项结果和扩池日频快照保留各自的记账口径及结果。

## 输入与策略

股票需要完整的 IBKR `competition.dataset_manifest.v2` 日线快照、交易日网格，以及独立的 SPY 或 2800 基准。美股以 USD、港股以 HKD 计价。TRADES 价格按拆股调整，不是含分红总回报。数字货币使用 Binance 现货 USDT 日线。只有验证过的连续区间才能从不完整归档中提取，起点不早于 2023-01-01，并绑定原始文件哈希；父归档仍标为 partial。不公开原始数据。

| 市场 | 固定策略 | 单边费用假设 |
| --- | --- | --- |
| 美股 | buy_hold、每日 equal_weight、momentum_20d、sma_cross(20,60)、SPY buy_hold | 20、40 bps |
| 港股 | 相同股票方法，以 2800 buy_hold 为基准 | 30、60 bps |
| 数字货币 | 买入持有式 equal_weight、momentum_63d、trend_200d | 0、10、25 bps |

股票动量筛选过去 20 个交易日收益为正的标的并等权配置，不按动量强弱排序。SMA 筛选短均线高于长均线的标的。数字货币动量要求过去 63 天收益为正，趋势要求上一根完整日线收盘价高于过去 200 天均价。符合条件的标的等权，没有标的则持有现金。股票最多 10 个持仓，数字货币最多 20 个，总敞口不超过 1，不加杠杆，不设换手上限，不调参。股票池超过 10 个时，取符合条件且按标识排序的前 10 个。

## 记账与解读

每个独立窗口先用 252 个观测值计算特征，再评分股票 63 个交易日或数字货币 90 个自然日。只纳入完整且评分区间不重叠的窗口。每个窗口从现金开始，信号使用前一根完整收盘价。`lagged_close_proxy` 假设在该前收盘价配置仓位，是理想化日频代理，并未验证真实可执行的成交时序。评分期首次建仓计费，期末不强制平仓。

新的 `self_financing_daily.v1` 按实际数量盯市，按真实交易名义金额收费，求解 `E_after = E_before - fee * sum(abs(weight * E_after - current_holding_value))`，让满仓建仓费用由现有资金支付。旧引擎的目标权重换手与费用口径不同，历史输出保留，不悄悄替换。

净值与零费用影子组合使用相同目标规则。收益为期末归一化资产减 1，费用拖累为毛收益减净收益。回撤从初始资产 1 起计算，是非负的峰谷跌幅。波动率与零无风险利率 Sharpe 使用日收益样本标准差，股票年化 252、数字货币 365；零波动时 Sharpe 为 null。费用按归一化资产单位求和，换手按真实单边交易金额除以交易前资产后求和。超额收益只比较同窗口、同费用基准，不等于 alpha。独立窗口不能连乘为连续账户收益。

平均盯市仓位、日均单边换手和空仓天数仅为日频模型代理。分母包含全部评分日期，空仓日要求日末无仓位且当天无模型交易。它们不能证明比赛资格，也不能覆盖日内交易证据。当前固定池存在选择偏差，分红、税、融资、整手、容量、点差及真实滑点未独立建模，仅有明确列出的费用假设。账户与产品授权需另行确认。

## 复现

使用可编辑源码检出以记录代码身份，安装锁定的离线 team profile。根项目仅调用独立研究包 CLI 并读取版本化产物，不导入研究包 Python。v1 evaluation 不变。

```sh
python -m competition_tools.team evaluate --config /external/team.toml --spec /external/study-spec.json --output-root /external/new-study
python -m competition_tools.check_study_delivery --config /external/team.toml --output-root /external/new-synthetic-contract
```

v2 spec 仅包含以下三个键。

```json
{"schema":"competition.evaluation_spec.v2","manifests":["/external/dataset/manifest.json"],"costs":{"US":[20,40],"HK":[30,60],"crypto":[0,10,25]}}
```

不可变私有计划在执行前绑定输入与源码哈希、代码提交、任务、日期、费用和方法。上限为 384 项任务及 3600 秒。研究包产出 `competition.daily_study_result.v1` 和私有 `periods.json`，根项目验证身份与哈希。输入变化或不可用时标为阻塞，指标为 null。结果始终为 `accepted_research=false`。公开结果另行按白名单投影，不包含逐日仓位或私有日志。
