# Synthetic process timing

Use this synthetic check to see where a child process spends time or exceeds its deadline. Its results cannot establish real Gateway startup or login performance.

The diagnostic separates process launch, redirected-stream collection, child exit, and the outer PowerShell deadline. It starts only a fixed synthetic PowerShell child. It does not inspect or start Gateway, Java, accounts, or broker sessions, and it changes no production timeout or lease rule.

Run from the repository root with an installed root environment and an absolute external destination that does not exist:

```powershell
python -m competition_tools.check_native_process_delivery --output-root D:/data/2026-quant-competition/task-results/process-check --timeout-seconds 10
```

`diagnostic.json` contains sanitized timing and status fields. The nested `native/` directory retains synthetic stdout/stderr and the wrapper's timing record locally. Do not publish raw process streams. `completed` means the synthetic child exited successfully. Other statuses distinguish `start_failed`, `child_failed`, `observation_timeout`, and `outer_timeout`.

The wrapper measures launch and redirection time inside PowerShell. The Python parent enforces a separate 20-second outer deadline and kills its synthetic process tree on timeout. `--timeout-seconds` accepts integers from 1 to 20. At 20 seconds, startup overhead can cause the outer deadline to win. A missing PowerShell installation is a start failure. These measurements do not establish real Gateway startup or login performance.
