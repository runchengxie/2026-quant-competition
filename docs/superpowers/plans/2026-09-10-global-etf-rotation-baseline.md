# Global ETF Rotation Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用现有六个跨市场 ETF 日线数据建立可审计的全球多资产轮动基线，并与买入持有和纯动量进行比较。

**Architecture:** 新增独立的 `strategies/global_etf_rotation` 模块，不修改港股比赛策略。策略按共同交易日期形成月度信号，以过去 3/6/12 个月动量和 60 日波动率排序，持有 Top-K，若绝对动量或风险条件不达标则持有现金；报告明确跨币种、不同交易日和数据覆盖限制。

**Tech Stack:** Python 3.12, standard library, pytest, existing competition metrics, CSV files under `D:\data\global-six-market\raw\ibkr`.

**Spec:** `docs/operations/market-data-inventory.md`, `docs/competition/rules.md`, `config/competition-2026-hk.json`

## Global Constraints

- 仅使用 SPY、HK_2800、UK_ISF、AU_STW、CA_XIU、SG_ES3 这六个已落盘 ETF 的日线 close/volume。
- 不做实时行情、订单簿、杠杆、融券或实际下单；该策略是独立研究策略，不替换当前港股比赛配置。
- 月度调仓，信号只使用调仓日前数据；不同市场交易日采用共同日期，缺失数据不前向填充超过下一共同日期。
- 默认最多持有 3 个 ETF，单票上限 45%，现金至少 10%；所有参数可配置。
- 输出必须记录原始路径、资产数量、共同日期、币种/FX 限制、成本假设和比较指标。

---

### Task 1: 添加全球 ETF 输入和策略接口

**Files:**
- Create: `strategies/global_etf_rotation/__init__.py`
- Create: `strategies/global_etf_rotation/backtest.py`
- Test: `tests/strategies/test_global_etf_rotation.py`

**Interfaces:**
- `load_daily_csv(path: str | Path) -> list[DailyBar]`
- `run_monthly_rotation(history: Mapping[str, Sequence[DailyBar]], config: GlobalETFConfig) -> GlobalETFResult`
- `GlobalETFResult` exposes dates, portfolio returns, benchmark returns, turnover, holdings and metrics.

- [ ] **Step 1:** Write failing tests for CSV parsing, common-date alignment, no look-ahead, and empty history rejection.
- [ ] **Step 2:** Run the focused test and confirm the expected import failure.
- [ ] **Step 3:** Implement deterministic date alignment and monthly close-to-close return accounting.
- [ ] **Step 4:** Run the focused tests.

### Task 2: Implement momentum, volatility and cash defense

**Files:**
- Modify: `strategies/global_etf_rotation/backtest.py`
- Test: `tests/strategies/test_global_etf_rotation.py`

**Interfaces:**
- `rank_assets(history, as_of, lookbacks=(63,126,252), volatility_window=60) -> list[RankedAsset]`
- `select_assets(ranked, top_k=3, max_weight=0.45, cash_weight=0.10) -> dict[str, float]`
- Score uses weighted momentum minus volatility, with absolute momentum filter and deterministic tie-breaking.

- [ ] **Step 1:** Add failing tests for ranking, cash defense, weight caps and deterministic ties.
- [ ] **Step 2:** Implement signal and target construction.
- [ ] **Step 3:** Run all strategy tests.

### Task 3: Run the six-ETF comparison and publish evidence

**Files:**
- Create: `scripts/run_global_etf_rotation.py`
- Create: `docs/operations/global-etf-rotation-baseline-2026-09-10.md`
- Create: `artifacts/global-etf-rotation-2026-09-10.json`

- [ ] **Step 1:** Add CLI and report schema for equal-weight buy-and-hold, pure momentum and defended rotation.
- [ ] **Step 2:** Run against actual six-ETF snapshot without writing to `D:\data`.
- [ ] **Step 3:** Record results, coverage, FX caveat, tradeability caveat, and competition boundary.

### Task 4: Verify and hand off

- [ ] **Step 1:** Run full pytest suite and `git diff --check`.
- [ ] **Step 2:** Confirm no IBKR order, account, credential or live configuration mutation.
- [ ] **Step 3:** Commit the isolated branch and present merge/PR options.
