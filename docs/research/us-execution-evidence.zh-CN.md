# 美股成交证据

[English](us-execution-evidence.md)

新的美股下一交易日适配器是离线价格净值模拟。合成契约测试已通过现有美元现金账本。现有日线缓存仍需补齐成交证据才能用于这项回放。它不会下单，也不据此宣称支持总回报核算或通过执行验收。

该适配器与五市场 `next-open` 实验分开，模型标识为 `us-next-session-price-nav.v1`。它要求美元标的、原始信号和成交价格、明确的 `XNYS` 日历版本，以及带时区的信号、信息可用和决策时间。成交使用严格晚于信息可用时间的第一个常规交易时段开盘，决策必须早于该开盘。决策过晚或缺少该开盘价格就阻塞，不顺延交易。信号字段记录数据截止时间，账本的信号时钟使用其后的信息可用时间，再到声明的决策时间。日线收盘估值的信息可用时间仍是按日期滞后建模的假设。

公司行动证据须覆盖全部输入日期和标的。已知存在事件时，当前仅支持价格净值的模型会阻塞，缺少证据也会阻塞。真实区间无事件的证据须经过检查，并把摘要登记到源码中的 `TRUSTED_ACTION_REVIEWS`。该登记表初始为空。修改 JSON 标志不能证明真实区间没有事件。合成公司行动证据只接受合成输入身份，并持续标为合成。

初始现金为 100000 美元。碎股模式明确属于模拟。整手模式要求正整数交易单位。`--fee-bps` 表示有限、非负且小于 10000 的佣金情景，额外滑点和换汇成本均为零，默认 20 bps。该费用不代表某一家券商的真实收费标准。

账本的 `configuration_sha256` 同时绑定输入配置字节及有效费用和模型参数，因此不同费用情景会得到不同摘要。

在独立的 `research/platform-compare` 环境中运行，

`/absolute/...` 是占位路径，Windows 须使用根据项目配置解析的带盘符绝对路径。

```sh
python -m platform_compare.us_next_session.run --config /absolute/us-inputs.json --output-root /absolute/new-output --fee-bps 20 --json
```

配置 schema 为 `competition.us_next_session_inputs.v1`，用 SHA-256 绑定 CSV 和公司行动证据文件。CSV 列为 `date`、`open`、`close`。输入与输出都放在源码目录外。命令在计算后重新核验全部绑定文件，写出诊断账本和 `run.json`。

根命令通过子进程调度，不导入账本研究包，

```sh
python -m competition_tools.team run us-next-session --config /absolute/team.toml --experiment-config /absolute/us-inputs.json --output-root /absolute/new-output
python -m competition_tools.team execution-readiness --config /absolute/team.toml --spec /absolute/readiness-spec.json --output-root /absolute/new-readiness
```

盘点配置的 `schema` 为 `competition.us_execution_readiness_spec.v1`，`manifests` 为包含 `path` 和 `sha256` 的记录列表。该命令盘点日线 manifest 声明及缺失的成交证据，不验证完整价格数据集，不授予交易权限，也不计算绩效。仅声明使用原始价格，无法证明常规时段首笔开盘、信息可用时间、上市范围、交易单位或公司行动覆盖。原研究引擎和已发布结果保持原状。
