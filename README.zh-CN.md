# 2026 Quant Competition

[English](README.md) · [项目网站](https://runchengxie.github.io/2026-quant-competition/zh-CN/) · [文档目录](docs/README.zh-CN.md)

这个项目用来准备 2026 年香港量化交易比赛。你可以用它整理行情数据、试跑交易策略，再把过程和结果保存下来。

第一次接触的话，先跑离线演示。演示使用虚构数据，在自己的电脑上运行，不会下单。你不需要券商账户、API 密钥，也不用安装其他 `quant-*` 项目。

## 我能用它做什么

| 你想做的事 | 从这里开始 |
| --- | --- |
| 先跑一个例子，看看项目怎么用 | [离线演示入门](docs/operations/team-quickstart.zh-CN.md) |
| 拿过去的行情试跑策略 | [研究示例](research/README.zh-CN.md) |
| 准备行情数据 | [数据准备](docs/research/datasets.zh-CN.md) |
| 看懂已有结果和它们的限制 | [研究结果说明](docs/research/strategy-validation-2026-10-19.zh-CN.md) |
| 看看现金、股数和手续费怎样影响结果 | [记账对照](docs/research/accounting-comparison.zh-CN.md) |

拿过去的行情试跑策略，通常叫作回测。它可以帮助你检查策略会怎样买卖，结果好看也不能保证以后赚钱。

## 第一次怎么跑

1. 安装 Python 3.12 和 `uv`，后者用来安装项目需要的 Python 软件包。然后下载或克隆本项目。
2. 按[离线演示入门](docs/operations/team-quickstart.zh-CN.md)安装环境，并选一个源码目录以外的文件夹存放数据和结果。
3. 先跑股票演示。它会生成一份示例数据和回测报告。同一份指南也提供加密市场演示。

这两个演示都不需要填写账户密钥或购买行情服务。想先看看项目长什么样，可以直接打开[项目网站](https://runchengxie.github.io/2026-quant-competition/zh-CN/)。

## 目前做到哪一步了

离线演示和研究工具已经可以使用。比赛策略还没有最终确定或注册，现有报告记录的是历史实验和软件检查结果。

连接券商执行交易还需要单独配置，并由人监督测试。Paper 指用虚拟资金练习的模拟账户。使用券商相关命令前，先读[模拟交易检查清单](docs/operations/release-checks.md)。跑通离线演示，不能证明券商连接已经可用。

## 接下来读什么

[文档目录](docs/README.zh-CN.md)按任务整理了比赛资料、研究说明、项目结构和账户配置。行情数据、生成的报告和密钥都放在源码目录之外。

## 想参与开发

安装开发环境、运行测试和构建网站的方法见[开发指南](docs/development.zh-CN.md)。各部分代码负责什么、交易流程还有哪些限制，见[项目结构与当前限制](docs/project-overview.zh-CN.md)。
