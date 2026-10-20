# 项目结构与当前限制

[English](project-overview.md) · [文档目录](README.zh-CN.md)

## 各部分怎样配合

研究部分负责准备数据、试跑策略和生成报告。执行部分读取明确的目标持仓，检查后计算它与当前持仓的差别。研究报告本身不能直接当作下单指令。

| 目录 | 负责的事 |
| --- | --- |
| `research/equity-lab` | 股票日线实验和六市场国际组合诊断 |
| `research/crypto-mm` | 加密市场日线实验和基于订单簿的做市模拟 |
| `research/platform-compare` | 本地现金与股数账本、记账对照和五市场下一开盘实验 |
| `src/competition_tools` | 安装、准备数据、评估和检查报告 |
| `src/packages` | 目标持仓格式、市场规则、风控、审计和对账 |
| `src/strategies/nira` | 读取外部生成的 Nira 目标文件 |
| `src/adapters` | 券商和数据服务接口 |
| `src/apps/execution_runner` | 执行程序的配置和交易流程 |
| `site` | 中英文项目网站 |
| `tests` | 根项目测试 |

三个研究包各自管理依赖和锁文件，都不需要安装外部量化框架。从原框架提取的记账代码保留 Apache-2.0 许可和来源清单，研究适配代码保留各自的目录级许可。

## 执行交易前要知道的事

研究向执行部分交付带版本的 `targets.json` 和 `lineage.json` 文件。执行程序不会导入外部 research-workspace 或 Nira 源码。

默认执行环境是 Paper，也就是模拟账户。程序里的 `RunnerSettings` 和配置解析器默认 `dry_run=false`。只检查、不提交时，调用方必须明确设置 `dry_run=true`。预检要求同时使用 Paper 和 dry-run。券商操作前先读[运行检查清单](operations/release-checks.md)。

当前执行程序只接受 v1 目标格式。已发布的 v1 JSON Schema 支持 JP/US，运行时代码还识别 HK，两者尚未统一。[国际 v2 目标设计](strategy/target-manifest-v2.md)描述了股票、ETF 和期货的标识，但尚未成为当前执行格式。模拟账户的提交、撤单、成交，以及重启后的恢复和对账，仍需由人监督验证。

## 策略研究的进度

团队正在比较香港股票的时点基本面与截面排名组合，以及使用 AIVIX 加密情绪信号的美股 ETF 思路。比赛策略尚未最终确定或注册。数据授权、样本外表现、账户权限和模拟交易行为都还需要验证。

[24 项策略记录](research/strategy-validation-2026-10-19.zh-CN.md)与[扩展数据评估](research/data-expansion-and-evaluation.zh-CN.md)记录的是不同批实验，阅读时应保留各自的日期和限制。这些结果不能证明从数据到下单的整条流程已经可用，也不能保证未来收益。

## 数据和私人配置放在哪里

输入数据、模型文件、生成的报告和运行日志放在源码之外，使用明确配置的数据目录。私人配置和密钥也放在源码之外。具体方法见[私人配置与数据服务](operations/environment-and-providers.zh-CN.md)。

比赛日期和账户要求见[规则摘要](competition/rules.md)，以主办方最新通知为准。
