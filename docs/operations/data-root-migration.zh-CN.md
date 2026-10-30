# 项目数据目录

[English](data-root-migration.md) · [团队快速开始](team-quickstart.zh-CN.md)

项目规范目录为 `DATA_ROOT/global-market-research`，`DATA_ROOT` 继续表示整个工作区的数据根目录。已有安装若只有 `DATA_ROOT/2026-quant-competition`，在完成有记录的迁移前仍使用旧目录。全新安装默认采用新名称。

两个目录同时存在时，默认选择会以 `AMBIGUOUS_PROJECT_DATA_ROOT` 失败。可以通过 `GLOBAL_MARKET_RESEARCH_DATA_ROOT`、工作区 TOML 可选的 `project_data_root`，或团队 v2 配置明确选择同一数据根下的项目目录。不要合并两个目录或用 junction 绕过错误。输入及 Gateway 的重解析路径保护继续生效。

团队 v1 仍包含 `schema_version`、`data_root`、`environment_root`，其中 `data_root` 表示工作区根目录。团队 v2 增加 `project_data_root`。可用以下命令创建明确配置。

```sh
python -m competition_tools.team init --config /absolute/team.toml --data-root /absolute/data --project-data-root /absolute/data/global-market-research
```

Windows 使用带盘符的路径。初始化只创建新配置，不覆盖旧文件。根编排将选定目录明确传给独立安装的研究子进程。三个标准库路径客户端共享经测试的文件和环境变量契约，不导入相邻包，CI 检查它们的源码一致性。

迁移前要盘点普通文件哈希、链接、可修改的路径配置、计划任务 action、运行环境和下游引用。无法确认必要写入方或消费者时暂停切换。经过审查的本机切换只改位置字段，不启动任务、连接券商、更改触发器或账户，也不授予新的下载许可。

历史产物字节、`competition.*` schema、提供方身份和研究协议保留旧名称。封闭的 `.storage-migration.json` 凭证绑定同一数据根下的精确新旧项目目录、`phase="completed"` 以及封存盘点的 SHA256。已有预约中的已知位置字段可以映射到保留的相对位置，无需改写凭证。路径映射不认证数据所有者，也不升级研究。

采集授权和研究预约写入在同一个工作区级锁下检查新旧两处位置。已有或消耗不确定的标记不会因选目录、换输出或修改代码而恢复预算。中断留下的共享锁必须独立核对，不能自动当作新预算。

历史环境和故意无效的测试链接继续作为证据保留。迁移后的环境经过核验或重建后才可用于运行。路径客户端变化会改变源码摘要，因此旧协议保留自己的源码快照，新研究另行冻结源码、协议及预约。详见[产物保留](artifact-retention.zh-CN.md)。
