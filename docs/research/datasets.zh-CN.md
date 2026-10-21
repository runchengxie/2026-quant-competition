# 独立研究数据准备

[English canonical](datasets.md)

比赛仓库维护离线数据准备工具，不依赖 quant 系列的本地仓库。根工具仅使用标准库，数字货币日线评估留在现有加密研究环境中，执行模块不导入这些研究代码。

## 命令和存储

按[团队快速上手](../operations/team-quickstart.zh-CN.md)安装锁定的 offline 环境。`competition.team.v1` 不变，另行准备外部 JSON 数据规格：

```sh
python -m competition_tools.team data plan --config /absolute/private/team.toml --spec /absolute/private/dataset.json
python -m competition_tools.team data acquire --config /absolute/private/team.toml --spec /absolute/private/dataset.json
python -m competition_tools.team data inspect --config /absolute/private/team.toml --spec /absolute/private/dataset.json --manifest /absolute/data/2026-quant-competition/datasets/spot-study/v1/manifest.json
```

`plan` 和 `inspect` 不发起网络请求。`acquire` 默认不启动Gateway或登录。只有显式IBKR取数可通过 `--ensure-gateway` 和已启用的私有部署使用[Paper登录前置步骤](../operations/gateway-login.zh-CN.md#数据任务的可选登录前置步骤)，任何模式均不购买数据或下单。输出沿用 `competition.team_result.v1`。部分覆盖返回退出码2及 `PARTIAL_COVERAGE`，不算下载完成。

数据位于配置的 `DATA_ROOT/2026-quant-competition/datasets/<dataset-id>/<version>/`。成功发布不覆盖已有版本。未完成的任务保留在 `<version>.partial`，包含 manifest、receipt、请求日志和文件断点。相同规格再次运行时校验已完成文件的哈希并补充缺失下载，规格变化不能复用原断点。上游档案修订需建立新版本重新下载，恢复校验只确认本地保留字节，不能证明上游此后没有修订。

下载锁阻止两个 CLI 同时修改同一版本。进程异常退出后，需先确认进程和断点，再人工处理失效锁。工具不会自动抢锁，也不更新共享 `current` 或 `latest`。

## Binance 现货日线

这是明确选择的新增数据源，不是原四家服务商的自动替代。完整 JSON 示例见英文文档，两种语言使用相同配置键。实际研究池为 BTCUSDT、ETHUSDT、BNBUSDT、SOLUSDT、XRPUSDT、ADAUSDT、DOGEUSDT、LINKUSDT，标记为 `fixed_current`。

仅下载已结束月份的 `1d` 现货档案，最多20个产品，统一 USDT 报价。ZIP 必须匹配 `.CHECKSUM`，且只包含预期 CSV。拒绝不安全路径、符号链接、额外成员、压缩后超过25MiB或解压后超过100MiB的档案、非有限值、错误 OHLCV、重复日期和错误月份或日线时间戳。按照[发布方格式](https://github.com/binance/binance-public-data)，2025年前现货时间戳使用毫秒，2025年起使用微秒。

试验上限为20次请求、25MiB、600秒；扩池上限为5000次请求、1GiB、3600秒，目前串行下载。重试和404均计入请求数。单资源最多3次尝试，单次超时30秒，Retry-After最多60秒，并受总时限约束。域名和路径白名单及禁止重定向共同防止隐式换源。月份不完整、档案不存在或任务停止均保留为缺口。日线不能提供订单簿或做市成交证据，USDT不能当成USD。

## 股票输入和标普500边界

`licensed_import` 接受明确指定的外部 `input_directory`，其中 `<product>.csv` 列必须为 `date,open,high,low,close,volume`。同时指定市场、币种、交易日历、时区和原始或复权口径。导入会记录源文件哈希并校验价格，但不能证明供应商授权、复权正确性或信息发布时间。

`point_in_time` 还需外部 `membership_file`，列为 `stable_id,symbol,valid_from,valid_to,available_at`。同一身份的区间不得重叠。拒绝空文件、无关区间和发布时间未知的成分证据，每个请求产品都需在请求期间有相关成分记录。`membership.eligible` 同时检查有效期和截至指定日期可知的信息，但导入成分区间不会自动让现有引擎应用历史选股规则。授权数字货币日线只有完整覆盖连续365天日历的请求范围才标为已取得。交易所日历导入保留为部分覆盖，并记录 `CALENDAR_COVERAGE_UNVERIFIED`，因为导入器没有权威交易日安排，不要求周末或假日也有价格。已保留的源文件或成分字节变化时，必须建立新版本。

当前名单必须保持 `fixed_current`。SPY和当前成分名单都不是历史标普500选股池。完整扩池需要合法历史成分、稳定身份、退市与公司行动证据及匹配价格数据，不会补造已移除成分。

`ibkr` 目前仅提供明确配置的一个月 Paper 历史数据试验。需安装可选 `broker-data` 环境，以外部 `credential_file` 指定 `host`、`port`、`client_id`，并通过合约列表指定 `product`、`con_id`、`exchange`、`currency`。`price_basis` 必须为 `split_adjusted`，[IBKR文档](https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-bars)说明 `TRADES` 调整拆股但不调整分红。只接受本机 Paper 端口4002，只读连接、请求 RTH `TRADES` 日线后断开，并保留空结果或部分结果。它不执行多年或全市场下载，试验成功不代表请求范围完整。批量券商下载需等待实际连接及成分、价格前提满足。

本子系统对 Algoseek、AIVIX、Index One 和 CoinPaprika 目前只给出准备状态及阻塞项，不猜测带认证的下载端点。`PROVIDER_CONTRACT_UNVERIFIED` 不代表供应商没有相应产品。其他已有接线保持原状，缺少权限不会触发付费请求或自动换源。

## 契约与证据

`schemas/research/` 定义 `competition.dataset_spec.v1`、`competition.dataset_manifest.v1`、`competition.dataset_receipt.v1` 和 `competition.coverage_report.v1`。manifest 绑定来源、规格、请求范围、实际覆盖、未知发布时间、原始和标准化文件哈希、字节数、行数、修订或校验和及标准化链路。没有独立证据时，发布时间保持未知。新数据不满足既有 `accepted_research` 门槛，也不替换事件输入 receipt。

完整 receipt 和原始观测保留在外部，Pages 只接收[评估报告](data-expansion-and-evaluation.zh-CN.md)对应的白名单汇总。新增数据及评估模块在各自目录按 MIT 授权，不改变无关执行代码或上游数据的许可。

## 有预算限制的股票日线快照

使用 `setup --profile daily-data` 安装锁定的可选券商和交易日历依赖，默认离线交付不变。`competition.dataset_spec.v2` 使用 `source=ibkr_daily`、外部 `connection_file`、明确的股票合约及独立基准。美股配置为 US/USD/XNYS/`America/New_York`，港股为 HK/HKD/XHKG/`Asia/Hong_Kong`。这是固定的当前股票池，不代表历史指数成分。[美股](../../config/examples/us-fixed-daily.json)和[港股](../../config/examples/hk-fixed-daily.json)示例含占位符：先复制到源码外，将 `connection_file` 替换为外部端点 JSON 的绝对路径，选择新版本并设置日期范围，再运行。

```powershell
& $pythonPath -m competition_tools.team data plan --config $teamConfig --spec $dailySpec
& $pythonPath -m competition_tools.team data acquire --config $teamConfig --spec $dailySpec
& $pythonPath -m competition_tools.team data inspect --config $teamConfig --spec $dailySpec --manifest $dailyManifest
& $pythonPath -m competition_tools.team data refresh --config $teamConfig --spec $nextVersionSpec --base-manifest $dailyManifest
```

最多支持 20 只股票和一个独立基准。代码、交易所和币种必须与券商确认的股票合约一致，请求前先通过单一 Paper 前缀账户检查。交易日历包含节假日、半日市和夏令时，仅将采集时已收盘的交易日纳入完整性判断。日线使用拆股调整后的每日 RTH TRADES，不是包含分红再投资的总收益数据，也不填充缺失价格。所有股票和基准覆盖全部已收盘交易日，才标为 `acquired`；来源、公司行动质量和研究验收仍未验证。

每个市场最多 120 次应用层券商请求、32 MiB 保留的原始及标准化数据、2400 秒。合约确认和失败请求计入预算，请求串行执行，开始时间至少相隔十秒，遇到券商错误停止，不重试或登录。每段覆盖一年或更短，并明确结束时间。这些是应用预算，不代表券商权限保证，也不衡量网络传输字节。原始文件保留解析后的 SDK 日线，标准化文件列为 `date,open,high,low,close,volume`。

完成的快照包含不可变的 `competition.dataset_manifest.v2` 和 `competition.dataset_receipt.v2`，记录文件哈希、合约身份、日历版本及日程哈希、预算和缺口。`inspect` 返回 `competition.coverage_report.v2`。未完成采集保留在本任务所有的 `.partial` 暂存目录，包含 `receipt.json` 和可校验检查点，暂不发布不可变 manifest。相同 acquire 可在剩余累计预算内继续。配置改变、文件损坏或已收盘交易日范围变化时，需要人工检查或新版本。不会自动删除遗留锁。

刷新需要完整且校验通过的父快照、新版本、保持数据集及产品、起始日期和价格口径不变，并且结束日期不得倒退。刷新将父数据复制到新暂存目录，检查最近五个可用的已收盘交易日，记录父 manifest 哈希，不记录私有路径。重叠区间改变时，重取受影响标的的完整历史；预算不足则保留未完成状态。重叠区间未变也不能排除更早的修订。刷新时保守保留 `last_full_verification`，公司行动及重叠区间外修订仍为 `not_verified`。父数据不会修改，也不更新 latest 指针。v1 `ibkr` 试验和显式启动选项的含义不变，v2 采集不会启动 Gateway 或授权下单。
