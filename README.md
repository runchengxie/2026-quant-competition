# 2026 Hong Kong Quantitative Trading Competition

2026 年香港量化交易大赛的规则文件、参赛分析和策略研究笔记。

## 项目内容

本项目主要用于整理以下信息：

- 比赛规则和时间安排
- IBKR 账户授权和资金安全边界
- 主办方、高校合作方及相关公司信息
- 持仓率、换手率和奖项规则
- 全球股票市场多头或指数增强策略的设计思路
- 报名和参赛前需要向组委会确认的问题

## 文件说明

```text
2026-hk-quant-trading-competition/
├── README.md
├── docs/
│   ├── competition/       # 规则与比赛解读
│   ├── strategy/          # 参赛策略研究
│   ├── operations/        # IBKR 与团队系统操作指南
│   └── superpowers/       # 文档架构设计与执行计划
├── packages/               # contracts, audit, reconciliation, policies
├── strategies/nira/        # external targets.json handoff only
├── adapters/               # Nautilus boundary and IBKR event mapping
├── apps/execution_runner/  # Paper-first runner configuration
└── tests/
```

原始 PDF 作为附件保存在 [GitHub Releases](https://github.com/runchengxie/2026-hk-quant-trading-competition/releases/tag/reference-pdfs-2026-09)；可搜索的规则、策略分析和操作指南分别放在对应主题目录。

- [比赛规则](docs/competition/rules.md)
- [原始 PDF 下载](https://github.com/runchengxie/2026-hk-quant-trading-competition/releases/tag/reference-pdfs-2026-09)
- [比赛解读与策略建议](docs/competition/competition-analysis.md)
- [参赛策略分析](docs/strategy/strategy-analysis.md)
- [IBKR 模拟账户指南](docs/operations/ibkr-simulated-account-guide.md)
- [团队 Token 指引](docs/operations/team-token-guide.md)
- [执行发布检查](docs/operations/release-checks.md)

执行层与 Linux 研究层通过版本化的 `targets.json` 和 `lineage.json` 交接，不直接导入
`research-workspace` 或 Nira 源码。执行层默认为 Paper，发布检查和证据要求见
[执行发布检查](docs/operations/release-checks.md)。

## 当前策略定位

当前拟报名的策略定位为：

> 基于 Point-in-Time 基本面与横截面排序模型的港股多头指数增强策略

策略以港股为主投资范围；全球股票策略仅作为扩展研究方向。核心方法包括：

- 使用 `Point-in-Time` 数据，减少未来信息泄漏
- 根据盈利质量、财务稳健性、估值、盈利预期修正、动量和低波动等因素进行横截面排序
- 使用机器学习 `Ranker` 对具有经济含义的特征进行组合
- 通过 `Top-K` 持仓和进入、退出缓冲降低无效换手
- 控制国家、区域、行业、个股、Beta、`Tracking Error` 和风格暴露
- 在组合层面管理流动性、交易成本、组合波动率和最大回撤

报名类别建议选择多头或指数增强策略。

## 比赛关键信息

按现有规则，正式交易阶段为香港时间：

- 2026 年 9 月 28 日 00:00 至 2026 年 12 月 29 日 06:00
- 正式交易阶段约三个月
- 资格条件提供持仓率和换手率两条路径，满足其中一条即可
- 交易阶段评价包括收益、Sharpe、最大回撤和稳定性

参赛前需要重点确认持仓率、换手率、衍生品名义价值、跨市场货币转换及加密资产周末统计等计算口径。详细清单见 [赛前时间与确认清单](docs/competition/schedule-and-checklist.md)。

## 阅读顺序

1. 先看 [比赛规则](docs/competition/rules.md)，必要时对照 [原始规则 PDF](https://github.com/runchengxie/2026-hk-quant-trading-competition/releases/download/reference-pdfs-2026-09/rules.pdf)。
2. 再看 [比赛解读](docs/competition/competition-analysis.md)，了解账户、评分、奖项和待确认问题。
3. 然后看 [参赛策略分析](docs/strategy/strategy-analysis.md)。
4. 需要开通账户或提交凭据时，查看 `docs/operations/` 下的操作指南。

## 研究边界

本文档中的公司背景、高校合作、监管身份、资金合作机会和官网披露数据，部分仍需要通过官方文件或书面回复进一步核实。文档中的策略内容属于研究讨论，不构成投资建议，也不代表最终报名材料或实际交易指令。

## 参考资料

- [Hong Kong Companies Registry](https://www.cr.gov.hk/)
- [Fund Connect HK](https://fundconnecthk.com/)
- [HKU Business School](https://www.hkubs.hku.hk/)
