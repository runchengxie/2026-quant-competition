# Competition MVP status

更新时间：2026-09-10

## 已完成

- 项目协作要求已写入根目录 `AGENTS.md`：独立 worktree、功能分支、PR、合并和清理。
- 已建立 Paper-safe 的比赛配置：`config/competition-2026-hk.json`。
- 已支持基础港股市场契约：`HK / SEHK / HKD`。
- 已支持目标持仓与当前持仓之间的 BUY/SELL 差额规划。
- `run_target_rebalance_pipeline` 已将目标交接、差额规划和 Paper/dry-run 执行串起来。
- 已支持 frozen run 的 targets、lineage、resolved config、metrics 和 evidence 文件。
- 已补充 IBKR 港股合约映射和 intent 方向提交接口。
- 已增加 Paper-safe preflight：可验证 Paper/dry-run、目标交接、单票权重、dry-run rebalance 和可选 Gateway TCP 可达性；详见 `docs/operations/paper-preflight.md`。
- 已建立港股低频动量 + 波动率控制基线回测，比较 2800 买入持有、纯动量和动量+波动率组合；结果见 `docs/operations/hk-strategy-baseline-2026-09-10.md`。
- 基线使用当前 20 只港股日线快照，月度调仓、10 只持仓、2%现金、单票上限12%，只使用调仓日前收盘数据。

## 尚未完成

- 尚未完成真实 Paper Gateway smoke：连接、逐只合约 qualification、订单回报、撤单、断线重连和 reconciliation。
- preflight 的 Gateway 检查仅为 TCP 前置探测，不替代真实 Paper Gateway API smoke，也不证明行情权限或订单成交。
- 港股每只股票的真实 lot size、交易时段、最小价格和流动性门槛仍需以 IBKR/组委会确认结果覆盖配置中的 baseline。
- 尚未从研究系统导入真实比赛版 `targets.json`、`lineage.json` 和冻结 OOS 绩效结果。
- 基准、持仓率、换手率和稳定性指标的赛事计算口径仍待组委会书面确认。
- 尚未运行连续 Paper shadow；真实运行证据和每日绩效报告尚未生成。
- 基线回测不是完整比赛宇宙，也不代表已经具备港股实时行情权限；港股当前仍以历史 + 延迟行情为已确认状态。
- NautilusTrader 常驻运行时和 Gateway 回调 wiring 仍是后续集成工作，不属于本次 broker-neutral MVP。

## 运行约束

- 当前配置固定为 `environment=paper`、`dry_run=true`。
- 不得将 `.env.local`、凭据、账户信息、订单日志或运行产物提交到 Git。
- 在 Paper smoke 完成前，不得启用 live guard 或把测试结果表述为真实券商验证。
