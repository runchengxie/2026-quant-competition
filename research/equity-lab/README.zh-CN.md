# 股票离线回测研究

[English](README.md)

基于每日 CSV 和 YAML 的回测实验室，包含八个离线策略 `sma_cross`、`momentum_20d`、`equal_weight`、`random_turnover`、`cnn_pattern`、`cnn_pattern_mvp`、`cnn_image_pattern` 和 `cnn_walk_forward_rank`。CNN 名称描述实验实现，不表示已经独立验证论文复现。这里不包含 Futu/OpenD SDK、账户代码、在线情绪数据源或执行适配器。

## 快速开始

进入本目录，配置外部 `DATA_ROOT` 和 `UV_PROJECT_ENVIRONMENT`，然后执行英文 README 的安装、`list`、`demo`、`backtest --strategy equal_weight` 和测试命令。

`HK.DEMO_A` 和 `HK.DEMO_B` 是虚构代码。演示生成 90 个工作日的数据，不代表交易所日历或历史行情。CSV 字段为 `date,open,high,low,close,volume,code`，文件名将代码中的点替换成下划线。每日数据位于外部项目目录的 `artifacts/data/processed/market/`。

`backtest` 接受 `--root`、`--config`、`--strategy-config` 和 `--universe`。YAML 中相对价格和报告路径以 `--root` 为基准，也支持绝对路径。没有显式文件时，优先使用存在的 `root/config/`，否则读取包内模板。环境覆盖项为 `EQUITY_LAB_BACKTEST_CONFIG`、`EQUITY_LAB_STRATEGY_CONFIG` 和 `EQUITY_LAB_UNIVERSE_FILE`。Python 服务另支持 `compare_benchmarks` 和 `benchmark_list`。模板成本仅用于演示，不是核实过的现行费用。

通常在 `artifacts/reports/backtests/` 生成 `portfolio_daily.csv`、`positions_daily.csv`、`summary.json`、`monthly_returns.csv`、`drawdown_daily.csv` 和可选 `equity_curve.png`，滚动验证、分位数及对比产物按条件生成。报告包含配置和数据元信息，也可能含自定义绝对路径或异常信息，分享前应审查。

## 结果解释与限制

这是使用滞后仓位、收盘到收盘收益的日频分数权重近似模型。不模拟港股整手、竞价、真实成交、最低佣金、换汇或券商权限。指标按每年 252 天年化，缺失价格可能前向填充，日历配置可能回退到观测日期并集。质量标记不会自动约束可交易性。复权价与分红输入应检查，避免重复计算。模型不会自动消除幸存者、退市和模型选择偏差。滚动验证元信息含固定窗口假设，不代表所有自定义配置已验证。

信号生成抛出异常后，服务保留全现金回退行为。`summary.json` 明确给出 `run_status=strategy_fallback` 和 `fallback_reasons`，CLI 打印原因并以状态码 2 退出。这是策略运行失败，不能当作成功的零收益策略。普通运行标记为 `run_status=completed`，仍不证明研究有效性。元信息中的相对路径在各平台统一使用 `/`。


前向填充之前会保留数据来源标记：`is_missing_bar` 表示原始开盘价或收盘价缺失，`is_interpolated` 标记已填充的收盘价，`is_halt` 仍是零成交量代理，不代表已确认的交易所停牌状态。成本优先使用策略的显式 `market`，其次是回测 `market`，最后按基准或股票池推断。比较基线目录会生成摘要声明的组合与持仓 CSV。`max_positions` 限制目标选股数量，渐进换手期间实际持仓数可能暂时超过它。非滚动验证 CNN 可能包含样本内预测，不能当作样本外证据。

## 配置与输出

使用 Python 3.12。导入模块前，将 `DATA_ROOT` 设置为共享数据目录的绝对路径，项目数据目录为 `DATA_ROOT/2026-quant-competition/research/equity-lab/`。也可以将 `WORKSPACE_CONFIG` 指向包含绝对路径 `data_root` 的 TOML 文件。默认查找 `CONFIG_ROOT/shared/workspace.toml`，或 `XDG_CONFIG_HOME/quant-competition/shared/workspace.toml`，后者默认是 `~/.config/quant-competition/shared/workspace.toml`。显式 `DATA_ROOT` 优先。配置缺失或无效会报错，包括解析 `--help` 前已导入配置的命令。

虚拟环境、输入数据、报告、图表和模型输出放在源码目录之外。使用 uv 时，将 `UV_PROJECT_ENVIRONMENT` 指向外部环境目录。演示生成器拒绝覆盖已有数据。演示数字仅用于验证软件，不代表投资收益或比赛表现。

## 许可证与执行边界

本子目录代码采用 MIT，不改变仓库其他部分和依赖的许可状态。这里没有券商连接和下单功能。研究输出不是 `targets.json`，不能直接交给执行服务。已发布执行 v1 JSON schema 接受 JP/US，运行时市场规范化还识别 HK，两者存在已有不一致，加密市场不受支持。这些行为均不使研究报告成为可执行目标。接入需要另行审查转换适配和执行验证。比赛产品资格以官方规则及券商、账户权限为准。

## 输入与实验验收

可选的[研究验收工具](../../docs/research/research-acceptance.zh-CN.md)使用显式清单检查输入并生成凭证，新入口不需要全局数据配置。软件检查成功不代表合格研究证据，所有者来源及留出集协议尚未接入。默认策略和既有报告保持不变。
