# 独立研究数据准备

[English canonical](datasets.md)

## 盘点保留日线的研究证据

对于已有的 IBKR 美股或港股日线 v2 快照，可用下面的离线命令复核完整文件清单，并列出尚缺的研究证据，无需重新下载。

```sh
python -m competition_tools.datasets.research_evidence --manifest /absolute/dataset/manifest.json --expected-sha256 MANIFEST_SHA256 --output /absolute/new-report.json
```

传入本次选定清单的精确小写 SHA256。Windows 使用带盘符的绝对路径。输出父目录必须已经存在，位于源码与输入数据集之外，输出文件必须尚不存在。即使核验期间其他进程创建了同名文件，工具也不会覆盖它。

首版只支持现有 `ibkr_daily` 生产者的拆股复权价格与当前固定股票池。它复用完整文件及凭证校验，核对生产者元数据，并绑定清单与凭证的原始字节，不读取连接配置。Databento、加密和 DEX 清单不在支持范围内。

退出码 0 表示成功写出盘点报告，报告的研究状态始终为 `blocked`。退出码 2 表示输入无效、完整性检查失败或写出失败，报错使用稳定代码，不包含私有路径。[封闭报告格式](../../schemas/research/daily-research-evidence-gap.v1.schema.json)只记录数据集身份、哈希、文件及字节数量和七项固定检查，不包含价格、标的或来源路径。`RETAINED_BYTES_VERIFIED` 通过，下列六项仍标为未验证，调用者填写信任标志不能改变结果。

| 要求 | 后续特定所有者适配器需要验证的证据 |
| --- | --- |
| 时点股票池 | 带日期的成分、纳入排除规则及目标范围的退市覆盖 |
| 历史证券身份 | 稳定标识，以及有生效日期的代码和证券类型映射 |
| 公司行动 | 完整的行动日期与价格、收益调整覆盖 |
| 历史可用时间 | 独立支持的信息可用时间和因果使用规则 |
| 所有者来源 | 绑定可信所有者、不可变资产版本与消费字节的发布协议 |
| 留出集治理 | 另行绑定候选、冻结代码配置、样本、访问及暴露历史的协议 |

这些是现有生产者尚不能满足的要求，不代表已经搜索了全部外部证据。数据集报告无法判断候选策略的留出集状态。哈希校验检测观察到的变化，不认证服务商，也不提供原子快照。本报告不升级研究或授权执行，详见[研究验收](research-acceptance.zh-CN.md)。

日线数据准备工具已经可用，无需其他 quant 系列仓库。小时线 DEX 试采集收到 HTTP403 后仍处于阻塞状态，尚无真实因子结果。下载前先选好数据类型，检查所需证据。

比赛仓库维护这些离线数据准备工具。根工具仅使用标准库，数字货币日线评估和小时线因子诊断在独立的加密研究环境中运行，执行模块不导入这些研究代码。

<a id="dexpaprika-hourly-pilot"></a>
## DexPaprika 小时线试采集

目前没有真实小时线因子结果。2026-10-22 的首次认证 `/usage` 检查返回 HTTP403，采集在一次请求后停止，没有重试或下载行情。仅凭响应无法确定原因，也未验证 Pro 权限。公开衍生统计的权限同样未确认。Pages 只展示冻结计划和阻断状态，不包含指标或实际覆盖率。

独立的 `competition.dex_dataset_spec.v1` 不改变旧日线 schema。将[示例](../../config/examples/dexpaprika-pilot.json)复制到仓库外，替换占位路径和协议哈希。采集前固定准确的数据集身份、请求区间、研究源码哈希和计划 manifest 位置。生成的 manifest 和报告再绑定实际文件哈希，不会假装事先知道未来 manifest 的哈希。

使用明确的 Ethereum 或 Solana 地址，以及不同的 `underlying_id`。这里不提供代码搜索、代币替换、池子发现或稳定币选择。可选的冻结 `pool_address` 会核对所属代币，其元数据只是当前快照，不代表历史流动性覆盖。

