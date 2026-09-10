# 港股基线策略 Paper shadow 清单

适用策略：`momentum_volatility` 低频港股基线。当前只允许 Paper、dry-run 和只读验证。

## 数据与信号

- [ ] 确认每日输入是已完成交易日的收盘数据，不把 IBKR 延迟 Last 当作实时成交价。
- [ ] 确认 20 只股票及 `2800` 的日期、币种、复权/分红口径一致。
- [ ] 信号时间戳早于下一交易日执行时间；不得读取执行日收盘价生成同日信号。
- [ ] 每月只生成一次目标组合；缺少历史或合约资格的股票进入排除清单。

## 组合与比赛约束

- [ ] 默认 10 只持仓、单票不超过 12%、现金 2%。
- [ ] 记录持仓率、空仓天数、调仓换手和成本假设。
- [ ] 用 2800 计算相对收益，但不把 2800 混入港股股票 alpha 池。
- [ ] 书面确认比赛的基准、持仓率、换手率、流动性和价格门槛口径。

## IBKR Paper 运行

- [ ] 使用 Paper IB Gateway `127.0.0.1:4002` 或明确记录的 TWS Paper 端口。
- [ ] 逐只确认 `SEHK/HKD` 合约 qualification；不能用 socket 连接成功代替行情权限确认。
- [ ] 记录实时行情错误（如 354/10089）与延迟行情类型（marketDataType=3）并分开标记。
- [ ] 保持 `environment=paper`、`dry_run=true`，先验证目标生成、订单意图、差额规划和回报落盘。
- [ ] 一次只保留一个 TWS/Gateway API 会话，避免 10197/2103/2110 干扰诊断。

## 证据与放行

- [ ] 每次运行保存输入快照、resolved config、targets、lineage、订单意图、回报和 reconciliation 结果。
- [ ] 连续 Paper shadow 至少覆盖一个月度调仓周期，且每日绩效报告可重算。
- [ ] Flex Query 能提供 trades、cash transactions 和 NAV Summary（Base）。
- [ ] 在上述证据齐全前，不启用 live guard，不发送实盘订单。
