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
├── rules.md
├── rules.pdf
└── competition-analysis.md
```

`rules.pdf` 是比赛原始规则文件。

`rules.md` 是根据原始 PDF 整理的 Markdown 版本，保留了主要标题、编号、列表、表格和计算公式，便于搜索、引用和版本管理。

`competition-analysis.md` 是根据规则、公开资料和相关讨论整理的分析文档，内容涵盖赛事背景、账户结构、评分方式、策略选择和全球股票市场指数增强方案。

## 当前策略定位

当前拟报名的策略定位为：

> 基于 Point-in-Time 基本面与横截面排序模型的全球股票市场指数增强策略

策略以全球股票市场为投资范围，重点考虑美国、欧洲、日本、香港及其他符合流动性和数据要求的市场。核心方法包括：

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

参赛前需要重点确认持仓率、换手率、衍生品名义价值、跨市场货币转换及加密资产周末统计等计算口径。详细清单见 [competition-analysis.md](competition-analysis.md)。

## 阅读顺序

建议先阅读 [rules.pdf](rules.pdf)，了解原始规则，再阅读 [competition-analysis.md](competition-analysis.md)，查看规则解读和策略建议。

## 研究边界

本文档中的公司背景、高校合作、监管身份、资金合作机会和官网披露数据，部分仍需要通过官方文件或书面回复进一步核实。文档中的策略内容属于研究讨论，不构成投资建议，也不代表最终报名材料或实际交易指令。

## 参考资料

- [Hong Kong Companies Registry](https://www.cr.gov.hk/)
- [Fund Connect HK](https://fundconnecthk.com/)
- [HKU Business School](https://www.hkubs.hku.hk/)
