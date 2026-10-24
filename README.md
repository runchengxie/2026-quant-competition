# 2026 Quant Competition

[简体中文](README.zh-CN.md) · [Project website](https://runchengxie.github.io/2026-quant-competition/) · [Documentation](docs/README.md)

This project helps a team prepare for the 2026 Hong Kong quantitative trading competition. It brings together tools to prepare price data, try trading ideas and keep track of the results.

New here? Start with an offline example. It uses made-up data, runs on your computer and does not submit orders. You do not need a broker account, API keys or any other `quant-*` repository.

## What can I do with it?

| I want to… | Start here |
| --- | --- |
| Run a first example | [Offline quickstart](docs/operations/team-quickstart.md) |
| Try a strategy on past prices | [Research examples](research/README.md) |
| Prepare a dataset | [Data preparation](docs/research/datasets.md) |
| Understand the existing results | [Research results and limitations](docs/research/strategy-validation-2026-10-19.md) |
| Inspect the latest sensitivity checks | [Robustness results](docs/research/strategy-robustness.md) and [fresh-data steps](docs/research/data-refresh.md) |
| Compare simple reversal, learned signals and weekly crypto trading | [Incremental research](docs/research/incremental-research.md) |
| Check daily selection costs and delayed execution | [Fixed strategy comparison](docs/research/strategy-comparison.md) |
| Check how cash, shares and fees affect a result | [Accounting comparison](docs/research/accounting-comparison.md) |

Trying a strategy on past prices is called a backtest. It helps you inspect the strategy's behavior, but it cannot promise future returns.

The website separates [strategy performance](https://runchengxie.github.io/2026-quant-competition/strategies/), [factor research](https://runchengxie.github.io/2026-quant-competition/factors/) and the [project guide with offline demos](https://runchengxie.github.io/2026-quant-competition/docs/project/). The equity prediction study publishes ranking results. The four separate daily rule signals still need independent IC, grouped-return and signal-decay tests. See [workflow modules](docs/architecture.md#workflow-modules-in-one-repository) for code ownership inside this independently deliverable repository.

## Run your first example

1. Install Python 3.12 and `uv`, which installs the project's Python packages. Download or clone this repository.
2. Follow the [offline quickstart](docs/operations/team-quickstart.md) to install the packages and choose a folder outside the code checkout for data and results.
3. Run the equity demo first. It creates sample data and a backtest report. The same guide also includes a crypto demo.

No account credentials or market-data subscription is needed for these demos. To browse before installing anything, open the [project website](https://runchengxie.github.io/2026-quant-competition/).

## How far along is the project?

The offline demos and research tools are available. The team has not finalized or registered its competition strategy. Existing reports describe historical experiments and software checks.

Broker execution needs separate setup and supervised testing. Paper trading means practicing with a simulated account. Before using broker commands, read the [Paper setup and release checks](docs/operations/release-checks.md); offline examples do not establish that a broker connection is ready.

## Where do I go next?

Use the [documentation index](docs/README.md) to find competition guidance, research details, project structure and account setup. Keep datasets, generated reports and credentials outside the code checkout.

## Development checks

Installation for development, test commands and website builds are in the [development guide](docs/development.md). Package boundaries and execution limits are in the [project overview](docs/project-overview.md).

[Retrospective daily study](docs/research/real-data-study.md)

[Project documentation](https://runchengxie.github.io/2026-quant-competition/docs/)
