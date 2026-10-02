# USD price ledger delivery — 2026-10-03

## Platform delivery

The approved [Stage A plan](../superpowers/plans/2026-10-02-usd-price-ledger-stage-a.md)
is implemented in the public reusable platform, through
[quant-platform PR #98](https://github.com/runchengxie/quant-platform/pull/98).

Platform revision: [`4cc08be1b80d200eab2eabff3ff58bf82e465eab`](https://github.com/runchengxie/quant-platform/commit/4cc08be1b80d200eab2eabff3ff58bf82e465eab).

Public import paths:

```python
from portfolio_backtester.usd_ledger import run_usd_price_replay
from portfolio_backtester.usd_ledger_bundle import write_usd_price_replay_bundle
from portfolio_backtester.usd_ledger_models import USDReplayRequest
```

See the [platform guide](https://github.com/runchengxie/quant-platform/blob/main/docs/reference/usd-price-ledger.md)
for complete synthetic examples and record signatures. Research consumers must
pin the reviewed reachable revision in their own environment and lockfile.
This competition repository has not installed that consumer or changed the
legacy baseline calculation.

## Implemented capability

- Long-only cash-equity and ETF quantities with explicit USD cash. Holdings stay
  fixed between transactions; weights drift with local prices and FX.
- Explicit direct/inverse historical FX, units, UTC timestamps, maximum mark
  ages, immutable source references and caller-attested session policy.
- Chronological execution: future sales cannot fund earlier buys; same-time
  sells precede affordable buys. Record commission, slippage and FX costs,
  proportional scaling, fractional/integral lot rounding and residual cash.
- Retain all-cash periods and liquidation dates. Report cumulative price-NAV
  return, drawdown and calendar-time CAGR; omit Sharpe without a sampling policy.
- Preserve sequenced mark updates, decision NAV, target sizing, modeled
  transactions and valuations. The publisher independently replays this evidence
  and checks both P&L components, cash, inventory, costs, lineage and clocks.
- Publish immutable diagnostic bundles through the existing platform writer.
  Decimal strings preserve financial precision. Orders/fills are empty;
  `order_lifecycle=False`, `orders_submitted=False`, `return_basis=usd_price_nav`.

Provider acquisition, real datasets, credentials, strategy parameters and runtime
orchestration were not added to quant-platform.

## Verification evidence

- Platform PR #98 merged after all repository CI checks passed, including
  Python 3.12/3.13 dependency modes, full checks/security audit and Rust checks.
- Local full platform suite: **1,578 passed, 12 skipped**, with 10 existing
  pandas/numpy warnings. Ruff, formatting and Linux-target type checks passed.
- The new mechanism also passed in the lean dependency environment. Package
  building, module inventory, the executable synthetic guide and strict MkDocs
  build were checked.
- One fresh independent whole-branch review found two Important publication
  issues: offsetting P&L mutations and inconsistent target sizing/lineage. Three
  failing regression tests reproduced them; ordered evidence replay fixed them;
  the complete suite passed afterward. No Critical/Minor findings were reported.
- Windows verification used Python 3.12, UTF-8 mode and an isolated pytest temp
  directory. The machine's default Python 3.14 cannot build an existing optional
  dependency; its default pytest temp root denies access. No unrelated dependency
  or permission changes were made. Type checks use Linux to match repository CI;
  an existing Unix-only resource helper is not a Windows type-check target.

These are synthetic mechanism checks, not a new real-data backtest or Paper
order lifecycle. No account information, positions or return figures are published.

## Remaining integration

1. Research/data owners must publish immutable price/FX assets with availability
   and session semantics. Existing date-only CSVs in ignored local `runs/` cannot
   be relabeled as verified execution marks. No files were moved in this delivery.
2. A separate research consumer plan must pin the merged platform revision,
   preserve/version the signal schedule, apply matched benchmark clocks/costs,
   and publish an official diagnostic research manifest and separate targets.
3. Dividend/split source conventions and total-return accounting remain Stage B.
   Futures require their own settlement/margin capability; both fail closed now.
4. Provider status remains as recorded in the
   [FX validation update](provider-fx-validation-2026-10-02.md): Index One FX
   queries authenticated, precision needs resolution; AIVIX endpoints need
   confirmation; QuantZone factor observations/PIT semantics are not verified.
5. International v2 targets remain interchange-only. The execution runner still
   rejects them before broker/journal side effects. Broker execution is unchanged.

## 简体中文摘要

通用 USD 价格净值账本已在 quant-platform 实现：按实际股数持仓、保留美元现金，
明确 FX 方向、费用和调仓资金顺序，并在发布前逐事件复算损益与目标股数。
完整本地测试 1,578 项通过，12 项跳过；独立审查发现的两处问题已有回归测试并修复。

比赛项目目前记录平台版本和接入路径，尚未接入真实数据研究流程。本阶段支持 ETF 和
现金个股的价格净值诊断；分红总回报、期货和国际 v2 模拟下单仍待后续实现。
原始下载数据继续保存在本地忽略目录 `runs/`，没有搬迁或公开。
