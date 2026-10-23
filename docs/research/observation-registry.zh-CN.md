# 手动观察登记

[English](observation-registry.md)

冻结协议只是记录一次研究决定，不代表已经开始采集数据或积累后续业绩。没有符合条件的新数据时，状态为 `awaiting_new_data`，`first_eligible_observation_at` 为 null。

固定的六个候选是美股 `mom20_monthly`、`mom20_monthly_buffer20`、`ew_monthly`，以及加密 `trend200_vol40_strict`、`ew_trend_gross_matched`、`ew_legacy`。美股费用为 20/40 bps，加密为 0/10/25 bps。每个策略和费用组合从净值 1 开始，始终从同一个初始状态连续回放。历史实验的各窗口独立从现金开始，不能拼成这个连续账户。

`competition.observation_protocol.v1` 绑定候选、费用、真实 UTC 冻结时间、已知观察截止时间、每个市场恰好 252 行不计分的预热数据、标的池、源码摘要与保留源码、初始净值、估值口径、严格规则中的零波动率处理、导入预算和停止条件。修改研究方案须建立新登记，不能覆盖原协议或已接受回执。

配置、预热 JSON、manifest、源码快照与回执全部放在源码目录外。使用已配置的外部团队环境：

`/absolute/...` 是占位路径，Windows 须使用根据项目配置解析的带盘符绝对路径。回放环境须使用保留源码或字节完全匹配的科学源码；可编辑安装的源码发生变化时，冻结协议的生产者摘要检查会阻塞。

```sh
python -m competition_tools.team observe freeze --config /absolute/team.toml --spec /absolute/protocol-template.json --registry-root /absolute/new-registry
python -m competition_tools.team observe append --config /absolute/team.toml --manifest /absolute/import.json --registry-root /absolute/existing-registry
python -m competition_tools.team observe status --config /absolute/team.toml --registry-root /absolute/existing-registry
```

CLI 记录当前 UTC 时间，不提供倒填冻结或导入时间的选项。Python API 允许显式传入时钟，供确定性测试使用。

每份 `competition.observation_import.v1` 包含一个市场完整且不变的 252 行预热数据，以及累计观察数据、逐行可用时间、价格口径和计价币种。美股沿用复权美元价格近似模型，加密使用原始 USDT 价格。USD 与 USDT 不能混用。导入须提供完整前缀，让独立安装的研究包从原初始账户回放。根项目独立复核计算，并在接受扩展前比较此前全部净值及未扣费账本记录。

可用时间须晚于冻结与已知截止时间，晚于对应完整日线，且不晚于导入时钟。应有交易日不能缺失。合成导入明确使用合成逐日网格，真实美股使用 `XNYS`，加密使用连续 UTC 日期。可用时间不明时阻塞导入。真实可用性证据须经过审查，并将摘要登记到源码中的 `TRUSTED_AVAILABILITY_EVIDENCE`，该表初始为空。调用者设置标志不能建立信任。合成证据始终标为 `synthetic_valuation_only`。

`competition.observation_availability_review.v1` 绑定具体协议、市场和归一化导入摘要，并记录核实决定及带时区的审阅时间。计算摘要前，将可用时间统一为 UTC ISO-8601，仅省略 `availability_evidence` 字段，其他导入内容全部计入。其他导入的审阅记录不能借用，检查已接受回执时会重新核验原证据字节。真实美股可在同一个 UTC 日期的交易所收盘后提供数据，加密与合成逐日网格则须等 UTC 当日完成。

不要把旧缓存尾部导入为后续样本。如果预热数据过旧，与首个拟计分日期之间缺少交易日，导入会阻塞。获得已授权的新数据并补齐预热后，应建立新协议，不能修改原协议。仅有价格观察也不等于具备成交证据。

每次导入最多新增 512 个日期，验证、计算和准备回执合计使用同一个 3600 秒预算。此前日期保留在原账户中，不计为新增日期。预算不明或已耗尽时，不能重复同一价格计算，仅修改可用时间等元数据也不能重置预算。没有自动重试或预算重置。

完全相同的数据及等价时区写法不会重复记账。价格冲突、缺失或乱序日期、源码字节变化、此前账本记录变化及并发追加都会阻塞接受。失败尝试不会产生已接受回执。回执摘要绑定保留的请求和结果文件、原导入文件字节及上一份回执。这能发现本地改动，但不是外部时间戳，也不能证明此前无人看过数据。

这些命令不会下载、调度、登录、连接券商或下单。采集、调度与执行均需另行授权。
