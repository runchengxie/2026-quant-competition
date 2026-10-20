# 国际市场离线实验

[English](international-experiments.md)

比赛仓库维护两个不同的国际市场研究实验。它们读取显式外部输入，不下载数据、提交订单或确认策略资格。本次交付不包含私有配置、研究笔记、供应商原始数据或原私有 Git 历史。

| 实验 | 安装后入口 | 环境 | 市场 |
| --- | --- | --- | --- |
| 六市场月度分数权重诊断 | `equity_lab.international.six_market_run` | 默认 `equity-lab`，普通依赖 | US/HK/UK/AU/CA/SG |
| 冻结调仓计划的 next-open 价格账本诊断 | `platform_compare.next_open.run` | 可选 `platform-compare`，固定框架和 `exchange-calendars==4.13.2` | US/HK/UK/AU/SG |

先完成[团队环境安装](../operations/team-quickstart.zh-CN.md)，将[虚构六市场配置](../../config/examples/international-six-market.synthetic.yaml)复制到 Git 外，将 `data_root` 改为自己的外部输入绝对路径。模板只有新造的示例权重，没有观测数据，也不能证明数据是合成的或具有使用授权。

```sh
python -m competition_tools.team run international --config /absolute/private/team.toml --experiment-config /absolute/private/six-market.yml --output-root /absolute/data/six-market-run-001
```

也可用已安装股票环境运行 `python -m equity_lab.international.six_market_run --config FILE --output-dir NEW_EXTERNAL_DIR --json`。六个资产 CSV 需要 `date,close,volume`，五个汇率 CSV 需要 `date,usd_per_local`。日期是当地日观测，并非日内可用时间戳。基准货币为 USD，资产与汇率必须有 24 个共同日历月。缺少加拿大或其他市场时失败，不缩减实验范围。通过 `distribution_files` 提供的分配 CSV 需要 `date,cash_per_share,currency,source`。

原有分数权重计算、月末观测计划、收益分项和报告 schema 得到保留。这是旧有诊断模型，不是现金与股份自洽的账本，也不是交易所日历驱动的 next-open 模拟器。它用已有前值对齐观测，拒绝部分陈旧日频资产序列，但不独立验证所有缺失观测或公司行动。最后一个月末没有后续资产交易日时，模型可能复用该观测日。分配覆盖按所提供的日期范围判断，不代表独立核实了全部支付记录。分配缺失或不完整时，总回报报告不可用。日频年化使用 252 个观测，因此月频合成 fixture 只验证软件，不能说明收益。输入哈希检测字节变化，不能证明供应商来源。输出保留 `global_six_market.summary.v1`、`global_six_market.total_return_summary.v1` 和 `global_six_market.inputs_lock.v1`，分享前应检查本地报告中的私有路径。

## 可选 next-open 回放

```sh
python -m competition_tools.team setup --config /absolute/private/team.toml --profile framework
python -m competition_tools.team run next-open --config /absolute/private/team.toml --experiment-config /absolute/private/next-open.yml --output-root /absolute/data/next-open-run-001
```

也可用已安装框架环境运行 `python -m platform_compare.next_open.run --config FILE --output-dir NEW_EXTERNAL_DIR --json`。显式配置包括 `experiment_id`、`strategy_id`、`data_root`、`target_schedule_path`、`signal_cutoff`、`initial_cash_usd`、`sizing_mode`、`max_price_age_days`、`max_fx_age_days`、`production_eligible`、`return_basis` 和 `reference_cost_bps`。保留的实验协议要求截止日期 `2026-10-01`、分数持仓、`production_eligible: false`、`return_basis: usd_price_nav` 和参考成本 `{commission: 5, equity_slippage: 5, fx: 0}`。这些是诊断协议限制，不代表已选定交易策略。本项目不分发私有调仓计划或默认配置。

输入包括 `research.target_schedule.v1` 调仓计划、绑定哈希的 `dataset-manifest.json` 以及五个 ETF 文件 `US_SPY.csv`、`HK_2800.csv`、`UK_ISF.csv`、`AU_STW.csv`、`SG_ES3.csv`。还需要五个汇率文件 `FX_AUDUSD.csv`、`FX_GBPUSD.csv`、`FX_USDCAD.csv`、`FX_USDHKD.csv`、`FX_USDSGD.csv`。CAD 只保留为输入证据，不增加加拿大 ETF。文件列为 `date,open,high,low,close,price_semantics,execution_eligible`。清单必须声明匹配的哈希、`execution_eligible: false` 和截止日期。此契约不同于 HK/US 的 `competition.accounting_request.v1` 适配器。

信号时钟采用各来源交易日最晚的预定 UTC 收盘时间。随后第一个预定开盘必须有来源 bar，否则记录拒绝输入，不改用收盘价兜底。日历为 XNYS/XHKG/XLON/XASX/XSES。收盘数据可用性和同交易日汇率中点时序仍是显式假设。结果为不含股息的 USD 价格 NAV。36 组成本组合仍是诊断，零汇兑成本只是乐观下界。输入锁保留 `global_etf_next_open.input_lock.v1`，记录实际固定框架版本，并核对已安装提供方元数据。

两个入口都拒绝已有输出目录或源码目录。团队入口将子进程日志保存在外部 `<data_root>/2026-quant-competition/team-runs/`，只返回脱敏结果。实验不改变默认五区域轮动、执行契约或历史公开的 24 项结果快照，也不发布新的真实数据收益结论。新增代码使用各子项目已有的目录级 MIT 许可证。
