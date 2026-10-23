# Strategy controls

[简体中文](strategy-controls.zh-CN.md)

The controls programme uses a separate versioned contract. No new real-data
control result or prospective observation is published yet. Existing daily-study
and ablation snapshots retain their original policies and identities.

US controls compare daily and monthly equal weighting and positive 20-session
momentum, with an additional fixed monthly weight buffer of 0.20. The buffer
compares drifted holdings and residual cash. It does not create an extra daily
exit rule. Crypto controls distinguish legacy policies, strict volatility
controls and an equal-weight allocation using the same decision-time gross
exposure as the strict trend policy. Equal exposure does not establish equal
realized risk.

`competition.strategy_controls_spec.v1` freezes both market inputs, exact arm
identities, fees and budgets. The initial grid has 132 US and 288 crypto jobs.
Maximum budgets are 512 jobs, 384 per batch and 3600 cumulative seconds.
Protocols bind source and input bytes; already inspected history remains
retrospective. These contracts do not authorize orders or accept research for
production.

`python -m competition_tools.team controls --help` describes the independent
entry point without loading personal configuration. Scientific leaf runners and
verified publication must be installed before an experiment can complete.
Keep configurations, manifests, retained source and outputs outside the checkout.
