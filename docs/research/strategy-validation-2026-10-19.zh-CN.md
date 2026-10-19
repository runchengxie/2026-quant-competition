# 策略盘点与验证记录，2026-10-19

现有实现可以作为离线实验运行，但四家数据服务商和 IB Gateway 尚未组成完整的数据到下单系统。本次记录 24 组固定配置诊断，包括八个股票策略分别在两个小样本市场上的运行、两个港股月频变体、两个五区域 ETF 变体，以及四个加密做市归档回放。没有选定比赛策略，没有调用下单方法。

[英文原文](strategy-validation-2026-10-19.md) 是事实依据。[公开汇总快照](../../site/src/data/strategy-validation.json) 为两个语言版本的网页提供同一组数据，不包含原始观测、机器路径、账户与订单标识或凭证。计算代码固定于 `ca6f4bc6f13fa933594cfe3f1823d800b42bb930`。这些是探索性软件与模型证据，不是可投资或样本外业绩。

## 具体有哪些策略

| 类别 | 实现 | 策略含义 |
| --- | --- | --- |
| 港股月频 | `hk_pure_momentum`、`hk_momentum_volatility` | 用前一交易日可见的 126/252 日动量月度排序，后者加入波动率标准化。保持原现金和仓位上限。本轮只有一只股票，不能验证横截面选股。 |
| 港股与美股实验 | `sma_cross`、`momentum_20d` | 20/60 日均线交叉和 20 日动量，只做多。 |
| 对照组 | `equal_weight`、`random_turnover` | 等权和固定随机种子的选择对照。只有一个可选资产时结果相同，不能视为两份独立 alpha 证据。 |
| 神经网络实验 | `cnn_pattern`、`cnn_pattern_mvp`、`cnn_image_pattern` | 数值或图像 CNN 分类器，可能对训练区间输出预测，完整区间收益包含此风险。名称不代表完成论文复现。 |
| 按时间切分的 CNN | `cnn_walk_forward_rank` | 训练、验证与测试窗口，含 purge、embargo、概率校准和排名。原 1,260 日训练窗口长于本次样本，没有可用 fold。 |
| 区域 ETF 轮动 | `global_pure_momentum`、`global_defended_rotation` | 63/126/252 日动量月度轮动，后者加入波动率与绝对动量防御。本轮只有五个区域，不是原完整六区域股票池。 |
| 加密 B0 | 中间价、固定价差、库存偏移 | 根据盘口、成交事件与库存账户报价。 |
| 加密 B1 | L1 microprice 与盘口不平衡 | 修改公允价，沿用同一模拟器，没有新增交易所接线。 |
| 加密 B2 | 波动率自适应价差 | 根据历史波动率调整报价宽度。 |
| 加密 B3 | 资金费率引导的库存目标 | 滚动费率观测改变目标库存，不是经确认的实际结算记录。 |
| 仍是候选 | AIVIX 驱动的美股配置、外部港股 XGBoost/PIT 排序 | 本仓没有完成端到端实现。`international_lite` 提供特征与评估工具，Nira 提供交接校验，不包含外部 alpha 模型，均不能算另一个已交付的自主策略。 |

## 四家服务商和 Gateway 能提供什么

| 数据源 | 实际证据 | 缺口 |
| --- | --- | --- |
| AIVIX / Cryptoracle | 当前日频 token discovery 经一次直连重试后返回业务 code 200。本地已有 BTC/ETH 三种日指标共 2,280 个观测。 | 历史首次发布时间和修订政策未知，保存的时间带时区偏移，尚未验证可因果使用的股票信号。不提供股票价格或加密 L2。 |
| Index One | 当前公共 schema 经一次直连重试后返回 HTTP 200。此前有限 FX 查询成功。 | 股票与 ETF 历史覆盖及组合对账未验证。此前 HKD FX 精度不足，不适合精确估值。schema 可读不代表已验证股票权限。 |
| Algoseek | 官方 API 描述了美股、期权、期货与参考数据。 | 本轮未确认授权配置或本地数据，没有调用认证接口、购买或下载，未确认港股覆盖。 |
| CoinPaprika | 当前 BTC/ETH 最新 OHLCV 各返回 HTTP 200 和一根日线。本地各有 365 个日 ticker 价格点。 | ticker 价格与 24 小时量不是交易所 OHLCV、逐笔成交或盘口。此前深度 OHLCV 请求受限，不能直接用于本做市模拟器。 |
| IB Gateway | 本次只读握手成功，一只港股返回截至 2026-10-16 的 738 根日线。另一合约无法确认，随后 error 1100 中断采集，一次重连被拒绝。 | 完整的当前股票池、稳定连接、实时订阅以及账户和产品交易权限。配置 Paper 端口不能独立证明账户环境。 |

