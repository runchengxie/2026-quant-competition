# Optional accounting consumer

Read root AGENTS.md first. This standalone package owns its accounting implementation under platform_compare.accounting. Adapters are MIT; derived accounting code retains Apache-2.0 and its ORIGIN.json inventory. Do not add quant-platform/research-contracts dependencies or external namespace imports. No sibling checkout sys.path imports, broker calls, provider credentials or real data in source. Root execution must not import this package. English is canonical; maintain README.zh-CN.md.

Run uv sync --locked --group dev, uv run --locked ruff check . and uv run --locked pytest -q from here. UV_PROJECT_ENVIRONMENT, cache, temp and all results belong outside source under the owning competition DATA_ROOT. Do not promote diagnostic bundles into research or execution eligibility. No owner/source/config attestation can be inferred from a caller boolean. Preserve default legacy engines and report bytes.
