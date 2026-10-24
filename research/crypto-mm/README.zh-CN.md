# 加密做市离线研究

[English](README.md)

这个事件驱动模拟器根据可见盘口队列、公开成交和资金费率信号模拟做市。B0 使用库存偏移报价，B1 加入盘口不平衡，B2 根据波动调整价差，B3 加入资金费率相关的目标库存。解读结果前请阅读[模拟假设](docs/assumptions.zh-CN.md)。

## 快速开始

[每周调仓研究](../../docs/research/incremental-research.zh-CN.md)使用日线比较趋势策略与同日历、同决策敞口的等权对照。这部分独立于做市事件模拟器，真实历史运行需要一次性预约。

进入本目录，先配置外部 `DATA_ROOT` 和 `UV_PROJECT_ENVIRONMENT`，再执行英文 README 中的可复制命令。`uv sync --locked --group dev` 安装锁定依赖，`python -m crypto_mm.demo` 生成演示数据，随后可运行审计、B0 回测、信号分析、绘图和测试。

演示在 `raw_data/{orderbook,trades,fundings}/` 下生成九个 Parquet 文件，并在同级写入 `demo-manifest.json`。文件名是 `YYYY-MM-DD.parquet`。当前读取器固定要求 `2026-03-19` 至 `2026-03-21` 三个日期标签，它们不代表提供了真实历史行情。读取器将 datetime 的存储单位转换成纳秒事件。字段包括 `datetime`、20 档 `bid_price_N`/`ask_price_N`/`bid_qty_N`/`ask_qty_N`、成交 `price`/`size`/`is_maker_ask` 和 `funding_rate`，类型和生成示例见 `market_data.py` 与 `demo.py`。

回测和分析打印到 stdout。绘图默认运行四个策略，写入外部项目目录的 `figures/`。绘图支持 `--help`，并在绘图前拒绝未知参数。没有其他绘图 CLI 选项；自定义目录请使用 `generate_figures(output_directory=...)`。敏感性扫描用于探索，不保证得到最优参数。程序化配置及校验见 `config.py` 的 `StrategyConfig` 和 `SimulationConfig`。

## 日线工作流模块

日线价格校验位于 `crypto_mm.data.daily_prices`，历史趋势定义位于 `crypto_mm.signals.daily_trend`，目标权重和调仓日历位于 `crypto_mm.portfolio`。原有 `crypto_mm.daily` 模块的公开辅助函数仍可导入。日线现金账本保留原来的计算方式，消费这些目标；事件驱动的做市模拟器保留自己的模型。

可选的[离线工作流检查](../../docs/operations/workflow-check.zh-CN.md)用虚构日线输入串联已安装的规则与账本，再由根工具核对产物、价格贡献与成本，以及不可覆盖的实验记录。这些记录用于工程检查，已有研究协议和公开结果保持原样。

## 已知限制

独立的 `crypto_mm.daily` CLI 消费已校验的现货日线 manifest，支持 `equal_weight` 建仓后持有及滞后的 `momentum_63d` 诊断。它使用365天年化、明确的USDT报价及按成交金额计算的成本，不复用事件 receipt，也不模拟做市。见[数据准备](../../docs/research/datasets.zh-CN.md)和[新评估证据](../../docs/research/data-expansion-and-evaluation.zh-CN.md)。`python -m crypto_mm.daily --help` 不需要工作区配置。

信号期限按实际秒数计算。采样间隔必须能整除 1、5、30 秒期限，无法表示的网格会抛出 `ValueError`。为兼容旧字段，`one_second_log_return` 保留名称，但非一秒采样时表示相邻网格的对数收益。时间和窗口配置必须为整数。

审计质量字段增加 `nonfinite_values` 和盘口 `nonpositive_price_rows` 计数，空值仍单独统计。审计报告用于诊断无效输入，不证明交易所数据有效性。库存峰值统计包含同一时间戳内每次成交。链接的评估记录了有预算的三天归档回放，不代表完整历史研究或参数优化。重叠挂单的共享可见队列和交易所成交真实性仍存在模型限制。

## 配置与输出

使用 Python 3.12。导入模块前，将 `DATA_ROOT` 设置为共享数据目录的绝对路径，项目数据目录为 `DATA_ROOT/2026-quant-competition/research/crypto-mm/`。也可以将 `WORKSPACE_CONFIG` 指向包含绝对路径 `data_root` 的 TOML 文件。默认查找 `CONFIG_ROOT/shared/workspace.toml`，或 `XDG_CONFIG_HOME/quant-competition/shared/workspace.toml`，后者默认是 `~/.config/quant-competition/shared/workspace.toml`。显式 `DATA_ROOT` 优先。配置缺失或无效会报错，包括解析 `--help` 前已导入配置的命令。

虚拟环境、输入数据、报告、图表和模型输出放在源码目录之外。使用 uv 时，将 `UV_PROJECT_ENVIRONMENT` 指向外部环境目录。演示生成器拒绝覆盖已有数据。演示数字仅用于验证软件，不代表投资收益或比赛表现。

## 许可证与执行边界

本子目录代码采用 MIT，不改变仓库其他部分和依赖的许可状态。这里没有券商连接和下单功能。研究输出不是 `targets.json`，不能直接交给执行服务。已发布执行 v1 JSON schema 接受 JP/US，运行时市场规范化还识别 HK，两者存在已有不一致，加密市场不受支持。这些行为均不使研究报告成为可执行目标。接入需要另行审查转换适配和执行验证。比赛产品资格以官方规则及券商、账户权限为准。

## 输入与实验验收

可选的[研究验收工具](../../docs/research/research-acceptance.zh-CN.md)使用显式清单检查输入并生成凭证，新入口不需要全局数据配置。软件检查成功不代表合格研究证据，所有者来源及留出集协议尚未接入。默认策略和既有报告保持不变。

[日频历史对比研究](../../docs/research/real-data-study.zh-CN.md)

## 小时线因子诊断

独立离线 CLI 为 `python -m crypto_mm.factors --spec /absolute/private/factor-protocol.json --output-root /absolute/data/new-factor-run`，需要不可变的小时线 manifest 和匹配的冻结源码。根工具 `team factors` 调用已安装 CLI，不传递服务商凭据。定义与限制见[因子说明](../../docs/research/strategies.zh-CN.md#hourly-dex-factors)，配置见[数据准备](../../docs/research/datasets.zh-CN.md#dexpaprika-hourly-pilot)。合成交付验证已通过；2026-10-22 的真实检查返回 HTTP403，没有获得行情观测或因子结果。
