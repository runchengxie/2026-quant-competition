# 当前市场与资产数据清单

> 盘点日期：2026-09-10  
> 盘点范围：本机 `D:\data\` 外部数据根目录、相关研究配置与 manifest。  
> 口径：只有实际存在且可以读取的文件才标记为“已落盘”；配置、权限探针和代码支持不等同于已获得数据。

## 一览

| 状态 | 市场/区域 | 资产大类 | 当前拿到的数据 | 频率/层级 | 最新可见日期 | 结论 |
|---|---|---|---|---|---|---|
| 已落盘 | 香港 | 股票 | 20 只高流动性港股 | 日线 OHLCV，IBKR `TRADES` 聚合 | 2026-09-03 | 可用于历史价格代理与流动性筛选 |
| 已落盘 | 香港 | ETF | 2800 | 日线收盘价与成交量，IBKR `TRADES` 聚合 | 2026-09-03 | 属于 global-six-market，不是 HK competition 股票池 |
| 已落盘 | 美国/香港/英国/澳大利亚/加拿大/新加坡 | ETF | SPY、2800、ISF、STW、XIU、ES3 | 日线收盘价与成交量 | 2026-09-03/04 | 跨市场配置研究；非 HK 比赛主策略 |
| 已落盘 | 多市场 | FX | USDHKD、GBPUSD、AUDUSD、USDCAD、USDSGD | 日线 | 2026-09-04 | 用于 global-six-market 的 USD 换算 |
| 已落盘 | 美国/欧洲/日本/香港 | 股指期货 | ES/MES、NQ/MNQ、YM/MYM、RTY/M2K、NKD/NIY、DY、HS、FX、MX | 连续合约 1 分钟 OHLCV | 2026-08-05；部分欧洲/香港品种 2026-07-17 | Databento GLBX/国际连续合约研究数据 |
| 已落盘 | 美国 | 能源期货 | CL、MCL | 连续合约 1 分钟 OHLCV | 2026-08-05 | 可用于能源期货研究 |
| 已落盘 | 美国 | 贵金属/工业金属期货 | MGC、SIL、HG | 连续合约 1 分钟 OHLCV | 2026-08-05 | 没有在当前 `data_ext` 中看到 GC/SI 等大合约文件 |
| 已落盘 | 美国 | 农产品期货 | ZS | 连续合约 1 分钟 OHLCV | 2026-08-05 | 可用于农产品研究 |
| 已落盘 | 美国 | 利率期货 | ZN | 连续合约 1 分钟 OHLCV | 2026-08-05 | 10 年期国债期货 |
| 已落盘 | 美国/CME | 加密货币期货 | MBT | 连续合约 1 分钟 OHLCV | 2026-08-05 | 仅 CME 比特币微型期货，不是现货或交易所订单簿 |
| 已落盘 | 美国 | ETF | TLT | 1 分钟 OHLCV | 2026-02-09 | 位于 futures-strategy 数据目录，需与期货数据分开使用 |
| 已落盘 | 越南 | 股票 | 50 只研究样本；HOSE/HNX/UPCoM | 日线；VCI + KBS 原始与标准化记录 | 2026-08-27 | 有质量报告，但复权语义仍未完全确认 |
| 仅探针 | 美国/香港/日本/新加坡/英国/澳大利亚/加拿大/德国 | 股票 | AAPL、700、7203、D05、VOD、BHP、SHOP、SAP | IBKR 合约/权限/短历史检查 | 2026-09-03/04 | 没有对应完整数据集，不计入已落盘资产 |

## 1. 香港比赛相关数据

### 1.1 港股股票：已落盘

路径：`D:\data\hk-competition-2026\raw\ibkr\`

- 标的数：20；代码为 `5、700、941、9988、3690、9618、1299、2318、2388、1398、3988、939、2628、386、883、1024、1810、2015、1211、1093`。
- 每只 738 根日线，覆盖 `2023-09-05` 至 `2026-09-03`。
- 字段：`date, open, high, low, close, volume, average, bar_count`。
- 来源：IBKR 历史行情，`what_to_show=TRADES`，`bar_size=1 day`，`use_rth=true`。
- 完整性抽查：20 个文件均无重复日期、无空收盘价。
- 局限：这是当前流动性股票的价格代理，不是历史港股通成分，也不包含 PIT 基本面。

证据：

- `D:\data\hk-competition-2026\raw\ibkr\manifest.json`
- `D:\data\hk-competition-2026\raw\ibkr\liquidity_probe.json`
- `docs/operations/ibkr-data-probe-2026-09-03.md`

### 1.2 香港 ETF：已落盘 1 只

路径：`D:\data\global-six-market\raw\ibkr\daily\HK_2800.csv`

- `2800`（盈富基金/HK 市场代理）共 738 根日线，覆盖 `2023-09-05` 至 `2026-09-03`。
- 字段只有 `date, close, volume`，没有盘口、逐笔或完整 OHLC 字段。
- 它属于 `global_six_market` 的香港资产代理，不是 HK competition 的 20 只股票池。

当前没有发现一组已经下载的港股 ETF 池，也没有 HSCI 成分历史文件或比赛版完整 PIT 数据文件。

## 2. 跨市场 ETF 与外汇

路径：`D:\data\global-six-market\raw\ibkr\`

### ETF 代理

| 市场 | 标的 | 行数 | 覆盖 |
|---|---|---:|---|
| 美国 | SPY | 753 | 2023-09-05 至 2026-09-03 |
| 香港 | 2800 | 738 | 2023-09-05 至 2026-09-03 |
| 英国 | ISF | 759 | 2023-09-05 至 2026-09-03 |
| 澳大利亚 | STW | 760 | 2023-09-06 至 2026-09-04 |
| 加拿大 | XIU | 754 | 2023-09-05 至 2026-09-03 |
| 新加坡 | ES3 | 754 | 2023-09-06 至 2026-09-04 |

这些文件是日线收盘价/成交量，实验文档标注为 price-return research diagnostic，不能直接视为 total-return 数据。

### FX

已落盘 5 条日频外汇序列：`USDHKD、GBPUSD、AUDUSD、USDCAD、USDSGD`。共同历史大致为 `2023-09-06` 至 `2026-09-04`。部分 manifest 中使用了按货币命名的文件别名（例如 `HKD.csv`），实际目录中也存在按货币对命名的文件，使用前应以文件清单和输入锁逐项核对。

global-six-market 当前仍是 `exploration`，paper-shadow 未完成，不能当作比赛晋级结论。

证据：

- `D:\data\global-six-market\raw\ibkr\manifest.json`
- `D:\data\global-six-market\runs\ibkr_20260904_total_return_shadow_audit3\inputs.lock.json`
- `research-workspace/strategy-research/research/experiments/global_six_market/README.md`

## 3. 期货、ETF 与其他衍生品数据

主要路径：

- `D:\data\futures-strategy\data_ext\`
- `D:\data\futures-strategy\data\`

当前 `data_ext` 和 `data` 各有 23 个同名 Parquet 品种文件，当前可核对的 `data_ext\coverage.csv` 覆盖如下：

| 大类 | 文件/品种 |
|---|---|
| 股指期货 | `ES、MES、NQ、MNQ、YM、MYM、RTY、M2K、NKD、NIY、DY、HS、FX、MX` |
| 能源期货 | `CL、MCL` |
| 贵金属/工业金属 | `MGC、SIL、HG` |
| 农产品 | `ZS` |
| 利率期货 | `ZN` |
| 加密货币期货 | `MBT` |
| ETF | `TLT` |

数据形态：

- Databento GLBX/国际市场来源的连续合约 1 分钟 OHLCV；
- `ts_event` 为 UTC 时间戳，另有 `trading_day`、连续合约代码和成交量；
- 主连按月度成交量规则拼接，不是单一固定到期合约；
- 不是订单级数据，也不是 5 档/10 档盘口。

当前最近的统一覆盖大多到 `2026-08-05`；DY/HS/FX/MX 等国际品种在 coverage 表中只到 `2026-07-17`，TLT 只到 `2026-02-09`。`data\README.md` 还描述了较长历史版本，但实际使用时应以具体文件和 coverage manifest 为准。

## 4. 越南股票数据

路径：`D:\data\vietnam-quant-research\pilot-v6\`

- 股票研究样本：50 只；交易所分布目标为 HOSE 30、HNX 10、UPCoM 10。
- listing/instrument master：3,586 条市场名录记录，其中包含已退市和未知交易所记录；这不是 3,586 只股票都有完整价格数据。
- 价格日线：`bronze\price_daily.jsonl` 共 175,554 行，日期 `2018-01-02` 至 `2026-08-27`。
- 来源：VCI 93,724 行，KBS 81,830 行；同时保留 raw、标准化和来源仲裁结果。
- 质量：研究质量状态为 `PASS_WITH_QUARANTINE`，有 454 行隔离记录；价格复权/语义状态仍为 `unresolved`，`factor_ready=false`。
- 数据层级：日线 OHLCV/公司名录/公司行动诊断，不是实时、逐笔或盘口数据。

证据：

- `D:\data\vietnam-quant-research\pilot-v6\metadata\research_quality_report.json`
- `D:\data\vietnam-quant-research\pilot-v6\metadata\price_semantics_report.json`
- `docs/daily-data-loop-v0.md`

## 5. 只有访问探针、尚未形成数据集的市场

`D:\data\ibkr-market-coverage\coverage_probe.json` 记录了 IBKR 对以下市场/标的的合约资格或短历史请求：

- 美国：AAPL
- 香港：700
- 日本：7203
- 新加坡：D05
- 英国：VOD
- 澳大利亚：BHP
- 加拿大：SHOP
- 德国：SAP

这份文件主要证明合约识别和部分短历史请求状态，不代表已经保存了完整可研究行情。探针显示日本 TSEJ 股票和德国 IBIS 股票存在无行情权限错误；港股/美股等实时权限仍需单独验证。

另有 `D:\data\japan-equities-ibkr\permission_probe.json`，它是日本股票 `7203.T` 的权限探针，不是历史价格文件。

## 5.1 IBKR 权限探针记录（截至 2026-09-10）

本节记录当前最可靠的已确认状态。后续轮询因 Gateway 的账户同步、证券定义和市场数据服务连接中断而未完成，因此“未确认”不等同于“没有权限”。

| 市场/资产 | 已确认情况 |
|---|---|
| 港股 `700` | 合约可识别；历史日线可取；实时行情未订阅；延迟 `Last` 可取 |
| 港股 ETF `2800` | 合约可识别；历史日线可取；实时行情未订阅；延迟 `Last` 可取 |
| 加拿大股票 `SHOP` | 合约和短历史可取 |
| 日本股票 `7203` | 合约可识别，但历史行情返回无 `TSEJ` 行情权限 |
| 德国股票 `SAP` | 合约可识别，但历史行情返回无 `IBIS` 行情权限 |
| FX | 尚未得到稳定的实时报价确认 |
| 期货 | 本轮未完成期货权限确认 |

当前最稳妥的权限结论：

- 港股：历史 + 延迟行情；
- 部分海外市场：合约 + 短历史；
- 日本 `TSEJ`：无历史行情权限；
- 德国 `IBIS`：无历史行情权限；
- 实时行情：尚未确认，没有发现新的已确认实时行情权限。

本轮失败原因包括 IBKR `2103`（市场数据连接中断）、`2110`（TWS 与服务器连接中断）和 `2157`（证券定义服务连接中断）。这些连接错误与 `354/10089`（实时市场数据未订阅）应分开解释。

## 6. 当前没有拿到或没有接通的数据

- HK competition 完整历史 PIT 财报、历史港股通成分和冻结 OOS 输入：缺失。
- 港股实时行情：当前账户只能收到延迟行情；实时 SEHK market-data subscription 尚未确认。
- 港股 Level 1 Bid/Ask、五档/十档、Level 2、tick-by-tick、订单簿：没有落盘，也没有接入当前比赛项目。
- HK competition 的连续实时监控服务：项目只有 Paper/dry-run 执行骨架，尚未形成常驻行情订阅器。
- 多数 IBKR 探针标的的完整历史文件：没有。
- 越南实时行情、盘口和逐笔：没有。
- 期货 tick、订单簿和 MBO：当前 `futures-strategy` 目录主要是 1 分钟 OHLCV；另有独立 `us-futures-mbo` 项目，但不能把其代码/配置视为已拿到 MBO 数据。

## 7. 使用时的建议

1. HK competition 主策略目前应按“20 只港股日线价格代理 + 外部 PIT 数据缺失”处理，不要把 `2800` 或 global-six-market 直接混进主股票池。
2. 需要实时交易监控时，应单独记录：实时/延迟状态、Bid/Ask、行情时间戳、权限、重连次数和 Gateway 会话 ID。
3. 期货研究应区分 `data`、`data_ext`、`newdata_extract` 和具体 coverage 文件，避免把不同快照和重复副本混用。
4. 越南数据可以用于日频研究，但在复权语义确认前，不应把 `factor_ready=false` 的结果作为生产因子输入。
5. 所有外部数据根目录都不在 Git 版本控制中；运行或迁移时应以 manifest、输入锁和文件 hash 作为证据。
