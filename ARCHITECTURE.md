# Competition workspace boundary

这个仓库是 2026 香港量化交易大赛的控制面，负责：

- 比赛规则、待确认事项和操作说明；
- 比赛专属参数、实验配置和 frozen run 元数据；
- 最终提交材料及其来源索引。

它不复制量化平台、数据供应商或交易执行实现。

## 代码归属

| 能力 | 权威位置 |
| --- | --- |
| 原始市场数据、数据质量和供应商适配 | `research-workspace/market-data-platform` |
| 因子、策略假设、生命周期和研究证据 | `research-workspace/strategy-research` |
| 策略计算、组合结果和应用层 | `research-workspace/strategy-app` |
| 数据编排、运行目录、原子发布和执行交接 | `research-workspace/strategy-pipeline` |
| IBKR 合约、订单、风控、对账和审计 | `research-workspace/quant-execution-engine` |

比赛仓库通过配置、版本锁定、运行清单和结果索引复用上述能力。只有当比赛
需求形成可复用能力时，才回迁到对应的 `research-workspace` 子项目；不要在本
仓库建立第二套执行引擎或数据平台。

## 推荐目录

```text
config/       比赛专属参数
docs/         规则、策略和操作文档
experiments/  比赛实验配置与结果索引
runs/         frozen run 元数据；大数据放在外部数据湖
.env.example  可提交的环境变量模板
.env.local    本机私有环境变量，不提交
```
