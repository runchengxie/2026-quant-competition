# Check the offline workflow

[简体中文](workflow-check.zh-CN.md)

This check runs the stock and crypto pipelines on fictional inputs and reconciles their outputs. A successful run confirms that the installed modules work together under these examples. Historical strategy performance and broker readiness require their own evidence.

## Run and verify

Install the independent offline profile using the [team quickstart](team-quickstart.md). Run from a matching, committed source checkout, using an environment that has the root package installed. Inputs, output and environments remain outside the source tree. The output directory must not exist.

```sh
python -m competition_tools.check_workflow_boundaries --source-root .
python -m competition_tools.check_workflow_delivery --config /absolute/team.toml --output-root /absolute/new-workflow-run --source-root .
python -m competition_tools.evaluation.run_record --run-root /absolute/new-workflow-run
```

Replace `/absolute/...` with paths you own. Windows requires drive-qualified paths. This mode needs the source checkout so the evidence can bind the code actually installed in each leaf environment. Existing `team demo` commands retain their previous behavior.

The runner starts the configured stock and crypto interpreters once each. It makes no provider request and submits no order. Each child has a 180-second timeout. The 600-second shared processing budget is checked between stages and before finalization. File hashing and persistence use synchronous filesystem calls, so this is not a hard timeout for blocked filesystem I/O. A failed attempt stays failed or incomplete and is not retried automatically.

## What each pipeline checks

The equity job uses 24 fictional daily labels, two made-up stock codes and a missing row. It prepares the panel, forms a short/long moving-average signal, constructs weights, and runs the existing fractional-weight engine with a 20-bps modeled cost and a separate zero-cost replay. These dates are an illustrative grid, not an exchange calendar.

The crypto job uses 270 fictional daily prices, including 252 warmup observations, with two made-up products. The strict trend/volatility policy forms targets. An initial decision and later Monday decisions control the existing self-financing ledger, with 35-bps modeled cost and a zero-cost counterfactual. Other days retain quantities and cash. Its unit remains USDT. The maker simulator uses a separate event model.

Both leaf producers write `competition.workflow_leaf_result.v1`, inspectable tables or ledgers, actual Python/distribution versions and installed package source digests. The [schema](../../schemas/research/workflow-leaf-result.v1.schema.json) names this new contract. Root validation compares the job, retained source, artifact hashes and embedded evidence before accepting the result. Production root modules never import leaf Python.

## Explain price gains and modeled costs

`explanations/equity-lab.json` and `explanations/crypto-mm.json` use `competition.performance_explanation.v1`. They preserve their accounting model and currency. Every period and the total must reconcile within `1e-10 × max(1, relevant NAV)` for monetary values. Invalid numbers, missing rows, incompatible models/currencies and unreconciled amounts reject the explanation. The report retains the largest absolute monetary reconciliation error.

| Field | Meaning |
| --- | --- |
| `instruments[].price_pnl` | Signed price contribution in the account's currency |
| `instruments[].return_contribution` | That contribution divided by initial equity |
| `modeled_costs` | Costs deducted along the net account path |
| `net_pnl` | Final equity minus initial equity, reconciled to price contributions minus modeled costs |
| `counterfactual_cost_drag_return` | Zero-cost replay return minus net replay return |

The counterfactual gap includes the effect of costs on later capital. It need not equal summed deducted costs divided by initial equity. These explanations attribute arithmetic model results, without establishing causal factor effects, Brinson attribution, realistic fills or venue fees. The pure `explain_fractional` and `explain_self_financing` APIs in `competition_tools.evaluation.contributions` can inspect compatible supplied artifacts. Their caller must bind the policy and counterfactual identity, as this runner does with its job and source records.

## Follow the experiment record

`experiment-plan.json` freezes parameters, costs, input hashes, the source commit, an exact-byte source archive and lockfile hashes before the child runs. `experiment-result.json` binds actual environment metadata and output hashes after validation. The records use relative bundle paths, so an intact bundle can be moved and checked without its original checkout.

`delivery.json` describes outputs already checked, with status `outputs_verified`. Overall completion comes from a verified `experiment-result.json` with status `completed`. The CLI returns nonzero for a failed delivery. If finalization cannot verify a changed plan or input, the run remains incomplete and the reported `record_issue` identifies that state. Do not overwrite the old directory to retry.

The reusable `init_run`, `freeze_run`, `finish_run` and `verify_run` APIs live in `competition_tools.evaluation.run_record`. They create new records exclusively and detect changes to inputs, retained code, locks or outputs. Hash integrity does not authenticate a vendor or author. Recorded lockfiles describe the intended environment; the separately recorded installed versions describe what ran. Existing historical experiments keep their own plans and receipts. Default demo markers are unchanged.

Keep complete bundles outside public source. This check's data are synthetic, and its records are engineering evidence. They do not become targets or accepted research and do not update published scientific snapshots.

## Keep module boundaries checked

CI runs the same static import checker. It resolves ordinary imports, relative imports and simple dynamic imports. A fixed signal-registry namespace is checked against the forbidden destinations, while ambiguous dynamic targets in pure layers fail. Root code cannot import independently installed research packages. Data and policy layers cannot import replay or broker mechanisms.

The checker inspects source rather than executing it. It is an architecture regression check, not a security sandbox or a proof about arbitrary runtime code. Its tests include allowed imports and similar names so valid boundaries remain usable. CI also runs the actual two-producer/root-consumer check using the installed offline profile.
