# 离线研究

[English](README.md)

参见[团队快速开始](../docs/operations/team-quickstart.zh-CN.md)，从同一仓库安装独立环境并运行合成演示。默认流程不安装 quant 框架包，记账对照仍为可选功能。

- [加密做市](crypto-mm/README.zh-CN.md)：事件驱动的可见队列模拟，使用合成 Parquet 演示数据。
- [股票实验室](equity-lab/README.zh-CN.md)：基于每日 CSV/YAML 的分数权重回测，使用虚构港股代码演示数据。

这些目录都是独立的 Python 3.12 项目，各有 `uv.lock`、测试和 MIT 许可证，应进入对应目录安装并运行检查。根项目执行依赖和测试保持独立，根目录 Ruff 仍检查新增文件。英文文档为事实依据，并提供 zh-CN 阅读文档，没有引入运行时国际化系统。

生成的数据和报告放在配置的外部 `DATA_ROOT/2026-quant-competition/research/` 下。这些包均不连接券商，产物不是可执行的目标交接文件。已发布 v1 JSON schema 接受 JP/US，运行时市场规范化还识别 HK，两者存在尚未解决的不一致，加密市场不受支持。比赛资格及真实市场适用性需要单独核实，解读前请查看各包限制。

MIT 仅用于新增子项目代码，不改变根目录已有代码或第三方依赖的许可状态。

## 输入与实验验收

可选的[研究验收工具](../docs/research/research-acceptance.zh-CN.md)使用显式清单检查输入并生成凭证，新入口不需要全局数据配置。软件检查成功不代表合格研究证据，所有者来源及留出集协议尚未接入。默认策略和既有报告保持不变。

## 可选记账对照

独立的[固定版本适配器](platform-compare/README.zh-CN.md) 通过单独环境调用公开 `quant-platform` 记账 API。[对照指南](../docs/research/accounting-comparison.zh-CN.md) 说明原策略决策、明确时钟、HK/US 合成诊断和真实输入的阻塞条件，不替换原引擎，也不发布新的结果快照。
