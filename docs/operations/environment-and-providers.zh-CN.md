# 私人配置与数据服务

[English](environment-and-providers.md) · [文档目录](../README.zh-CN.md)

离线演示不需要下面的密钥。准备接入某个数据服务或配置执行程序时，再阅读对应部分。

## 私人配置怎么放

参考项目根目录 `.env.example` 中的配置项，在源码之外保存自己的 `.env`。模板里只有公开的占位值。使用一份 `.env` 即可，不另外创建 `.env.local`。

执行程序读取进程环境变量，不会自动加载 dotenv 文件。启动前，需要把所需值加载进进程环境。密钥、账户信息、订单日志、服务商原始响应和运行产物都不能提交到 Git。

## AIVIX 与 Cryptoracle

在私人 `.env` 中设置 `CRYPTORACLE_API_KEY`，需要备用密钥时再设置 `CRYPTORACLE_API_KEY_BACKUP`，然后加载到进程环境。[客户端](../../src/adapters/cryptoracle/client.py)读取这两个值及 `CRYPTORACLE_API_BASE_URL`。

基础地址使用 `https://service.cryptoracle.network/openapi`。旧配置如果只写官方服务主机名，客户端会补上 `/openapi`。自定义地址保留其原路径。

```python
from adapters.cryptoracle import CryptoracleClient

client = CryptoracleClient.from_environment(timeout=15.0)
# 这个只读币种查询已在 2026-10-12 验证。
data = client.post("/v2.1/coin/list", {"timeType": "1h"})
```

每次先尝试主密钥。遇到 HTTP 401、403、429，或表示密钥无效的 JSON 业务码 `202` 时，用备用密钥对同一请求再试一次。空值、示例占位值和重复密钥会跳过，也可以只配置备用密钥。其他 HTTP 错误、网络错误和无效 JSON 都不会触发密钥切换。

非 200 的整数业务码会抛出 `CryptoracleAPIError`。通过 `status_code` 和 `business_code` 区分 HTTP 状态与业务错误，服务商可能在 HTTP 200 响应中返回业务错误。异常文字和配置对象的显示会省略密钥及服务商错误正文。客户端只使用 HTTPS，并拒绝重定向，避免把密钥转发到其他主机。

客户端不会自动加载 `.env`，也不会自动选择指标接口。[官方 API 概览](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1)说明了 `/openapi` 根路径，[认证文档](https://cryptoracle.gitbook.io/cryptoracle-docs/cryptoracle-open-api-v2.1/authentication)说明了 `X-API-KEY` 请求头。[2026-10-12 验证记录](cryptoracle-validation-2026-10-12.md)记录了通过已配置代理及直连进行只读币种查询、无效主密钥切换的结果。指标、历史数据权限和覆盖范围尚未验证。

## QuantZone

QuantZone 是可选来源。有权限时，在私人 `.env` 中同时填写 `QUANTZONE_ACCESS_KEY` 和 `QUANTZONE_SECRET_KEY`。SDK 分别使用 `access_key` 和 `sign_secret`，只填一个 `QUANTZONE_API_KEY` 不够。

`QUANTZONE_API_BASE_URL` 记录候选服务地址。项目尚未实现 QuantZone 适配器或认证流程，填写配置不能证明账户权限或因子覆盖范围。双密钥和 SDK 初始化方法见[官方文档](https://www.quantzone.tech/docs)，服务地址以自己控制台显示的为准。

## 历史验证和记账实现

数据服务及汇率的只读检查见[2026-10-02 验证记录](provider-fx-validation-2026-10-02.md)。[2026-10-03 账本交付记录](usd-ledger-delivery-2026-10-03.md)描述的是原 quant-platform 实现。当前比赛项目已拥有独立账本，对照实验和下一开盘回放都不再安装该框架。

[独立记账对照](../research/accounting-comparison.zh-CN.md)保留原策略决策，用合成 HK/US 输入比较权重模型和现金、股数模型。真实日线输入仍需要可核验的时钟、每手数量和汇率信息，已有公开历史快照保持原样。
