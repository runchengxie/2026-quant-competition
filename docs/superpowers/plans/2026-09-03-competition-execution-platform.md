# 比赛执行平台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在比赛项目中落地标准目标交接、NautilusTrader/IBKR 执行、事件日志、恢复和比赛审计。

**Architecture:** 保留 Nira 与 `research-workspace` 为独立研究源，比赛仓库作为局部执行 monorepo。Windows runner 连接 IBKR Gateway，Linux 只产生目标文件；事件日志和对账负责订单事实与恢复。

**Tech Stack:** Python 3.12, NautilusTrader, IBKR TWS API, Pydantic 或 dataclass schema, JSON/JSONL, pytest, uv。

**Spec:** `docs/superpowers/specs/2026-09-03-competition-execution-platform-design.md`

## Global Constraints

- 研究代码不得复制进比赛项目，研究和执行通过 `targets.json`、`lineage.json` 和稳定 schema 连接。
- Windows runner 默认只连接 IBKR Paper Gateway `127.0.0.1:4002`。
- 实盘必须使用独立配置、显式保护开关和人工监督。
- 未确认的订单状态不得推断为拒绝或成交，必须通过事件或对账确认。
- 凭证、账户信息、订单日志和运行产物不得提交到 Git。
- 每个任务使用独立 worktree 和功能分支，完成后通过 PR 合并。

### Task 1: Freeze contracts and market model

**Files:**
- Create: `packages/contracts/*`
- Create: `packages/market_model/*`
- Create: `schemas/targets.schema.json`
- Test: `tests/contracts/*`, `tests/market_model/*`

- [ ] Write failing tests for target validation, Japanese symbols, currency, exchange and lot-size rules.
- [ ] Implement the smallest typed contract and market normalization layer.
- [ ] Run `pytest tests/contracts tests/market_model -q`.
- [ ] Commit `feat: add competition execution contracts`.

### Task 2: Add Nira target handoff

**Files:**
- Create: `strategies/nira/*`
- Modify: `docs/strategy/*`
- Test: `tests/strategies/test_nira_handoff.py`

- [ ] Write failing tests for loading an external target file without importing Nira source paths.
- [ ] Implement target import, lineage preservation and output validation.
- [ ] Run `pytest tests/strategies/test_nira_handoff.py -q`.
- [ ] Commit `feat: add nira target handoff`.

### Task 3: Introduce NautilusTrader execution boundary

**Files:**
- Create: `adapters/nautilus/*`
- Create: `apps/execution_runner/*`
- Modify: `pyproject.toml`, `.env.example`
- Test: `tests/execution/test_runner_contract.py`

- [ ] Write failing tests for Paper-only defaults, explicit environment resolution and dry-run behavior.
- [ ] Implement the runner boundary without placing external orders in unit tests.
- [ ] Run `pytest tests/execution/test_runner_contract.py -q`.
- [ ] Commit `feat: add nautilus execution boundary`.

### Task 4: Implement IBKR event adapter

**Files:**
- Create: `adapters/ibkr/*`
- Modify: `apps/execution_runner/*`
- Test: `tests/adapters/test_ibkr_events.py`

- [ ] Write failing tests for contract mapping and normalization of order, fill, error and disconnect events.
- [ ] Implement Paper Gateway connection and event translation behind the contracts interface.
- [ ] Run unit tests and a supervised Paper contract smoke test.
- [ ] Commit `feat: add ibkr event adapter`.

### Task 5: Add event journal and reconciliation

**Files:**
- Create: `packages/audit/*`
- Create: `packages/reconciliation/*`
- Test: `tests/audit/*`, `tests/reconciliation/*`

- [ ] Write failing tests for idempotent event append, projection rebuild, unknown submit outcome and reconnect reconciliation.
- [ ] Implement append-only JSONL journal, projection rebuild and reconciliation reports.
- [ ] Run `pytest tests/audit tests/reconciliation -q`.
- [ ] Commit `feat: add event journal and reconciliation`.

### Task 6: Add execution policies

**Files:**
- Create: `packages/execution_policies/*`
- Test: `tests/execution_policies/*`

- [ ] Write failing tests for single-order policy and deterministic child-order plans.
- [ ] Implement limit/market baseline and a dry-run TWAP policy without binding to a broker SDK.
- [ ] Run `pytest tests/execution_policies -q`.
- [ ] Commit `feat: add execution policy boundary`.

### Task 7: Competition evidence and release checks

**Files:**
- Modify: `docs/operations/*`, `README.md`
- Create: `tests/test_release_contract.py`

- [ ] Write failing tests that reject secrets, live configuration in Paper runs and missing evidence fields.
- [ ] Implement evidence export and release preflight documentation.
- [ ] Run the full local quality gate and supervised Paper smoke.
- [ ] Commit `docs: document competition execution release checks`.
