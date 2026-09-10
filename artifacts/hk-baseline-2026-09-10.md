# 港股低频动量 + 波动率基线回测

- 快照日期：2026-09-10
- 股票数量：20
- 股票样本：2023-09-05 至 2026-09-03
- 基准：`HK_2800.csv`，2023-09-05 至 2026-09-03
- 成本假设：佣金 + 滑点合计 10.0 bps

## 比较结果

| 组合 | 累计收益 | Sharpe | 最大回撤 | 正收益日占比 | 调仓次数 | 平均调仓换手 |
|---|---:|---:|---:|---:|---:|---:|
| 2800_buy_and_hold | 35.44% | 0.56 | 20.56% | 49.25% | 0 | 0.00% |
| pure_momentum | 21.33% | 0.52 | 23.93% | 49.89% | 24 | 34.30% |
| momentum_volatility | 33.99% | 0.76 | 19.87% | 52.22% | 24 | 30.22% |

## 解释与限制

- Only 20 HK stocks are available; this is not a complete historical competition universe.
- No point-in-time constituents or fundamentals are used.
- No realtime, bid/ask, depth, tick, or order-level data is used.
- Daily close execution is a research proxy and does not prove live fillability.
- Competition rule interpretation, benchmark, and turnover threshold still require organizer confirmation.

该结果仅证明在当前 20 只港股日线快照上的历史研究表现；不能证明已经具备韩国/港股实时行情权限，也不能直接作为实盘下单许可。
