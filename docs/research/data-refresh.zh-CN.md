# 有界补数据与新观察

下一步需要新的证据。本次历史稳健性回放没有下载新行情，已接受的真实新观察仍为零。离线准备只生成可审阅的请求清单和预热检查，不登录、不启动 Gateway、不启用调度，也不批准导入。

## 当前已准备的请求

私有清单在 2026-10-23 UTC 冻结，已完成日期边界为 2026-10-22。准备时仍在交易或尚未完成的日期不包含在内。

| 市场 | 保留数据的共同日期 | 已准备范围 | 计划资源或调用数 | 启动状态 |
| --- | --- | --- | ---: | --- |
| 加密 | 2026-09-30 | 2026-10-01 至 2026-10-22 UTC | 176 个 ZIP + 176 个校验文件，共 352 个资源 | 未启动 |
| 美股 | 2026-10-20 | 从 2026-10-14 开始的五交易日重叠复核，至 2026-10-22 | 11 次资格确认 + 11 次历史调用，共 22 次 | 未启动 |

这些带日期的清单保留在私有数据目录。准备好清单不代表供应商已经提供数据，也不保证请求能完成。实际启动前应再次核对准确日期；新增日期需要明确审查新清单，不能静默扩大现有请求范围。

## 加密逐日扩展

数据源仍为 Binance Vision 现货 `1d` K 线，沿用 BTCUSDT、ETHUSDT、BNBUSDT、SOLUSDT、XRPUSDT、ADAUSDT、DOGEUSDT、LINKUSDT 八币种池。逐日 ZIP 使用独立身份和解析器，不改变原来的月度归档。按照[官方说明](https://github.com/binance/binance-public-data)，逐日文件次日提供，2025 年起现货时间戳为微秒，之前为毫秒。

扩展 spec 只有四个字段：

```json
{
  "schema": "competition.binance_daily_extension.v1",
  "start": "2026-10-01",
  "end": "2026-10-22",
  "parent_sha256": "<sha256-of-the-verified-parent-manifest>"
}
```

日期必须紧接每个币种父数据的末尾，连续扩展。每份计划最多包含 31 个已完成 UTC 日期、248 个 ZIP 和 248 个校验文件。硬上限为含失败在内的 600 次尝试、传输 128 MiB、累计解压 256 MiB、单 ZIP 解压 4 MiB，以及包含核验和收尾的累计 600 秒。剩余尝试额度不代表可以增加资源。本实现每个资源只尝试一次，遇到错误或消耗不明就停止，不自动重试。

工具只接受准确的官方 HTTPS 路径，拒绝跳转、URL 中的凭据、错误校验值、意外 ZIP 成员、未支持币种、错误时间戳、多根日线及无效 OHLCV。父数据保留原来的 partial/acquired 状态，扩展切片完整不代表更早的不完整历史也自动完整。

先解析配置中的根目录、使用已安装的根解释器，再将尖括号占位替换为仓库外绝对路径：

```powershell
python -m competition_tools.team daily-extension prepare --config <team.toml> --spec <extension.json> --base-manifest <parent-manifest.json> --output-root <new-plan-directory>
python -m competition_tools.team daily-extension inspect --config <team.toml> --manifest <new-dataset/manifest.json>
```

这两条命令离线运行。下面这条会发起真实请求，只能在准确的冻结请求清单获批后使用：

```powershell
python -m competition_tools.team daily-extension acquire --config <team.toml> --plan <plan-directory/plan.json> --output-root <new-dataset-directory>
```

一次性预算记录放在项目所属数据目录，不随输出位置改变。换目标目录、配置目标位置或 frozen-at 时间都不能重置它。失败或消耗不明时，需要明确调查并获得新的授权，不能自动再试。原始 ZIP、校验文件、合并后的标准化文件、收据和 manifest 都留在仓库之外。新的 `competition.binance_daily_manifest.v1` 由本扩展命令和观察准备读取，不会自动被原来的历史研究加载器接受。

## 美股刷新清单

```powershell
python -m competition_tools.team observation-prepare us-refresh --config <team.toml> --manifest <complete-US-parent-manifest.json> --output-root <new-inventory-directory>
```

命令生成 `us-refresh-plan.json` 清单，不是可以直接用于下载的 acquisition spec。它保留父数据的起点和身份，选择已经完成的 XNYS 交易日，并包含既有的五交易日重叠复核。11 个标的包含 SPY，上限为 22 次计数调用、最多 11 次历史请求、含父数据在内保留 10 MiB、累计 300 秒，每个请求尝试一次。仅限速间隔就约需 210 秒，因此不保证能完成。价格修订若需要超出预算的重建，应停止并准备新的有界清单。

真实获取仍需启动审查后使用现有的明确配置日线刷新入口，另有 v2 acquisition spec 和私有 connection-file 引用。不要把新清单 JSON 直接当作那个 spec。准备阶段不会创建券商连接，也不启动自动登录或使用 `--ensure-gateway`。

## 分市场预热与协议交接

```powershell
python -m competition_tools.team observation-prepare market --config <team.toml> --manifest <verified-market-manifest.json> --parent-registry <old-registry-directory> --output-root <new-preparation-directory>
```

结果要求 252 期共同且已完成的数据、完整市场日历、向后延伸的预热期及新鲜的已核验数据。它记录采集时间、输入哈希、下一个可观察市场日期、原有候选和费用，以及零条观察。旧数据、缺日期或修订后的输入保持阻塞。补齐的历史数据用于预热，不能当作前瞻观察。

某个市场通过这些检查后，显式冻结已审阅的准备记录：

```powershell
python -m competition_tools.team observation-prepare freeze-market --config <team.toml> --preparation <preparation.json> --parent-registry <old-registry-directory> --output-root <new-registry-directory>
```

冻结时再次检查时效，并要求源码已提交。六个候选和 observation v1 字段保持不变。为支持两个市场独立开始且不修改 v1，每个市场可以使用独立协议，替换本市场预热，保留另一市场的父预热。外部 `relationship.json` 记录父协议、新协议、活跃市场和准备产物摘要。cutoff 检查会阻止把另一市场中间已有的旧数据尾段计入观察。需要分别追踪各市场的协议 ID，不能默认它们共用同一个登记目录。

`known_cutoff` 表示已经检查过的价格日期边界，不替代实际采集、准备和冻结时间。冻结仍增加零条观察，也不赋予数据时点可信状态。真实导入仍需通过[现有观察登记](observation-registry.zh-CN.md)注册经过人工核对的准确证据，不能倒填可用时间，或把已经缓存的旧数据称为尚未见过的数据。