原始响应和账户同步信息保留在本地，没有更改账户设置、订阅、存储或部署工作流、生产数据指针。数据探测与回测是独立检查，不能证明完整的人工监督下单流程或研究到券商的接线。

官方资料见 [Cryptoracle](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/api-list/co-private-data/token-list)、[Index One](https://indexone.io/docs/api)、[Algoseek](https://algoseek.com/docs/rest-api/intro) 和 [CoinPaprika](https://coinpaprika.com/api/developers/)。产品介绍不代表本账户权限。

## 样本与解释边界

股票实验的港股输入只有 `HK.5`，`HK.2800` 仅作基准，美股只有 `US.SPY`。港股为 2023-10-18 至 2026-09-30 的 727 个对齐交易日，美股为 2023-10-03 至 2026-09-30 的 751 日。ETF OHLCV 来自此前冻结的 IBKR TRADES/RTH 采集。统一分析截止日是 2026-09-30，本次新取得的更晚港股数据没有加入比较，也没有从 CoinPaprika ticker 价格伪造 OHLC。

八个股票策略保持打包的模型参数与随机种子。回测覆盖项为本地计价单位初始资本 100,000、日频调仓、基准日历、8 bps 佣金、12 bps 滑点，以及港股 10 bps、美股零额外监管成本，均按交易名义金额计。这些是示意常数，不是已核验的当前 IBKR 费率，各策略的风险限制仍按原配置。信号后移不能消除 CNN 训练泄漏。每日目标权重记账、未核验的复权与分红、当前固定股票池、极小的资产覆盖和日线成交代理，都使其无法成为投资业绩证明。不同暴露水平也会使近似单资产持有的对照组明显胜过受仓位限制的信号策略。

港股月频样本经预热后从 2024-11-01 开始，共 471 个观测，成本 10 bps，保留原现金与仓位上限。五区域 ETF 从 2024-12-02 开始，共 423 个共同交易日，成本 10 bps。加拿大因历史权限缺失被排除，模型比较原币价格收益，Sharpe 保留旧版每年 252 期惯例。旧函数没有完整实现汇率、分红、同步市场估值及自融资持仓账本，不能与股票实验直接比较。

加密使用单独保留的 2026-03-19 至 21 日归档样本，不是本次从四家服务商取得的数据。九个文件哈希与保留清单一致。本轮已执行检查没有发现相应的空值、非有限数值、乱序、非正价格或数量及重复成交。共有 3,581,577 个盘口快照、70,556 笔成交和 12,902 个资金费率观测，但交易场所、产品和时区来源未确认，质量扫描不能证明这些信息。模拟器按既有假设将时间作为 UTC。

B0–B3 保持原默认值，包括 tick 0.1、订单量 0.1、库存上限 1、挂撤单延迟 100 ms、零 maker 费率和一秒快照。由于没有已注资本金收益率分母或确认的计价币种，仅展示原数据计价单位的绝对 PnL，不计算百分比收益或 Sharpe。这不能证明实际成交、排队真实性或泛化能力。同价多单盘口量重叠仍是模型限制，归档回放不等于经确认的历史交易记录。

研究报告的 `completed` 只说明函数返回。本次发布另行将无持仓结果标为 `no_trades`，无可用 walk-forward fold 标为 `no_eligible_folds` 并将其表现留空。没有搜索参数、缩短训练窗口或改变测试预期来制造成功。公开股票表中的回撤按正幅度展示。

## 实际结果


### HK

| strategy | start / end | return | Sharpe | drawdown | evidence |
| --- | --- | ---: | ---: | ---: | --- |
| `cnn_image_pattern` | 2023-10-18 / 2026-09-30 | 22.77% | 1.539 | 4.65% | `in_sample_diagnostic` |
| `cnn_pattern` | 2023-10-18 / 2026-09-30 | 0.00% | N/A | 0.00% | `no_trades` |
| `cnn_pattern_mvp` | 2023-10-18 / 2026-09-30 | 22.77% | 1.539 | 4.65% | `in_sample_diagnostic` |
| `cnn_walk_forward_rank` | 2023-10-18 / 2026-09-30 | N/A | N/A | N/A | `no_eligible_folds` |
| `equal_weight` | 2023-10-18 / 2026-09-30 | 152.99% | 1.479 | 22.12% | `limited_universe` |
| `momentum_20d` | 2023-10-18 / 2026-09-30 | 6.91% | 0.717 | 3.84% | `limited_universe` |
| `random_turnover` | 2023-10-18 / 2026-09-30 | 152.99% | 1.479 | 22.12% | `limited_universe` |
| `sma_cross` | 2023-10-18 / 2026-09-30 | 13.62% | 1.068 | 4.65% | `limited_universe` |
| `hk_pure_momentum` | 2024-11-01 / 2026-09-30 | 10.60% | 1.758 | 2.81% | `limited_universe` |
| `hk_momentum_volatility` | 2024-11-01 / 2026-09-30 | 10.60% | 1.758 | 2.81% | `limited_universe` |

### US

| strategy | start / end | return | Sharpe | drawdown | evidence |
| --- | --- | ---: | ---: | ---: | --- |
| `cnn_image_pattern` | 2023-10-03 / 2026-09-30 | 13.30% | 1.395 | 4.04% | `in_sample_diagnostic` |
| `cnn_pattern` | 2023-10-03 / 2026-09-30 | 0.00% | N/A | 0.00% | `no_trades` |
| `cnn_pattern_mvp` | 2023-10-03 / 2026-09-30 | 13.30% | 1.395 | 4.04% | `in_sample_diagnostic` |
| `cnn_walk_forward_rank` | 2023-10-03 / 2026-09-30 | N/A | N/A | N/A | `no_eligible_folds` |
| `equal_weight` | 2023-10-03 / 2026-09-30 | 80.53% | 1.373 | 19.00% | `limited_universe` |
| `momentum_20d` | 2023-10-03 / 2026-09-30 | 5.63% | 0.966 | 1.91% | `limited_universe` |
| `random_turnover` | 2023-10-03 / 2026-09-30 | 80.53% | 1.373 | 19.00% | `limited_universe` |
| `sma_cross` | 2023-10-03 / 2026-09-30 | 6.00% | 0.934 | 2.07% | `limited_universe` |

### MULTI

| strategy | start / end | return | Sharpe | drawdown | evidence |
| --- | --- | ---: | ---: | ---: | --- |
| `global_pure_momentum` | 2024-12-02 / 2026-09-30 | 31.95% | 1.436 | 12.71% | `native_currency_proxy` |
| `global_defended_rotation` | 2024-12-02 / 2026-09-30 | 31.60% | 1.470 | 12.71% | `native_currency_proxy` |

### CRYPTO

| strategy | PnL | fills | peak inventory | evidence |
| --- | ---: | ---: | ---: | --- |
| `B0` | -235.370 | 5400 | 1.000 | `archived_diagnostic` |
| `B1` | -240.258 | 4939 | 1.000 | `archived_diagnostic` |
| `B2` | -6.684 | 463 | 0.738 | `archived_diagnostic` |
| `B3` | -256.235 | 5386 | 1.000 | `archived_diagnostic` |

四个加密变体在这个零费用模型和特定样本中均亏损。B2 亏损较少，不能证明其存在稳定优势。

## 复现与后续工作

两个研究包分别使用自己的锁文件和仓库外 `DATA_ROOT`、`UV_PROJECT_ENVIRONMENT`。需要授权输入和明确的配置、股票池文件，仓库不附供应商快照。股票命令为 `python -m equity_lab.cli backtest --strategy <name> --root <external-run-root> --config <backtest.yaml> --universe <universe.txt>`，每个策略设置独立 `report_path`，保留上文说明的原打包 YAML、成本和截止日。

加密调用现有 API `crypto_mm.backtest.run_backtest(strategy_id="B0", data_root=Path("<licensed-event-directory>"))`，分别运行 B1/B2/B3，用 `dataclasses.asdict(result)` 留存结果。两个包各自的合成 Demo 属于另一类输入。月频函数为 `strategies.hk_low_frequency.run_monthly_backtest` 与 `strategies.global_etf_rotation.run_monthly_rotation`。

JSON 保存输入、配置的 SHA-256 指纹和代码版本。输入指纹由排序后的源文件哈希计算，股票输入规范化与日期过滤关系另在本地清单保存。股票配置指纹涵盖原策略 YAML 和去掉机器路径的回测覆盖项，月频指纹引用所记版本的原默认值，加密指纹包含完整返回配置。股票 observations 指对齐交易日，加密指输入事件数。公开汇总无需原始授权数据即可阅读，完全复现仍需相同授权快照。

下一步包括恢复 Gateway、取得完整且含历史时点与复权语义的股票池、确认 Algoseek 权限、在叠加信号前解决 AIVIX 首次可用时间与修订语义、确认 Index One 股票覆盖和精度、核验盘口场所与产品来源和费用，以及取得足够的神经网络样本外历史。研究包没有券商接线。港股 v1 schema、客户端与券商订单身份关联、实际账户环境，以及人工监督下的 Paper 下单、回报、撤单、成交、重启和对账仍待解决。
