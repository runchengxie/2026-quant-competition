param(
    [Parameter(Mandatory=$true)][string]$OutputRoot,
    [ValidateRange(1,20)][int]$TimeoutSeconds = 10,
    [ValidateSet('success','exit7','sleep','start-failure')][string]$Mode = 'success'
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputRoot) { throw 'SYNTHETIC_OUTPUT_EXISTS' }
$null = New-Item -ItemType Directory -Path $OutputRoot
$clock = [Diagnostics.Stopwatch]::StartNew()
$startedAt = [DateTimeOffset]::UtcNow
$info = [Diagnostics.ProcessStartInfo]::new()
$info.FileName = if ($Mode -eq 'start-failure') { 'competition-synthetic-nonexistent-process' } else { (Get-Process -Id $PID).Path }
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$code = switch ($Mode) {
    'exit7' { '[Console]::Out.WriteLine("synthetic-sentinel"); exit 7' }
    'sleep' { 'Start-Sleep -Seconds 30; exit 0' }
    default { '[Console]::Out.WriteLine("synthetic-sentinel"); exit 0' }
}
foreach ($arg in @('-NoLogo','-NoProfile','-NonInteractive','-Command',$code)) { $info.ArgumentList.Add($arg) }
$process = [Diagnostics.Process]::new()
$process.StartInfo = $info
$started = $false
$expired = $false
$exitCode = $null
$exitedAt = $null
$launchSeconds = 0.0
$redirectSeconds = 0.0
try {
    $started = $process.Start()
    $launchSeconds = $clock.Elapsed.TotalSeconds
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        $expired = $true
        $process.Kill($true)
        $null = $process.WaitForExit(1000)
    } else {
        $exitCode = $process.ExitCode
        $exitedAt = [DateTimeOffset]::UtcNow.ToString('o')
    }
    $redirectStart = $clock.Elapsed.TotalSeconds
    [IO.File]::WriteAllText((Join-Path $OutputRoot 'stdout.txt'),$stdout.GetAwaiter().GetResult())
    [IO.File]::WriteAllText((Join-Path $OutputRoot 'stderr.txt'),$stderr.GetAwaiter().GetResult())
    $redirectSeconds = $clock.Elapsed.TotalSeconds - $redirectStart
} catch {
    if ($started) { throw }
} finally {
    $process.Dispose()
}
$value = @{
    schema='competition.synthetic_process_timing.v1'
    started=$started
    exit_code=$exitCode
    observation_expired=$expired
    started_at=$startedAt.ToString('o')
    exited_at=$exitedAt
    observed_at=[DateTimeOffset]::UtcNow.ToString('o')
    launch_seconds=$launchSeconds
    redirection_seconds=$redirectSeconds
    wall_seconds=$clock.Elapsed.TotalSeconds
    synthetic=$true
}
$json = $value | ConvertTo-Json -Compress
[IO.File]::WriteAllText((Join-Path $OutputRoot 'timing.json'),$json)
$json
