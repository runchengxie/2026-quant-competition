# 团队 IBKR 模拟账户开通指南

> 来源：[`ibkr-simulated-account-guide.pdf`](../sources/ibkr-simulated-account-guide.pdf)
> 说明：以下内容根据 PDF 文本和页面顺序整理；截图页面仍需结合原 PDF 查看。

## 一、选择开通路径

| 路径 | 特点 | 适用情况 |
|---|---|---|
| 完整实盘账户 → 模拟账户 | 权限更可控，交易权限与实盘账户配置同步 | 需要自定义股票、期权、指数期权、期货等权限 |
| IBKR Free Trial | 开通更快，但权限由系统预设且不能自行新增 | 只需快速测试平台或策略 |

选择建议：交易品种明确且需要跨市场权限，优先选择第一种；只需验证平台和策略，可考虑 Free Trial。

## 二、路径一：完整实盘账户转模拟账户

1. 开立 IBKR 实盘账户，基础币种建议选择美元。
2. 申请所需交易权限，例如股票、期权、指数期权和期货。
3. 在账户设置中开通模拟交易账户。
4. 模拟账户初始权益为 100 万美元，权限以实盘账户配置为准。
5. 使用模拟交易用户名和密码登录 Paper 账户。

操作位置：进入 IBKR 实盘账号，点击右上角头像 → “设置” → “模拟交易账户”，然后设置模拟交易用户名和密码。

登录入口：[IBKR 登录](https://www.interactivebrokers.com.hk/sso/Login)。进入后确认右上角账户类型为 `Paper`。

> 如果团队此前已经开通过模拟账户，但需要重新获得 100 万美元初始模拟资金，可以考虑另行开立 IBKR 账户并创建新的模拟账户。重新开户前应确认基础币种和账户资格。

## 三、路径二：IBKR Free Trial

注册入口：[IBKR Free Trial](https://ndcdyn.interactivebrokers.com/Universal/Application?ft=T&spltst=www&trk=PAPER-COURSE)。

Free Trial 无需完成完整实盘开户流程，但交易权限由系统预设，开通后不能自行新增。注册地区会影响初始资金币种和可用权限：

| 注册地区 | 初始模拟资金 | 权限或注意事项 | 原指引建议 |
|---|---:|---|---|
| 美国 | 100 万美元 | 受美国政策限制，不可交易非美股票期权及非美现金指数期权 | 不适合港股期权等产品 |
| 新加坡 | 100 万新加坡元 | 受新加坡政策和地域监管限制 | 推荐 |
| 香港 | 100 万港币 | 模拟资金量相对较少 | 按本地需求选择 |

> 开通前先测试目标交易品种是否具备权限。实际资金币种与权限以注册页面和账户显示为准。

## 四、交易软件

- **TWS**：图形化交易端，适合手动交易、图表分析、订单和组合管理。 [下载 TWS](https://www.interactivebrokers.com.hk/en/trading/download-tws.php)
- **IB Gateway**：程序化交易端，适合 API 和自动化策略，界面更轻量。 [下载 IB Gateway](https://www.interactivebrokers.com.hk/en/trading/ibgateway-latest.php)

使用前检查：确认界面显示 `Paper` / `Simulated`，复核目标品种、市场和交易权限，并按稳定性需求选择 `Latest` 或 `Stable` 版本。
