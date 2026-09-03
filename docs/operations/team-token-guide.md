# 香港资管通团队 Token 获取指引

> 来源：[`team-token-guide.pdf`](../sources/team-token-guide.pdf)
> 说明：以下内容根据 PDF 文本和页面顺序整理；截图页面仍需结合原 PDF 查看。

## 一、Token 是什么

IBKR Flex Token 是授权第三方系统读取 IBKR 账户报表数据的安全凭证，可用于同步账户资产、持仓、交易记录、资金流水和账户报表。

Flex Token 仅用于读取报表数据，不具备交易权限，不会直接产生下单、转账或提款权限。

## 二、获取前准备

- 已完成 IBKR 账户开户。
- 可以正常登录 IBKR Client Portal。
- 使用账户主账号登录；部分关联账户可能需要 Master Account 权限。

## 三、获取 Token

1. 登录 [IBKR 官网](https://www.interactivebrokers.com.hk/cn/home.php)。
2. 进入报表设置。
3. 配置“自主网络服务”。
4. 点击“生成新的验证口令”。
5. 到期倒计时选择 `1 Year`。
6. 点击“创建”查看 Token。

> 注意：新创建的 Token 会覆盖旧 Token。

第 4、6—10 页含有操作截图或版式信息，具体按钮位置以 [原始 PDF](../sources/team-token-guide.pdf) 为准。

## 四、获取 Query ID

1. 进入“创建活动自主查询”。
2. 填写查询名称；查询名称仅支持英文。
3. 设置查询区段；原指引建议全选。
4. 发送配置的时段选择过去 365 个日历日。
5. 点击“继续”，查看活动自助查询。
6. 点击“创建”，获取 Query ID。

第 12—17 页主要为操作截图，建议对照 [原始 PDF](../sources/team-token-guide.pdf) 操作。

## 五、提交团队系统

登录 [香港资管通团队端](https://team.fundconnecthk.com/login)，提交 IBKR Token 和 Query ID。

## 六、首次成交要求

Token 和 Query ID 绑定后，还需要在该账户中成功成交至少一笔实际买卖订单。仅提交未成交的委托不算完成交易。

如果账户没有已完成的成交记录，系统可以验证 IBKR 凭据，但最新 Flex 报表中可能没有交易数据，后台会提示。成交后，系统会在后续自动同步中更新策略业绩，通常无需重复绑定 Token。

## 七、安全提醒

- 不要把 Token、Query ID 或账户密码提交到公开代码仓库。
- 仅向确认过的团队系统提交凭据。
- Token 虽然没有交易权限，仍属于账户敏感授权信息，应按密钥管理。
