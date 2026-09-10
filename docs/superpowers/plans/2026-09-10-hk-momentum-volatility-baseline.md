# HK Momentum Volatility Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 IBKR 权限、已落盘港股日线数据和 2026 港股比赛规则约束下，建立可审计的低频港股动量 + 波动率控制基线，并与 2800 和纯动量策略比较。

**Architecture:** 研究代码留在本项目的 `strategies/international_lite` 现有边界内，新增一个面向 CSV 日线输入的港股组合回测模块；执行侧继续保持 Paper-first 和 `dry_run=true`，不把研究回测直接连接到下单。回测输出使用固定数据快照、明确的信号滞后、交易成本和比赛指标，避免把延迟行情误当成实时数据。

**Tech Stack:** Python 3.12, standard library, pytest, existing `strategies.international_lite` modules, CSV files under `D:\data\hk-competition-2026\raw\ibkr\daily` and `D:\data\global-six-market\raw\ibkr\daily\HK_2800.csv`.

**Spec:** `docs/operations/market-data-inventory.md`, `docs/competition/rules.md`, `config/competition-2026-hk.json`

## Global Constraints

- 只使用目前已落盘并通过基础质量检查的港股日线数据；不引入尚未确认的韩国、实时、L1/L2 或基本面 PIT 数据。
- 组合只做多港股股票；不使用杠杆、融券、期货、期权或盘口信号。
- 调仓频率为月度；信号只能使用调仓日前已知的收盘价，持仓收益从下一交易日开始计算。
- 默认 10 只持仓、单票上限 12%、现金 2%；所有参数必须可配置。
- 回测必须输出毛收益、成本后收益、换手率、持仓率、空仓天数和比赛指标；结果不能自动宣称满足比赛资格。
- 不改变 IBKR 连接、账户、订单或实时行情权限；执行配置保持 `paper` 和 `dry_run=true`。

---

### Task 1: 定义港股日线输入和组合回测接口

**Files:**
- Create: `strategies/hk_low_frequency/__init__.py`
- Create: `strategies/hk_low_frequency/backtest.py`
- Test: `tests/strategies/test_hk_low_frequency_backtest.py`

**Interfaces:**
- `load_daily_csv(path: str | Path) -> list[DailyBar]`
- `run_monthly_backtest(history: Mapping[str, Sequence[DailyBar]], benchmark: Sequence[DailyBar], config: HKBacktestConfig) -> HKBacktestResult`
- `HKBacktestResult` exposes dated portfolio returns, benchmark returns, turnover, selected symbols, and `CompetitionMetrics`.

- [ ] **Step 1: Write failing tests** for CSV parsing, date ordering, missing close rejection, no look-ahead, and empty-universe rejection.
- [ ] **Step 2: Run** `uv run pytest tests/strategies/test_hk_low_frequency_backtest.py -q`; expected initial failure because the module does not exist.
- [ ] **Step 3: Implement** typed dataclasses and a deterministic monthly backtest using next-session execution and close-to-close returns.
- [ ] **Step 4: Run** the focused tests and then `uv run pytest tests/strategies -q`.

### Task 2: Implement momentum + volatility ranking and controls

**Files:**
- Modify: `strategies/hk_low_frequency/backtest.py`
- Test: `tests/strategies/test_hk_low_frequency_backtest.py`

**Interfaces:**
- `rank_hk_universe(history, as_of, lookbacks=(63,126,252), volatility_window=60) -> list[RankedSymbol]`
- `select_targets(ranked, top_k=10, max_weight=0.12, cash_weight=0.02) -> dict[str, float]`
- Score is `0.5 * z(momentum_126) + 0.3 * z(momentum_252) - 0.2 * z(volatility_60)` with deterministic tie-breaking by symbol.

- [ ] **Step 1: Add failing tests** for score direction, insufficient-history exclusion, deterministic ties, weight cap, and cash residual.
- [ ] **Step 2: Run** the focused tests and confirm failures.
- [ ] **Step 3: Implement** the ranking, eligibility filter, capped weights, and baseline/ablation configuration (`pure_momentum`, `momentum_volatility`).
- [ ] **Step 4: Run** all strategy tests.

### Task 3: Run reproducible comparison on the actual HK snapshot

**Files:**
- Create: `scripts/run_hk_baseline_backtest.py`
- Create: `docs/operations/hk-strategy-baseline-2026-09-10.md`

**Interfaces:**
- CLI accepts `--data-root`, `--benchmark`, `--output`, and `--cost-bps`.
- Output report records source paths, row counts, date ranges, parameter values, data-quality exclusions, and comparison metrics for 2800 buy-and-hold, pure momentum, and momentum + volatility.

- [ ] **Step 1: Add a smoke test** that invokes the runner against a temporary two-symbol CSV fixture and checks the report schema.
- [ ] **Step 2: Implement** the runner using the real data paths and JSON/Markdown evidence output; do not write into `D:\data`.
- [ ] **Step 3: Run** the smoke test and the real snapshot run.
- [ ] **Step 4: Record** performance, turnover, drawdown, data limitations, and whether each rule can be assessed from available evidence.

### Task 4: Paper-shadow readiness and handoff

**Files:**
- Modify: `docs/operations/competition-mvp-status.md`
- Create: `docs/operations/hk-strategy-paper-shadow-checklist.md`
- Test: `tests/test_release_contract.py` if release assertions require an update

- [ ] **Step 1: Add a checklist** covering delayed-vs-real-time data, monthly signal timestamp, contract qualification, dry-run guard, order reconciliation, and Flex evidence.
- [ ] **Step 2: Update MVP status** with the backtest evidence and unresolved permissions; keep live trading explicitly blocked.
- [ ] **Step 3: Run** the full test suite and `git diff --check`.
- [ ] **Step 4: Review** that no credential, order, or realtime-monitoring mutation was introduced.
