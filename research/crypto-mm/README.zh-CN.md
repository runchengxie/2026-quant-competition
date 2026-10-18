# 加密做市离线研究

[English](README.md)

这个事件驱动模拟器根据可见盘口队列、公开成交和资金费率信号模拟做市。B0 使用库存偏移报价，B1 加入盘口不平衡，B2 根据波动调整价差，B3 加入资金费率相关的目标库存。解读结果前请阅读[模拟假设](docs/assumptions.zh-CN.md)。

## 快速开始

进入本目录，先配置外部 `DATA_ROOT` 和 `UV_PROJECT_ENVIRONMENT`，再执行英文 README 中的可复制命令。`uv sync --locked --group dev` 安装锁定依赖，`python -m crypto_mm.demo` 生成演示数据，随后可运行审计、B0 回测、信号分析、绘图和测试。

演示在 `raw_data/{orderbook,trades,fundings}/` 下生成九个 Parquet 文件，并在同级写入 `demo-manifest.json`。文件名是 `YYYY-MM-DD.parquet`。当前读取器固定要求 `2026-03-19` 至 `2026-03-21` 三个日期标签，它们不代表提供了真实历史行情。字段包括纳秒 `datetime`、20 档 `bid_price_N`/`ask_price_N`/`bid_qty_N`/`ask_qty_N`、成交 `price`/`size`/`is_maker_ask` 和 `funding_rate`，类型和生成示例见 `market_data.py` 与 `demo.py`。

回测和分析打印到 stdout。绘图默认运行四个策略，写入外部项目目录的 `figures/`。绘图没有参数解析器，任何参数都会被忽略，`--help` 也可能触发绘图。敏感性扫描用于探索，不保证得到最优参数。程序化配置及校验见 `config.py` 的 `StrategyConfig` 和 `SimulationConfig`。

## 已知限制

自定义信号采样间隔可能导致期限标签错误，因为期限被用作样本偏移。数据审计没有全面拒绝 NaN 或无穷值，通过审计不代表数值全部有效。这些已知问题仍保留，没有修改测试预期来掩盖。本次没有复现完整历史回测或参数扫描。

## 配置与输出

使用 Python 3.12。导入模块前，将 `DATA_ROOT` 设置为共享数据目录的绝对路径，项目数据目录为 `DATA_ROOT/2026-quant-competition/research/crypto-mm/`。也可以将 `WORKSPACE_CONFIG` 指向包含绝对路径 `data_root` 的 TOML 文件。默认查找 `CONFIG_ROOT/shared/workspace.toml`，或 `XDG_CONFIG_HOME/quant-competition/shared/workspace.toml`，后者默认是 `~/.config/quant-competition/shared/workspace.toml`。显式 `DATA_ROOT` 优先。配置缺失或无效会报错，包括解析 `--help` 前已导入配置的命令。

虚拟环境、输入数据、报告、图表和模型输出放在源码目录之外。使用 uv 时，将 `UV_PROJECT_ENVIRONMENT` 指向外部环境目录。演示生成器拒绝覆盖已有数据。演示数字仅用于验证软件，不代表投资收益或比赛表现。

## 许可证与执行边界

本子目录代码采用 MIT，不改变仓库其他部分和依赖的许可状态。这里没有券商连接和下单功能。研究输出不是 `targets.json`，不能直接交给执行服务。已发布执行 v1 JSON schema 接受 JP/US，运行时市场规范化还识别 HK，两者存在已有不一致，加密市场不受支持。这些行为均不使研究报告成为可执行目标。接入需要另行审查转换适配和执行验证。比赛产品资格以官方规则及券商、账户权限为准。
