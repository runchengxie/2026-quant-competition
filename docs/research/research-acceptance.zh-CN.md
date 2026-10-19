# 研究输入与实验验收

[English](research-acceptance.md)

这些可选工具检查文件身份、输入质量和实验结构，保留现有策略、默认引擎和报告。回测进程成功退出，并不足以证明研究结果可用。工具不连接券商，也不生成可执行目标。

## 目前能做什么

1. 分别安装的研究包读取显式输入清单，生成 `competition.research_input_receipt.v1` 凭证。
2. 根项目校验凭证，并在指定数据根目录内重新计算源文件的精确字节哈希。
3. 实验验收检查提供的配置、摘要和观测记录，返回 `accepted_diagnostic` 或 `blocked`。

目前尚未接入数据所有者的来源凭证和留出集协议验证。因此，所有 `research_evidence` 请求都会因 `OWNER_CONTRACT_VALIDATION_UNAVAILABLE` 被阻止。填入 `verified` 或给出正收益，都不能让当前版本返回 `accepted_research`。合成输入、未知来源和已经查看过的历史均会保留标记。

## 输入清单

清单和凭证应放在 Git 之外。`dataset_root` 必须是已存在的绝对目录，文件引用必须是用 `/` 分隔的规范相对路径。绝对引用、`..`、重复引用、符号链接越界、哈希及大小变化都会被拒绝。工具在读取前后计算哈希，不改写源文件。这只能检测变化，不是原子文件系统快照，消费时仍需复查。

