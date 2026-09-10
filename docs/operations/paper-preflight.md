# Paper-safe execution preflight

该 preflight 只验证执行前置条件，不提交订单、不请求撤单，也不把 TCP 连接成功解释为行情权限或成交确认。

## 使用

```powershell
uv run --extra test python scripts/run_paper_preflight.py `
  --targets path\to\targets.json `
  --config config\competition-2026-hk.json `
  --output runs\preflight.json
```

如果需要检查本机 Paper Gateway 的 TCP 可达性，再显式添加：

```powershell
uv run python scripts/run_paper_preflight.py `
  --targets path\to\targets.json `
  --config config\competition-2026-hk.json `
  --check-gateway
```

## 检查项

- `execution_safety`：必须是 `environment=paper` 且 `dry_run=true`；环境变量覆盖配置时以解析后的结果为准。
- `target_handoff`：校验 `targets.json`、可选 sibling `lineage.json`、市场和策略标识。
- `target_risk`：检查配置中的最大单票权重和目标权重总和。
- `dry_run_rebalance`：生成差额 intent，但通过 `dry_run` 保证不调用 broker adapter。
- `gateway`：默认 `skipped`；显式检查时只做 TCP connect，失败状态为 `blocked`。

## 状态解释

- `pass`：本项通过。
- `fail`：输入或安全条件不满足，应先修复。
- `blocked`：外部条件不可达，例如 Gateway 没有监听；不等价于订单拒绝或市场数据无权限。
- `skipped`：本次未请求该检查。

建议把 JSON 报告留在本地 `runs/`，不要提交账户信息、凭证、订单日志或包含敏感数据的运行产物。
