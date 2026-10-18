# Offline research boundary

Read the root AGENTS.md first. This subtree is independently packaged and MIT licensed. English README is canonical; keep README.zh-CN.md synchronized. Tests and diagnostics use English. No runtime locale framework is provided.

Do not add broker connections, private datasets, account configuration or personal metadata. Keep scientific behavior and meaningful tests. Report inherited defects explicitly. Inputs/outputs and UV_PROJECT_ENVIRONMENT belong outside the checkout under configured DATA_ROOT. Never infer an execution handoff from research report files.

From this directory run `uv sync --locked --group dev`, `uv run --locked ruff check .` and `uv run --locked pytest -q`. Use `MPLBACKEND=Agg` for headless checks. Root execution tests are separate; root Ruff still checks this code. No dedicated type, coverage or security/dependency-audit threshold is configured here. Do not claim unexecuted checks pass.