完整清单示例见 [English](research-acceptance.md#input-manifest)。替换示例中的根目录、哈希和大小后再使用。`unknown` 表示未知，工具不会据此猜测来源。

| 字段 | 可用值 |
| --- | --- |
| `market` | `HK`、`US`、`CRYPTO` |
| `source_state` | `synthetic`、`archived_unverified`、`owner_published` |
| `price_basis` | `raw`、`adjusted`、`unknown` |
| `universe_state` | `synthetic`、`fixed_current`、`point_in_time`、`unknown` |
| `availability_state` | `verified`、`period_only`、`unknown` |
| `timezone` | IANA 时区名或 `unknown` |
| `kind` | `daily_bars`、`orderbook`、`trades`、`fundings` |

`synthetic` 必须与两个合成元信息字段一致。自行声明 `owner_published` 或 `verified` 不构成独立认证。`code_revision` 为 40 位小写十六进制或 `unknown`。当前生成器要求对应包名及版本 `0.1.0`。根项目的 [JSON schema](../../schemas/research/input-receipt.v1.schema.json) 描述凭证结构，Python 消费端还检查指纹、路径和元信息一致性。

股票入口支持 HK/US 日线 CSV，列为 `date,open,high,low,close,volume,code`。日期必须采用 `YYYY-MM-DD`，代码前缀必须符合市场。OHLCV 布尔值、非有限数、非正价格、OHLC 边界错误、负数或缺失成交量，以及文件内外重复的日期和代码组合都会被拒绝。验收不补价，也不认证复权、公司行动、交易日历、股票池完整性或历史可得性。

加密入口使用 `competition-crypto-mm` 和 `market=CRYPTO`，要求三个数据组齐全、每日覆盖一致、Parquet `datetime` 使用纳秒精度，并通过现有盘口、成交和资金费率审计。带时区列必须与声明一致。无时区时间可保留 `unknown`，在清单填写时区并不能证明原始时间的含义。文件名采用 `YYYY-MM-DD.parquet`，空文件或非零质量计数会被拒绝。这些检查不认证交易场所、产品身份或成交模型的真实性，也不会伪造 L3 订单标识。

凭证移除 `dataset_root`，新增逐文件 `rows`、`quality.issue_codes` 和 `fingerprint`，保留文件列表顺序。指纹是移除 `fingerprint` 后的 UTF-8 规范 JSON 的 SHA-256，键排序、使用紧凑分隔符、保留 Unicode，并禁止非有限数。源文件哈希始终计算原始字节，LF/CRLF 差异也会影响哈希。

## 命令与退出码

使用 Python 3.12，在各自独立的环境中按 lockfile 安装。`UV_PROJECT_ENVIRONMENT` 应位于源码之外。新命令使用显式清单，不依赖全局数据配置，`--help` 无需数据、私有配置或券商模块。其他旧命令保留各自的配置要求。

在对应研究包目录运行生成器，再到根目录运行消费端和实验验收：

```sh
uv run --locked python -m equity_lab.validation --manifest <manifest.json> --output <receipt.json>
uv run --locked python -m crypto_mm.commands.validate_inputs --manifest <manifest.json> --output <receipt.json>
uv run --locked python -m competition_tools.research_acceptance --receipt <receipt.json> --dataset-root <absolute-data-root>
uv run --locked python -m competition_tools.experiment_acceptance --plan <plan.json> --input-receipt <receipt.json> --summary <summary.json> --observations <positions.csv-or-events.json> --dataset-root <absolute-data-root> --output <acceptance.json>
```

尖括号内为待替换参数。生成器检查成功并写出凭证后退出 0。根输入消费端在结构、文件和质量检查通过时返回 `diagnostic_only` 并退出 0，此时仍可能带有来源警告。实验验收只有在所请求用途获接纳时才退出 0，`blocked` 或无效证据退出 2。报错采用稳定代码，不输出原始私有路径，参数解析错误也只返回 `INVALID_ARGUMENTS`。输出文件只能新建，不覆盖旧证据。

## 实验计划与观测记录

`competition.experiment_plan.v1` 必须恰好包含以下字段：

| 字段 | 约定 |
| --- | --- |
| `purpose`、`evaluation_kind` | `software_diagnostic` 或 `research_evidence`；`retrospective` 或 `owner_unexposed` |
| `strategy_id`、`config` | 稳定策略标识及所提供的配置对象 |
| `config_fingerprint`、`input_fingerprint`、`output_fingerprint` | 规范配置哈希、输入凭证指纹、`{"summary": summary, "observations": observations}` 的规范哈希 |
| `sample_interval` | 含首尾的 `start`、`end` ISO 日期或时间 |
| `windows` | `training`、`validation`、`evaluation`，各为含首尾的起止对象或 null，评估窗口必填 |
| `minimum_universe`、`minimum_observations` | 正整数，分别为评估标的数和不同评估时间戳数 |
| `costs` | `fee_bps`、`slippage_bps`、`currency`、`verified`，费用有限、滑点非负、布尔值显式填写 |
| `history_exposed`、`owner_protocol_receipt` | 是否查看过历史的布尔声明，以及可选的所有者协议引用对象，不代表审批 |

时间戳保留最多九位小数，按纳秒精确比较，同一时刻的不同偏移表示保留相同身份，更细精度会被拒绝。日期采用 `YYYY-MM-DD`，时间可追加 `T` 或空格、`HH:MM:SS`、可选小数及 `Z` 或 `±HH:MM`，时区感知状态应一致。窗口必须位于样本区间内，互相重叠会阻止验收。已经看过的历史不能再声称为未接触评估集。软件诊断可以保留样本内和来源警告，但不构成样本外证据。

验收可读取现有股票 `summary.json` 和 `positions_daily.csv`，识别 `strategy`、`run_status`、`fallback_reasons`、`target_weight` 和 `cnn_walk_forward_fold`。CSV 中的 `target_weight`、`inventory` 和非空 fold 在计算输出指纹前转为数值；JSON 观测记录应直接使用数值。可调用工具的 `canonical_digest` 保持表示一致。原报告字节和指标不会被改写。无持仓、缺少必要 fold、回退、重复观测和评估覆盖不足都会被阻止。已知的非 walk-forward 图像模型保留 `IN_SAMPLE_MODEL`。计入的 fold 必须提供完整训练、验证和测试区间，顺序无重叠、位于声明窗口内，且各观测中的协议一致。若声明了正的 `cnn_purge_days` 或 `cnn_embargo_days`，仍会因 `FOLD_PURGE_UNVERIFIED` 被阻止，部分评估记录无法核验按交易观测计算的间隔及标签边界，不能用日历天数代替。旧股票配置元信息只有路径标签，不含实际运行配置字节，工具保留 `CONFIG_BINDING_UNVERIFIED`，不会跟随私有路径推断配置。

加密会比较结构化 `summary.config` 与 `plan.config`，并核对 maker fee 和 `costs.fee_bps`，明确矛盾会阻止验收，缺少结构化运行配置也会阻止加密验收。加密需要 JSON 事件记录，包含 `datetime` 和有限 `inventory`，摘要指标包含有限的 `total_pnl`、`fee_cashflow`、`max_absolute_inventory` 及整数 `fill_count`。`pnl_unit` 必须明确为 `HKD`、`USD`、`USDT`、`USDC` 或 `quote_currency`。百分比收益要求正的 `funded_capital`。成本币种未知或费用未核验时，不能成为研究证据。工具检查所提供材料的一致性，不独立重算回测、费用账本或所有者管理的 fold。

保留输出采用 `competition.experiment_acceptance.v1`，仅包含状态、用途、排序后的稳定问题代码、三个指纹及样本计数。`public_acceptance_summary` 拒绝未知字段，仅允许这一汇总契约，用于后续单独审查的发布步骤。这些命令不会向 Pages 发布凭证、原始数据、文件名或服务商响应。

## 验证与后续工作

跨环境检查实际运行研究包生成器，再调用根项目消费端：

```sh
uv run --locked python -m competition_tools.check_research_receipts --project equity-lab --leaf-python <equity-environment-python> --output-root <new-external-directory>
uv run --locked python -m competition_tools.check_research_receipts --project crypto-mm --leaf-python <crypto-environment-python> --output-root <another-new-external-directory>
```

CI 在独立的锁定环境中分别执行两项，不安装私有研究所有者的代码。测试覆盖字节变化、路径越界、元信息、输入边界、回退、空结果、窗口重叠、指纹、CLI 报错及汇总隐私。现有 Pages 测试比较中英文的机器事实。

对保留的 2026-10-19 报告应用新验收后，16 个研究包股票实验均未通过研究证据验收。港股仍只有一只股票，美股仍只有 SPY，零持仓 CNN 和无 fold 结果还带有额外阻止原因。4 个加密汇总报告也未通过，原因包括缺少保留的逐事件记录和明确的 PnL 单位。根项目另外 4 个按月或价格代理报告缺少适配器要求的持仓及来源凭证，本次未验收。此次只验收保留材料，没有重新运行历史回测。[原有 24 条结果快照](strategy-validation-2026-10-19.zh-CN.md)保持不变。

后续核算适配器应通过版本化 artifact 或独立环境复用固定版本的所有者 API。本次没有安装 `quant-platform` 核算及契约。只读本机核验发现，该平台默认 IBKR factory 导入的 `quant_execution_engine.broker.ibkr` 不可用，这不代表本仓库自己的 IBKR adapter 缺失。`quant-backtest-runtime` 当前要求 Linux，未在 Windows 启用。存在 pandas 或模块命名冲突的模型、研究和报告所有者仍采用独立进程。数据来源、因果 FX、公司行动、完整研究股票池、所有者留出集治理及受监督的 Paper 生命周期均待后续完成，参见[架构](../../ARCHITECTURE.zh-CN.md)。
