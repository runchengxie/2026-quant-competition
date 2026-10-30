# 低换手浅层树增量研究

[English](low-turnover-tree-study.md)

这个独立启用的流程在已保留的股票持有期研究上增加浅层直方图梯度提升树和20交易日动量基线。根工具先核验完整父运行记录，再独立重算父报告的持仓证据，核验通过后才复用168个已保存账户。新增请求最多96个账户、12次拟合启动。本次实现没有运行真实研究。

2026-05-28至2026-07-24、2026-07-27至2026-09-21两个窗口都已被查看，结果仍属探索性历史比较。六项科学证据要求全部保持未通过状态。本流程不能证明总回报准确性、完整的历史股票准入、数据可用时点、流动性、容量或可交易性，也不会生成交易目标。相关背景见[已保留的比较](strategy-comparison.zh-CN.md)和[已批准设计](../superpowers/specs/2026-10-31-low-turnover-tree-study-design.md)。

## 固定的比较范围

每个持有期和窗口组合沿用父研究的月度候选池、六个特征、60交易日验证切分、严格标签清除、原始价格标签和实际持仓单位现金账本。内部训练之前至少需要80个日历交易日。缺失值填补仅在训练数据上拟合。深度2和3调用现有 `fit_incremental` 实现，固定100轮、学习率0.05、最多七个叶节点、每叶至少100条样本、L2为1.0、63个分箱、种子42，并关闭提前停止。选择依次依据平均每日RankIC、MSE和预先声明顺序，要求每天至少30个有效候选、至少20个有效验证日期。仅选中的候选可在外部训练样本上再拟合一次。

动量定义为父研究收盘决策代理时点的 `close(t) / close(t-20) - 1`。21个精确日历价格点必须全部存在、价格有效、候选身份和代码不变，且没有已知公司行动边界。预测候选不按未来标签筛选。历史不足会明确记为不可用，也可能使该账户停止。这个价格代理本身不能证明历史数据何时实际可得。

固定Top50、缓冲0/20、持有期5/20、单边模型费用0/20/40基点和延迟0/1。每个窗口独立初始化账户，不拼接净值。父绑定缺失会停止流程，不会重新拟合旧试验。父文件和已经消耗的预约记录保持原样。

私有协议预先声明432个逐格收益比较，将Ridge、Elastic Net和浅层树与等权、反转、动量按窗口、持有期、费用、延迟、缓冲配对。等权始终使用其唯一的缓冲0账户。另有24个相对反转和动量的每日RankIC配对汇总，只采用候选数量相同且双方RankIC均有效的日期。等权分数恒定，其RankIC不可用。缺失配对保留原因。这些条件共享历史和重叠标签，不能视为独立观测。不确定性固定为不可用，原因是 `uncertainty_tooling_not_validated`，查看结果后不会追加置信区间或显著性结论。

## 准备、预约、运行与核验

先完成或明确推迟[数据根目录迁移](../operations/data-root-migration.md)，并取得迁移负责人对真实运行的明确授权。迁移完成后使用选定的新项目根目录；迁移进行中不要创建该目录下的输出。协议绑定完整父记录、准备输入的字节哈希、父导出、当前根与叶源码哈希、两份锁文件、固定规则和新的所有者输出路径。

根环境与叶环境分别从已评审源码安装。根工具继续仅依赖标准库；叶环境沿用锁定的 `predictive` 附加依赖。从显式工作区配置或环境中解析 `DATA_ROOT`。下面的PowerShell示例假设已经提供解析后的 `$dataRoot`、根解释器 `$rootPython` 和叶解释器 `$leafPython`。

```powershell
$source = (git rev-parse --show-toplevel).Trim()
$project = & $rootPython -c "import sys; from competition_tools.project_storage import project_root; print(project_root(sys.argv[1]))" $dataRoot
$parent = Join-Path $project 'task-results/evidence-followup-20261025/historical-run'
$owner = Join-Path $project 'research/equity-lab'
$output = Join-Path $owner 'tree-study/20261031-v1'
$prepared = & $rootPython -m competition_tools.evaluation.tree_study prepare `
  --owner $owner --parent-run $parent --parent-equity (Join-Path $parent 'equity') `
  --input (Join-Path $parent 'inputs/daily.parquet') --output $output --source-root $source |
  ConvertFrom-Json
& $rootPython -m competition_tools.evaluation.tree_study run `
  --protocol $prepared.protocol --reservation $prepared.reservation --python $leafPython
& $rootPython -m competition_tools.evaluation.tree_study verify --protocol $prepared.protocol
```

准备阶段在预约前完成父记录核验，冻结 `competition.low_turnover_tree_protocol.v1`，并创建按协议和输入哈希唯一标识的 `competition.research_reservation.v1` 预约。改变源码、输出或时间戳都不能恢复预算。若预约之后准备失败，该预约仍然保留，需要调查，不能删除后重试。

选择器在迁移后使用新根目录，在迁移被明确推迟且仅旧目录存在时沿用旧根目录。后续有记录的迁移会解析已知位置字段，不会改写不可变协议或父记录。

新叶入口为 `python -m equity_lab.predictive.tree_study_cli --input <prepared> --output <new-output> --reservation <receipt>`。应通过根工具的 `run` 启动，确保拟合前再次独立核验父证据。工作开始前独占领取启动标记。初始预约快照、逐持有期领取记录和权威尝试账本都与所有者预约存放在一起，不依赖可变的结果目录。隐藏子进程必须匹配原始身份、所有者和输出。每个持有期使用单独子进程，硬上限1200秒、最多六次拟合启动、两个计算线程，并保留独立报告。失败和中断的启动均消耗预算，没有自动重试或恢复功能。可导入运行函数的默认真实估计器也必须提供经过核验的持有期领取记录。显式注入拟合器仅供合成测试使用，这些约束不是任意Python或scikit-learn代码的安全沙箱。

新叶报告版本为 `equity.low_turnover_tree.v1`。预测CSV保留完整候选和日期网格，包括未来标签缺失的行。验证预测CSV供根工具独立重算候选RankIC、MSE和所选深度。根核验检查完整预测网格、动量因果性、选股计划、全部费前费后现金路径、覆盖率及配对汇总。停止账户保留原因、日期和部分历史。持有期失败时保留启动标记、部分报告、超时记录及不可用单元，部分运行不能通过完整输出核验。

协议、预约、尝试、源码和锁文件身份、父记录、报告及核验证据都应纳入私有保留。迁移期间的合成测试使用单独分配的演练目录，不能据此启动真实拟合。本流程没有发布命令。原始价格、逐候选预测和私有路径继续保密。未来公开汇总需要单独的封闭模式评审；真正未暴露的评估需要另行冻结未来协议并提供数据可用时点证据。
