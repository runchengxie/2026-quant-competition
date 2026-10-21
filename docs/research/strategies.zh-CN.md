# 策略详解

这些策略是固定的日频研究对照，不是已获准执行的策略。解读结果前，请先阅读[研究方法](real-data-study.zh-CN.md)和[数据契约](datasets.zh-CN.md)。首页将各策略链接到本指南，并且只在相同市场、费用及计分窗口下进行对比。

## 共同假设与证据范围

2026-10-21 冻结研究包含 318 个已完成的策略、窗口与费用组合。每个窗口先预热 252 期，再对股票计分 63 个交易期，对加密货币计分 90 个日频周期。各窗口独立从现金开始。资产池是当前选定的固定名单，不是历史时点的指数成分。美股池有十个标的，港股十个，加密货币八个。数据身份、覆盖范围、复权和选择偏差的限制见研究说明，不能从策略名称推断。

信号使用前一日收盘信息，持仓获得下一期收盘到收盘的变化。模型仅做多、使用现金。初始建仓扣费，期末不强制平仓。股票按每年 252 期、加密货币按 365 期年化。除预设费用外，模型未计入股息、税费、融资、离散手数、容量和独立验证的执行滑点。这里的策略不连接券商，也不能证明符合比赛资格。

固定单边费用为美股 20/40 bps、港股 30/60 bps、加密货币 0/10/25 bps。零费用是对照。首页默认采用非零的 20/30/10 bps。费用摘要在每档预设费用都覆盖的相同窗口上比较，也保留零费用对照。缺少基准值的窗口不计入正超额占比的分母，零超额不算胜出。这些是描述统计，不是显著性检验，也不是新增样本外证据。

<a id="buy-hold"></a>
## 买入持有 `buy_hold`

股票研究按标识排序选取最多十个标的，初始等权配置，此后权重随价格漂移，不会每天重新等权。主要风险包括市场下跌、权重漂移后的集中度，以及当前选定资产池的偏差。窗口净收益为正，本身不能证明跑赢基准。

实现见[股票研究](../../research/equity-lab/src/equity_lab/study/run.py)。与 `equal_weight` 比较时，应固定市场、窗口和费用，再观察再平衡的影响。

<a id="equal-weight"></a>
## 等权组合 `equal_weight`

股票版本每天决策时，对按标识排序的最多十个标的重新等权。加密货币版本则对固定现货池初始等权，此后持有并允许权重漂移。同一标识在这两个独立实验中的配置规则不同。加密货币 `equal_weight` 也是指定基准，因此相对自身的超额收益为零。

股票再平衡可能增加换手和费用拖累。两种实现都不能防止普遍的市场下跌，应在同一市场内比较。实现见[股票](../../research/equity-lab/src/equity_lab/study/run.py)和[加密货币日频研究](../../research/crypto-mm/src/crypto_mm/daily/study.py)。

<a id="momentum-20d"></a>
## 二十期正动量 `momentum_20d`

股票模型筛选截至前一日收盘、过去二十个交易期收益严格为正的标的，按标识排序取最多十个并等权配置，无符合标的时持有现金。这是正负过滤，不是横截面动量排名，目标仓位可能每天变化。

信号在零附近波动时可能反复切换并增加费用。过滤器也可能滞后于突然反转，错过下跌后的反弹。应结合换手、费用敏感性及最差窗口查看中位收益。实现见[信号](../../research/equity-lab/src/equity_lab/signals/momentum.py)和[配置](../../research/equity-lab/src/equity_lab/study/run.py)。

<a id="sma-cross"></a>
## 均线过滤 `sma_cross`

股票模型按前一日收盘，筛选二十期均线严格高于六十期均线的标的，按标识排序取最多十个并等权配置，无符合标的时持有现金。这是日频状态过滤，不是日内交叉时点的成交模拟。

横盘可能引发反复调仓，滞后信号也可能错过反弹初期。应在两档股票费用下，与买入持有和等权基线比较。实现见[信号](../../research/equity-lab/src/equity_lab/signals/sma.py)和[配置](../../research/equity-lab/src/equity_lab/study/run.py)。

<a id="benchmark-buy-hold"></a>
## 股票基准 `benchmark_buy_hold`

它持有预先指定的单标的股票参考资产，是比较基线，不是推荐组合。窗口收益继续公开，逐日归一化曲线因与价格关联而有意不公开。因此对比表可以显示基准结果，但图表中没有对应曲线。

该基准并不重建选定股票池，其相对自身的超额收益为零。基准和资产池定义见[研究证据](real-data-study.zh-CN.md)。

<a id="momentum-63d"></a>
## 加密货币六十三期正动量 `momentum_63d`

日频现货模型筛选前一日收盘高于六十三个日频周期前收盘的资产并等权配置，无符合资产时持有现金。这是正收益过滤，不做排名、做空或衍生品交易。

阈值附近的频繁切换可能增加费用，波动和急剧反转也可能主导结果。应查看同窗口对比及匹配窗口的费用摘要。实现见[加密货币日频研究](../../research/crypto-mm/src/crypto_mm/daily/study.py)。

<a id="trend-200d"></a>
## 加密货币二百期趋势过滤 `trend_200d`

日频现货模型筛选前一日收盘严格高于过去二百期均价的资产并等权配置，无符合资产时持有现金。目前不按波动率缩放仓位，也没有调仓缓冲。这些是可能的后续实验，不是已交付能力。

过滤器可能滞后于反转，也可能在均线附近反复进出。较低仓位不保证较小回撤，应查看最差窗口和较高费用下的结果，不能只选一条有利曲线。实现见[加密货币日频研究](../../research/crypto-mm/src/crypto_mm/daily/study.py)。

## 复现与检查

先按[队员快速开始](../operations/team-quickstart.zh-CN.md)准备可编辑安装的源码和锁定的离线环境。真实数据重放需要获得授权的不可变数据 manifest、仓库外的团队配置及 v2 研究规格。根命令运行各 manifest 所支持的固定策略矩阵，没有单策略参数。新的源码提交或不同输入会形成新的研究身份，不会得到原始 artifact 哈希的精确复刻。

```sh
python -m competition_tools.team evaluate --help
python -m competition_tools.team evaluate --config /external/team.toml --spec /external/study-spec.json --output-root /external/new-study
python -m competition_tools.evaluation.study_publication --aggregate /external/new-study/run/study-results.json --output /external/new-public-study.json
```

以上路径应位于源码仓库外，输出使用新路径。公开仓库不分发授权原始数据。可以另用合成数据交付检查验证 CLI 契约，但不能将其视为真实数据表现。

```sh
python -m competition_tools.check_study_delivery --config /external/team.toml --output-root /external/new-synthetic-contract
```

[打开业绩看板](https://runchengxie.github.io/2026-quant-competition/zh-CN/#performance)，在相同费用及准确窗口下比较策略，再通过匹配窗口的费用摘要观察费用依赖。独立窗口不会拼成连续复利账户，本次展示更新不重跑或提升任何策略的状态。
