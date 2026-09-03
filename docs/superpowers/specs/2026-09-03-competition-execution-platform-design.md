# 比赛执行平台架构设计

## 目标

建立一个轻量、可审计、支持国际市场的比赛执行平台：Linux/Nira 生成目标，Windows 上的 NautilusTrader 执行运行时通过 IBKR Gateway 连接 Paper 或经人工批准的 Live 账户。

## 边界

本项目不复制 `research-workspace`、Nira 或其数据资产。研究侧只输出版本化的 `targets.json`、`lineage.json` 和必要的信号元数据。本项目消费这些产物，负责执行前检查、订单生命周期、券商事实、恢复和比赛报告。

## 组件

```text
Nira / research-workspace
        │ targets.json + lineage.json
        ▼
contracts + market_model + risk
        ▼
NautilusTrader execution runner
        ▼
IBKR adapter → Windows IB Gateway → IBKR account
        │
        ├── OrderEvent / Fill event journal
        ├── Rebuildable order projection
        └── Reconciliation and audit evidence
```

### Contracts

目标文件描述研究侧希望达到的组合，不直接描述券商 SDK 对象。`OrderIntent` 表达经过风险批准的单笔意图。`OrderEvent` 和 `Fill` 使用稳定的 JSON schema，时间统一为 UTC，数量和价格保留十进制定点语义。

### Market model

市场模型负责把标准代码解析为交易所合约，并维护交易所、币种、最小手数、交易时段、费用和汇率规则。日本代码例如 `1321.T`、`7203.T` 不得按美股 `.US` 规则处理。

### Execution runner

Windows runner 保持到 Gateway 的常驻连接，消费目标命令，监听订单状态、成交、错误、连接变化和账户事件。提交结果只表示 Gateway 已接受提交动作；最终状态必须由事件或对账确认。

### State and recovery

事件日志是追加写入的事实记录。当前订单、持仓和运行摘要是可由事件重建的 projection。启动时先加载本地事件，再查询 Gateway 做 reconcile。连接中断、重复事件和未知提交结果必须保持幂等。

### Execution policies

第一阶段只支持安全的单笔限价/市价订单和撤单。TWAP、VWAP、POV 等算法作为独立的执行策略层接入，不能写入 IBKR adapter。算法必须接收统一的订单意图并输出子订单计划。

## 仓库策略

采用局部 monorepo：比赛执行、契约、市场模型、风险和审计放在本仓库；研究仓库和 Nira 保持独立。稳定共享代码只通过小型版本化 package 或标准文件契约复用。

## 环境策略

- Paper Gateway 默认使用 Windows `127.0.0.1:4002`。
- 实盘配置不得放入项目 `.env` 文件。
- RQData 和 Cryptoracle 凭证只由本地环境注入，并且不进入事件日志。
- Linux 不直接持有 IBKR API 连接；Windows runner 是唯一的 Gateway 客户端。

## 验收标准

1. Paper 账户可以识别美股、日本股票和日本 ETF 合约。
2. 事件流能够记录提交、接受、部分成交、成交、撤单、拒单、错误和断线。
3. runner 重启后不会重复报单，并能通过 reconcile 恢复未知状态。
4. `targets.json` 能从 Nira 导出并经过 schema、市场和风险验证。
5. 订单和成交证据可导出给比赛方，同时不泄露凭证。
6. Paper 和 Live 配置在代码和运行时上明确隔离。