请求准确覆盖 90 天已结束的 UTC `1h` K 线，每个资产分为三段 720 小时，使用 `limit=1000`。根据[代币 OHLCV 契约](https://docs.dexpaprika.com/tutorials/token-ohlcv)，价格和成交额均为 USD。规范化行的字段固定为 `asset_id`、`time_open`、`interval_end`、`open`、`high`、`low`、`close`、`volume`。决策使用 `interval_end`，缺失小时保留为空。变化的重叠数据、重复或无效 K 线及未知单位会被拒绝。历史可用时间标为 `bar_close_proxy_unverified`，并非实际观测到的发布时间。小时线不替代 USDT 日线或做市事件输入。

硬限制为 100 次 HTTP 尝试、50MiB、900 秒，每分钟最多发起 20 次请求。每个资源最多两次尝试，仅传输失败和 HTTP429/500/502/503/504 可以重试。失败响应的字节和预检请求也计入预算。请求只到官方 Pro 主机，直接使用 Authorization，不跟随重定向。单次最多 30 秒，且不能超过剩余期限。计划会预留重试和用量检查，十个资产可能超限，此时 `fits_budget=false` 阻止采集。此次冻结的九资产计划预留 96 次尝试。

[用量读数](https://docs.dexpaprika.com/tutorials/check-credit-usage)覆盖整个账户，可能包含购买或超额额度。工具保守地取返回剩余额度与 Pro 套餐 5M 未用额度中的较小值。字段未知、余量不足、账期变化或累计用量倒退都会阻止后续请求。额度检查与服务端计费分开进行，仍有并发用量变化和账单不确定性。工具不购买数据、不改订阅或自动扩容设置。

完成及部分完成的快照以独占方式发布。被阻断的尝试保留在本工具拥有的 `<version>.partial` 工作目录中。正常检查点续跑会验证全部保留文件哈希，并扣除累计请求、字节和耗时预算。中断后支出不明、规格变化或文件损坏，需要新版本或人工核对，不会自动解除旧锁。DEX 不支持 `refresh` 和 Gateway 参数。

将 `DEXPAPRIKA_API_KEY` 保存在仓库外的 `CONFIG_ROOT/projects/<repo>/providers/dexpaprika.env`。迁移 CLI 读取明确指定的 `workspace.toml`，仅从指定原工作区的 `.env` 移走这一项，保留其他字节，并在目标旁保存仅所有者可访问的恢复副本。凭据冲突、重解析路径和源码仓库内的目标会被拒绝。完全为空的 `.git` 占位目录不视为仓库，非空元数据和 Git 文件仍被拒绝。Windows 迁移使用 Windows PowerShell 和 icacls 权限工具。研究子进程既不接收凭据文件参数，也不继承 `DEXPAPRIKA_API_KEY`。

```sh
python -m competition_tools.datasets.dex_credentials migrate --workspace /absolute/private/shared/workspace.toml --source-env /absolute/code/global-market-research/.env --destination /absolute/private/projects/2026-quant-competition/providers/dexpaprika.env
python -m competition_tools.team data plan --config /absolute/private/team.toml --spec /absolute/private/dex-dataset.json
python -m competition_tools.team data acquire --config /absolute/private/team.toml --spec /absolute/private/dex-dataset.json
python -m competition_tools.team factors --config /absolute/private/team.toml --spec /absolute/private/factor-protocol.json --output-root /absolute/data/new-factor-run
```

最后一条命令要求协议指定的不可变 manifest 已存在。此次被阻断的尝试没有研究观测，未执行或发布真实数据诊断与图表。定义见[因子说明](strategies.zh-CN.md#hourly-dex-factors)。已安装生产者和消费者的合成交付另行测试。

真实 DEX 指标公开功能保持关闭，直至权威许可来源经过明确的人工审查，并通过受审查的代码修改加入来源摘要。调用者自行提供的许可文件、条款摘录和校验值不能建立这种信任。

## 命令和存储

按[团队快速上手](../operations/team-quickstart.zh-CN.md)安装锁定的 offline 环境。`competition.team.v1` 不变，另行准备外部 JSON 数据规格，再运行以下命令。

```sh
python -m competition_tools.team data plan --config /absolute/private/team.toml --spec /absolute/private/dataset.json
python -m competition_tools.team data acquire --config /absolute/private/team.toml --spec /absolute/private/dataset.json
python -m competition_tools.team data inspect --config /absolute/private/team.toml --spec /absolute/private/dataset.json --manifest /absolute/data/2026-quant-competition/datasets/spot-study/v1/manifest.json
```

`plan` 和 `inspect` 不发起网络请求。`acquire` 默认不启动 Gateway 或登录。只有显式 IBKR 取数可通过 `--ensure-gateway` 和已启用的私有部署使用[Paper 登录前置步骤](../operations/gateway-login.zh-CN.md#数据任务的可选登录前置步骤)。下文独立的 Databento 试点支持事先授权的计费下载。数据工具不下单。输出沿用 `competition.team_result.v1`。日线部分覆盖返回退出码 2 及 `PARTIAL_COVERAGE`。DEX 使用 `PARTIAL_DEX_COVERAGE`，两者都不算下载完成。

数据位于配置的 `DATA_ROOT/2026-quant-competition/datasets/<dataset-id>/<version>/`。原有 v1/v2 数据源成功发布时不覆盖已有版本，未完成的任务保留在 `<version>.partial`，包含 manifest、receipt、请求日志和文件断点。相同规格再次运行时校验已完成文件的哈希并补充缺失下载，规格变化不能复用原断点。上游档案修订需建立新版本重新下载，恢复校验只确认本地保留字节，不能证明上游此后没有修订。Databento 试点使用下文的单次尝试规则。

## Databento 日线数据试点

本试点交付待验收的数据，不产生新的策略收益。独立契约 `competition.databento_dataset_spec.v1` 固定使用 `EQUS.SUMMARY`、`ohlcv-1d`、USD 原始价格和 UTC 区间 `[2025-01-01, 2026-01-01)`。固定标的为 SPY、QQQ、IWM、TLT、GLD、AAPL、MSFT、NVDA、AMZN、META，不代表历史标普 500 成分股。

在仓库外的 `databento.env` 保存唯一一条 `DATABENTO_API_KEY=...`。用已安装的根环境运行英文文档中的 `pilot_spec` 示例，创建外部 JSON 规格。Windows 使用带盘符的绝对路径。随后使用上文相同的 `team data plan`、`acquire` 和 `inspect` 参数。`plan` 不需要密钥或网络。日历检查使用锁定的可选 `daily-data` 环境。此契约拒绝 `refresh`、父 manifest 和 Gateway 参数。运行 `acquire` 前需审阅请求并授权计费下载。

上限为 0.10 美元、5 次元数据请求、1 次下载尝试、120 秒总活动时间和 20 MiB 未压缩 HTTP 响应。失败请求及其响应字节也计入限制。工具在下载前检查最新报价、计费字节数、记录数和适用单价，确认保守费用上界。服务端限制最多返回 4,000 条记录。触及限制或记录数不一致时拒绝结果。计费按未压缩二进制数据计算，不能用 CSV 文件大小推算账单。无法证明费用边界时会保留阻塞记录，不能当成免费请求。参见[官方 HTTP API](https://databento.com/docs/api-reference-historical?historical=http)。

所有结果，包括阻塞和部分完成的尝试，均保留在 `databento-us-daily-pilot/20261023-v1/`。固定的 `DATA_ROOT/2026-quant-competition/authorizations/databento-us-2025-pilot.attempt.json` 在预检前占用本轮授权，不随输出目录变化。需将 `WORKSPACE_CONFIG` 设为定义权威 `data_root` 的外部 `workspace.toml`。修改团队输出配置不能重置授权。`download-attempt.json` 表示计费请求可能已经开始。失败或中断后不自动重试。不要删除记录或换目录重复不确定的请求，应先核对保留证据和账户用量。重复采集会被拒绝，离线 `inspect` 则校验文件哈希和请求、规格身份。

仓库外保留原始 CSV、带日期的证券映射、逐标的标准化 CSV、覆盖报告、日历来源和 `competition.databento_dataset_manifest.v1`。无法证明上市日历时记录 `LISTING_CALENDAR_UNVERIFIED`，缺失观测不填充。价格保持 `raw`，公司行动仍未核验。所有结果均为 `accepted_research=false`，已有正式研究入口仍要求原有来源和复权契约。

[Summary 最终日线](https://databento.com/docs/datasets/equs-summary)包含盘后成交量，约在美东 20:15 发布。午夜的 bar 时间戳不代表数据可用时间。记录会区分发布时点假设与本次取得数据的时间，不保证历史可用时间。后续策略接入必须处理复权，并在输入实际可用后才能成交。

CoinPaprika Business 是独立候选数据源。早期本机检查在 TLS 阶段失败。后续不带密钥的 `/v1/key/info` 探测收到 HTTP403 HTML 边缘服务响应。响应来自边缘服务，尚未取得认证后的 API JSON，密钥和套餐状态仍待确认。本次没有交付 CoinPaprika 采集器。

下载锁阻止两个 CLI 同时修改同一版本。进程异常退出后，需先确认进程和断点，再人工处理失效锁。工具不会自动抢锁，也不更新共享 `current` 或 `latest`。

## Binance 现货日线

这个新增数据源需要明确选择，原四家服务商继续按各自配置使用。完整 JSON 示例见英文文档，两种语言使用相同配置键。实际研究池为 BTCUSDT、ETHUSDT、BNBUSDT、SOLUSDT、XRPUSDT、ADAUSDT、DOGEUSDT、LINKUSDT，标记为 `fixed_current`。

仅下载已结束月份的 `1d` 现货档案，最多20个产品，统一 USDT 报价。ZIP 必须匹配 `.CHECKSUM`，且只包含预期 CSV。拒绝不安全路径、符号链接、额外成员、压缩后超过25MiB或解压后超过100MiB的档案、非有限值、错误 OHLCV、重复日期和错误月份或日线时间戳。按照[发布方格式](https://github.com/binance/binance-public-data)，2025年前现货时间戳使用毫秒，2025年起使用微秒。

试验上限为20次请求、25MiB、600秒。扩池上限为5000次请求、1GiB、3600秒，目前串行下载。重试和404均计入请求数。单资源最多3次尝试，单次超时30秒，Retry-After最多60秒，并受总时限约束。域名和路径白名单及禁止重定向共同防止隐式换源。月份不完整、档案不存在或任务停止均保留为缺口。日线不能提供订单簿或做市成交证据，USDT不能当成USD。

## 股票输入和标普500边界

`licensed_import` 接受明确指定的外部 `input_directory`，其中 `<product>.csv` 列必须为 `date,open,high,low,close,volume`。同时指定市场、币种、交易日历、时区和原始或复权口径。导入会记录源文件哈希并校验价格，但不能证明供应商授权、复权正确性或信息发布时间。

`point_in_time` 还需外部 `membership_file`，列为 `stable_id,symbol,valid_from,valid_to,available_at`。同一身份的区间不得重叠。拒绝空文件、无关区间和发布时间未知的成分证据，每个请求产品都需在请求期间有相关成分记录。`membership.eligible` 同时检查有效期和截至指定日期可知的信息，但导入成分区间不会自动让现有引擎应用历史选股规则。授权数字货币日线只有完整覆盖连续365天日历的请求范围才标为已取得。交易所日历导入保留为部分覆盖，并记录 `CALENDAR_COVERAGE_UNVERIFIED`，因为导入器没有权威交易日安排，不要求周末或假日也有价格。已保留的源文件或成分字节变化时，必须建立新版本。

当前名单必须保持 `fixed_current`。SPY和当前成分名单仅覆盖各自定义的范围，历史标普500选股池仍待构建。完整扩池需要合法历史成分、稳定身份、退市与公司行动证据及匹配价格数据，不会补造已移除成分。

`ibkr` 目前仅提供明确配置的一个月 Paper 历史数据试验。需安装可选 `broker-data` 环境，以外部 `credential_file` 指定 `host`、`port`、`client_id`，并通过合约列表指定 `product`、`con_id`、`exchange`、`currency`。`price_basis` 必须为 `split_adjusted`，[IBKR文档](https://www.interactivebrokers.com/docs/tws-api/doc/md/historical-bars)说明 `TRADES` 调整拆股但不调整分红。只接受本机 Paper 端口4002，只读连接、请求 RTH `TRADES` 日线后断开，并保留空结果或部分结果。它不执行多年或全市场下载，试验成功不代表请求范围完整。批量券商下载需等待实际连接及成分、价格前提满足。

本子系统对 Algoseek、AIVIX、Index One 和 CoinPaprika 目前只给出准备状态及阻塞项，不猜测带认证的下载端点。`PROVIDER_CONTRACT_UNVERIFIED` 不代表供应商没有相应产品。其他已有接线保持原状，缺少权限不会触发付费请求或自动换源。

## 契约与证据

`schemas/research/` 定义 `competition.dataset_spec.v1`、`competition.dataset_manifest.v1`、`competition.dataset_receipt.v1` 和 `competition.coverage_report.v1`。manifest 绑定来源、规格、请求范围、实际覆盖、未知发布时间、原始和标准化文件哈希、字节数、行数、修订或校验和及标准化链路。没有独立证据时，发布时间保持未知。新数据不满足既有 `accepted_research` 门槛，也不替换事件输入 receipt。

完整 receipt 和原始观测保留在外部，Pages 只接收[评估报告](data-expansion-and-evaluation.zh-CN.md)对应的白名单汇总。新增数据及评估模块在各自目录按 MIT 授权，不改变无关执行代码或上游数据的许可。

## 有预算限制的股票日线快照

使用 `setup --profile daily-data` 安装锁定的可选券商和交易日历依赖，默认离线交付不变。`competition.dataset_spec.v2` 使用 `source=ibkr_daily`、外部 `connection_file`、明确的股票合约及独立基准。美股配置为 US/USD/XNYS/`America/New_York`，港股为 HK/HKD/XHKG/`Asia/Hong_Kong`。这是固定的当前股票池，不代表历史指数成分。[美股](../../config/examples/us-fixed-daily.json)和[港股](../../config/examples/hk-fixed-daily.json)示例含占位符，先复制到源码外，将 `connection_file` 替换为外部端点 JSON 的绝对路径，选择新版本并设置日期范围，再运行。

```powershell
& $pythonPath -m competition_tools.team data plan --config $teamConfig --spec $dailySpec
& $pythonPath -m competition_tools.team data acquire --config $teamConfig --spec $dailySpec
& $pythonPath -m competition_tools.team data inspect --config $teamConfig --spec $dailySpec --manifest $dailyManifest
& $pythonPath -m competition_tools.team data refresh --config $teamConfig --spec $nextVersionSpec --base-manifest $dailyManifest
```

最多支持 20 只股票和一个独立基准。代码、交易所和币种必须与券商确认的股票合约一致，请求前先通过单一 Paper 前缀账户检查。交易日历包含节假日、半日市和夏令时，仅将采集时已收盘的交易日纳入完整性判断。日线使用拆股调整后的每日 RTH TRADES，分红再投资尚未纳入，缺失价格保留为空。所有股票和基准覆盖全部已收盘交易日，才标为 `acquired`。来源、公司行动质量和研究验收仍未验证。

每个市场最多 120 次应用层券商请求、32 MiB 保留的原始及标准化数据、2400 秒。合约确认和失败请求计入预算，请求串行执行，开始时间至少相隔十秒，遇到券商错误停止，不重试或登录。每段覆盖一年或更短，并明确结束时间。这些是应用预算，不代表券商权限保证，也不衡量网络传输字节。原始文件保留解析后的 SDK 日线，标准化文件列为 `date,open,high,low,close,volume`。

完成的快照包含不可变的 `competition.dataset_manifest.v2` 和 `competition.dataset_receipt.v2`，记录文件哈希、合约身份、日历版本及日程哈希、预算和缺口。`inspect` 返回 `competition.coverage_report.v2`。未完成采集保留在本任务所有的 `.partial` 暂存目录，包含 `receipt.json` 和可校验检查点，暂不发布不可变 manifest。相同 acquire 可在剩余累计预算内继续。配置改变、文件损坏或已收盘交易日范围变化时，需要人工检查或新版本。不会自动删除遗留锁。

刷新需要完整且校验通过的父快照、新版本、保持数据集及产品、起始日期和价格口径不变，并且结束日期不得倒退。刷新将父数据复制到新暂存目录，检查最近五个可用的已收盘交易日，记录父 manifest 哈希，不记录私有路径。重叠区间改变时，重取受影响标的的完整历史。预算不足则保留未完成状态。重叠区间未变也不能排除更早的修订。刷新时保守保留 `last_full_verification`，公司行动及重叠区间外修订仍为 `not_verified`。父数据不会修改，也不更新 latest 指针。v1 `ibkr` 试验和显式启动选项的含义不变，v2 采集不会启动 Gateway 或授权下单。

数据源可能在日历确定休市的日期返回成交量为零、OHLC 完全相同的占位日线。这些记录保留在原始文件中，不计入标准化交易日，并通过 `excluded_non_session_bars` 和 `CLOSED_SESSION_ZERO_VOLUME_FLAT` 记录。休市日若有成交量或价格区间变化，仍会阻止采集。实际观察涉及 2023-07-17，[港交所当日取消了全部交易时段](https://www.hkex.com.hk/News/Market-Communications/2023/2307172news?sc_lang=en)。排除占位记录不等于填充缺失交易日，也不证明公司行动数据正确。
