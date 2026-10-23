# 合成进程计时

这个工具分别记录进程启动、重定向输出收集、子进程退出和外层 PowerShell 超时。它只启动固定的合成 PowerShell 子进程，不检查或启动 Gateway、Java、账户或券商连接，也不修改生产超时和运行锁规则。

在仓库根目录使用已安装的根环境运行，输出路径必须是仓库外尚不存在的绝对路径：

```powershell
python -m competition_tools.check_native_process_delivery --output-root D:/data/2026-quant-competition/task-results/process-check --timeout-seconds 10
```

`diagnostic.json` 保存脱敏后的计时和状态。其下的 `native/` 目录在本地保留合成标准输出、错误输出和计时记录。不要公开原始进程输出。`completed` 表示合成子进程成功退出，其余状态分别为 `start_failed`、`child_failed`、`observation_timeout` 和 `outer_timeout`。

启动和输出收集时间从 PowerShell 内部开始计量。Python 父进程另设 20 秒外层期限，超时后终止本次合成进程树。`--timeout-seconds` 接受 1 到 20 的整数，设为 20 时，启动开销可能让外层期限先到。未安装 PowerShell 时记为启动失败。这些结果不能代表真实 Gateway 的启动或登录速度。
