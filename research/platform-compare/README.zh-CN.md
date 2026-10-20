# 独立记账与对照实验

[English](README.md)

这个独立离线包使用比赛项目自有的 USD 价格账本，支持 HK/US 记账对照及五市场下一开盘诊断。不安装 `quant-platform` 或 `research-contracts`，也不依赖相邻仓库。结果不认证研究有效性，不连接券商。

账本从公开提交 `28a32ba707ad72d1eb68cde5075663e1b3819ac7` 提取，迁入 `platform_compare.accounting`，保留 Apache-2.0 许可证、来源清单和文件哈希；适配代码继续使用 MIT。见 [来源记录](src/platform_compare/accounting/ORIGIN.json)。该提交只表示代码来源，不表示仍由外部框架计算。独立锁文件继续隔离各研究包的依赖版本。

使用 Python 3.12，把环境放到源码外：

```powershell
$env:UV_PROJECT_ENVIRONMENT = $comparisonEnvironment
uv sync --locked --group dev --project research/platform-compare
& $comparisonPython -m platform_compare.cli --help
& $comparisonPython -m platform_compare.cli run --request $requestJson --dataset-root $datasetRoot --output $newBundleDirectory
& $comparisonPython -m platform_compare.cli verify --request $requestJson --dataset-root $datasetRoot --bundle $newBundleDirectory
```

输入、环境和输出包均存放在解析后的 `DATA_ROOT/2026-quant-competition/` 下，不能放进源码。输出目录必须尚不存在。当前只有交易日期的历史 CSV 不具备所需的因果时钟，不能根据文件名或日期推断可用时间、成交时间、汇率和每手数量。

## 输入与输出契约

严格的 `competition.accounting_request.v2` 请求只包含 `schema_version`、`provider`、`run_id`、`market`、`synthetic`、`evidence`、`input_ref`、`input_fingerprint`、`config`、`config_fingerprint`。`provider` 为 `{repository: "2026-quant-competition", engine: "competition.usd_price_ledger", version: "1"}`，`market` 为 `HK` 或 `US`，`synthetic` 在此版本必须为 `true`，`evidence` 为 `software_diagnostic`。

`input_ref` 包含 `artifact_id`、规范相对路径 `relative_path`、SHA256 `sha256` 和整数 `size_bytes`，哈希必须等于 `input_fingerprint`。引用文件必须位于显式数据根目录内，回放前后校验字节。这只能绑定输入文件，不能保证数据商来源可信。

独立的 `competition.accounting_inputs.v1` JSON 文件只包含 `schema_version`、`market`、`synthetic`、`upstream_input_fingerprint`、`instruments`、`prices`、`fx`、`decisions`、`valuation_times`、`research_clock`。价格和汇率仅从这些已校验字节读取。适配器根据文件引用向 owner 提供 `ArtifactRef`，不会在请求中重复接受未绑定的行情记录。

金额使用有限十进制字符串。拒绝 JSON 浮点数、用布尔值冒充计数、重复键、未知字段和不支持的单位。时间必须明确为 UTC，最多精确到微秒，与 owner 的 Python datetime 契约一致。更高精度会被拒绝，不会截断。研究时钟、可用性、成交资格和会话策略都须明确提供。此版本只接受合成输入。`synthetic=false` 一律返回 `REAL_INPUT_EVIDENCE_UNVERIFIED`，即使时钟和哈希内部一致。真实输入需要另外接入独立核验来源和时序证据的适配器，修改调用者标记不能提供这些证据。

`config` 只包含 `initial_cash`、`sizing_mode`、`commission_bps`、`slippage_bps`、`fx_cost_bps`、`max_price_age_seconds`、`max_fx_age_seconds`、`fx_pairs`、`allow_assumed_availability`、`return_basis`、`allow_modeled_execution_prices`。指纹为 UTF-8 JSON 的 SHA256，键排序、紧凑分隔符、`ensure_ascii=false`，禁止非有限数。策略决策序列使用相同的规范哈希方法。记录的具体字段见 [contracts.py](src/platform_compare/contracts.py)。

结算、现金和持仓估值、费用、汇率、整手取整及独立对账均由 provider 完成。其 publisher 生成 owner manifest、Parquet 文件和诊断内容。验证调用真正的 owner reader，检查哈希，并核对请求、输入引用、配置、时钟、backend 和诊断层级。验证还会在源码外的临时目录中，通过本地账本 API 和 publisher 完整重放请求，并比较全部诊断结果。这会拒绝篡改 manifest 后重新贴标签的旧结果，以及改动表格或替换请求的情况。临时重放文件随后清除，不信任额外的 `comparison.json` 文件。

`competition.accounting_result.v2` 是从已验证文件派生的汇总，包含 provider、输入、配置、决策序列和 manifest 指纹，十进制 USD 现金、净值、持仓、费用和成交额，以及 sizing、费用假设、计数、`orders_submitted=false`、`order_lifecycle=false`。另一个进程可以通过 `verify` 重新生成。它不属于 `accepted_research`，也不能证明券商执行。现金和股数模型会产生与滞后一周期权重代理不同的持仓漂移，不保证收益数值相同。

## 测试与边界

```powershell
& $comparisonPython -m pytest research/platform-compare/tests -q
```

测试使用比赛项目自有账本，对合成的全现金、美股持仓、费用、港股不同手数和汇率输入执行回放、发布和验证。覆盖错误单位、过期或未来行情、文件改动、请求替换、表格篡改和安全的 CLI 报错。不需要授权行情、账户或券商网络调用。适配代码使用 MIT，迁入的账本及其测试保留 Apache-2.0。

## 历史兼容

新请求和汇总使用 v2，旧的固定框架 v1 文件保留原样，不能自动改写来源。五市场输入锁升级为 `global_etf_next_open.input_lock.v2`，以 `accounting_engine` 记录本地实现，不再写入 `platform_revision`。原有 CLI、包路径及 `setup --profile framework` 名称保留兼容；该 profile 现在只安装本地记账包。
