Set-StrictMode -Version Latest

function Invoke-PaperApiProbe {
    param([string]$PythonPath, [string[]]$Arguments, [double]$BudgetSeconds)
    $process=[Diagnostics.Process]::new()
    try {
        $process.StartInfo.FileName=$PythonPath
        $process.StartInfo.UseShellExecute=$false
        $process.StartInfo.CreateNoWindow=$true
        $process.StartInfo.RedirectStandardOutput=$true
        $process.StartInfo.RedirectStandardError=$true
        foreach($argument in $Arguments){$process.StartInfo.ArgumentList.Add($argument)}
        $clock=[Diagnostics.Stopwatch]::StartNew()
        if(-not $process.Start()){throw 'Probe failed'}
        $stdout=$process.StandardOutput.ReadToEndAsync()
        $stderr=$process.StandardError.ReadToEndAsync()
        $remaining=[int][Math]::Max(0,($BudgetSeconds*1000-$clock.Elapsed.TotalMilliseconds))
        if(-not $process.WaitForExit($remaining) -or $clock.Elapsed.TotalSeconds -ge $BudgetSeconds){
            # This process is the read-only probe, never the Gateway launcher.
            if(-not $process.HasExited){$process.Kill($false)}
            return @{state='blocked';code='API_PROBE_TIMEOUT'}
        }
        if($process.ExitCode -notin @(0,2,3)){throw 'Probe failed'}
        return ($stdout.GetAwaiter().GetResult() | ConvertFrom-Json -AsHashtable)
    } catch {
        return @{state='blocked';code='API_PROBE_FAILED'}
    } finally {$process.Dispose()}
}

function Invoke-PaperGateway {
    [CmdletBinding()]
    param(
        [ValidateSet('check','dry-run','status','prepare','start','ensure')][string]$Action,
        [string]$PythonPath, [string]$ConfigPath, [string]$WorkspacePath,
        [string]$ApiConnectionPath,
        [scriptblock]$ApiProbe,
        [scriptblock]$SpecProbe,
        [scriptblock]$InteractiveProbe = { [Environment]::UserInteractive -and (Get-Process -Id $PID).SessionId -gt 0 }
    )
    $lease=$null
    $leasePath=$null
    $releaseLease=$false
    try {
        if ($Action -eq 'ensure') {
            if ($null -eq $ApiProbe) {
                $ApiProbe={param($seconds,$budgetSeconds)
                    # Include bounded interpreter/SDK startup separately from connect.
                    Invoke-PaperApiProbe -PythonPath $PythonPath -Arguments @('-m','competition_tools.team.gateway','--connection-file',$ApiConnectionPath,'--timeout',"$seconds") -BudgetSeconds $budgetSeconds
                }
            }
            $api=& $ApiProbe 2 10
            if($api.state -eq 'ready'){return @{state='api_ready';api='connected';account_identity='not_checked';historical_data='not_checked';exit_code=0}}
            if($api.state -ne 'not_ready'){return @{state='blocked';code=$api.code;exit_code=2}}
        }
        if ($Action -in @('start','ensure') -and -not (& $InteractiveProbe)) {
            return @{state='blocked';code='INTERACTIVE_DESKTOP_REQUIRED';exit_code=2}
        }
        $query = if ($Action -in @('start','ensure')) {'launch-spec'} else {$Action}
        if ($null -ne $SpecProbe) {
            # Unit-level dependency injection; the public entry script never accepts this.
            $spec = & $SpecProbe $query
        } else {
            $raw = & $PythonPath -m competition_tools.gateway_launcher $query --config $ConfigPath --workspace $WorkspacePath 2>$null
            if ($LASTEXITCODE -ne 0) {
                $failure = ($raw -join "`n") | ConvertFrom-Json -AsHashtable
                return @{state='blocked';code=$failure.code;exit_code=2}
            }
            $spec = ($raw -join "`n") | ConvertFrom-Json -AsHashtable
        }
        if ($Action -notin @('start','ensure')) {
            if ($null -ne $SpecProbe) { return $spec.status }
            return $spec
        }
        if (-not $spec.config.activation_authorized) {
            return @{state='blocked';code='ACTIVATION_NOT_AUTHORIZED';exit_code=2}
        }
        $leasePath=Join-Path $spec.config.log_directory 'launch.lease'
        try { $lease=[IO.File]::Open($leasePath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None) }
        catch [IO.IOException] {
            if (Test-Path -LiteralPath $leasePath) { return @{state='blocked';code='START_LEASE_PRESENT';exit_code=2} }
            throw
        }
        $releaseLease=$true
        # Revalidate every guard while holding the common cross-process lease.
        if ($null -ne $SpecProbe) {
            $spec = & $SpecProbe $query
        } else {
            $raw = & $PythonPath -m competition_tools.gateway_launcher $query --config $ConfigPath --workspace $WorkspacePath 2>$null
            if ($LASTEXITCODE -ne 0) {throw 'Revalidation failed'}
            $spec = ($raw -join "`n") | ConvertFrom-Json -AsHashtable
        }
        if (-not $spec.config.activation_authorized -or (Join-Path $spec.config.log_directory 'launch.lease') -ne $leasePath) {throw 'Configuration changed'}
        $launcher = $spec.config.configured_launcher
        if ($launcher -match '[\x00-\x1f"%!&|<>^()]' -or -not [IO.Path]::IsPathFullyQualified($launcher)) {throw 'Invalid path'}
        if ((Get-FileHash -LiteralPath $launcher -Algorithm SHA256).Hash.ToLowerInvariant() -ne $spec.launcher_sha256) {throw 'Changed launcher'}
        # Hash and process/ACL checks are performed by the fresh launch-spec query above.
        $prefix = Join-Path $spec.config.log_directory ('launcher-' + [guid]::NewGuid().ToString('N'))
        # Retain the lease after timeout or uncertain spawn failure. A person must
        # inspect the private desktop/process state before removing that one file.
        $releaseLease=$false
        $child = Start-Process -FilePath "$env:SystemRoot/System32/cmd.exe" -ArgumentList @('/d','/s','/c', ('""' + $launcher + '" /INLINE"')) -WindowStyle Hidden -PassThru -RedirectStandardOutput ($prefix+'.stdout.log') -RedirectStandardError ($prefix+'.stderr.log')
        try {
            if($Action -eq 'ensure') {
                $clock=[Diagnostics.Stopwatch]::StartNew()
                while($clock.Elapsed.TotalSeconds -lt [int]$spec.config.timeout_seconds) {
                    $remaining=[int][Math]::Floor([int]$spec.config.timeout_seconds-$clock.Elapsed.TotalSeconds)
                    if($remaining -lt 1){break}
                    $api=& $ApiProbe ([Math]::Min(2,$remaining)) ([Math]::Min(10,$remaining))
                    # Even injected probes must never release a lease on late readiness.
                    if($clock.Elapsed.TotalSeconds -ge [int]$spec.config.timeout_seconds){break}
                    if($api.state -eq 'ready') {
                        $releaseLease=$true
                        return @{state='api_ready';api='connected';account_identity='not_checked';historical_data='not_checked';exit_code=0}
                    }
                    if($api.state -ne 'not_ready'){return @{state='blocked';code=$api.code;exit_code=2}}
                    if($child.HasExited){$releaseLease=$true;return @{state='child_exited';exit_code=$child.ExitCode;api='not_checked'}}
                    $remainingMs=[int]([int]$spec.config.timeout_seconds*1000-$clock.Elapsed.TotalMilliseconds)
                    if($remainingMs -gt 0){Start-Sleep -Milliseconds ([Math]::Min(1000,$remainingMs))}
                }
                return @{state='observation_timeout';api='not_ready';historical_data='not_checked';exit_code=3}
            }
            if (-not $child.WaitForExit([int]$spec.config.timeout_seconds * 1000)) {
                return @{state='observation_timeout';authentication='not_checked';api='not_checked';historical_data='not_checked';exit_code=3}
            }
            $child.WaitForExit()
            $releaseLease=$true
            return @{state='child_exited';exit_code=$child.ExitCode;authentication='not_checked';api='not_checked';historical_data='not_checked'}
        } finally { $child.Dispose() }
    } catch {
        # Never forward upstream streams, paths, INI values or exception text.
        return @{state='blocked';code='LAUNCHER_CHECK_FAILED';exit_code=2}
    } finally {
        if ($null -ne $lease) {
            $lease.Dispose()
            if ($releaseLease) {Remove-Item -LiteralPath $leasePath -ErrorAction SilentlyContinue}
        }
    }
}

function Export-PaperGatewayTask {
    [CmdletBinding()]
    param([string]$OutputPath,[string]$WrapperPath,[string]$PythonPath,[string]$ConfigPath,[string]$WorkspacePath,[string]$UserSid)
    $ErrorActionPreference='Stop'
    foreach($p in @($OutputPath,$WrapperPath,$PythonPath,$ConfigPath,$WorkspacePath)) {
        if (-not [IO.Path]::IsPathFullyQualified($p) -or $p -match '[\x00-\x1f"%!&|<>^()]' -or $p -match '[/\\]\.worktrees[/\\]') {throw 'INVALID_TASK_PATH'}
    }
    if ($UserSid -notmatch '^S-1-5-21-(\d+-){3}\d+$' -or (Test-Path -LiteralPath $OutputPath)) {throw 'INVALID_TASK_CONFIGURATION'}
    # XML artifact only. There is deliberately no registration or enable operation.
    $escape = {param($text) [Security.SecurityElement]::Escape($text)}
    $arguments = '-NoLogo -NoProfile -File "'+$WrapperPath+'" -Action start -PythonPath "'+$PythonPath+'" -ConfigPath "'+$ConfigPath+'" -WorkspacePath "'+$WorkspacePath+'"'
    $xml = @"
<?xml version="1.0" encoding="utf-8"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Review-only Paper Gateway launch. Manual mobile authentication required.</Description></RegistrationInfo>
  <Triggers><LogonTrigger><Enabled>true</Enabled><UserId>$(& $escape $UserSid)</UserId></LogonTrigger></Triggers>
  <Principals><Principal id="Owner"><UserId>$(& $escape $UserSid)</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><StartWhenAvailable>false</StartWhenAvailable><Enabled>false</Enabled><ExecutionTimeLimit>PT6M</ExecutionTimeLimit></Settings>
  <Actions Context="Owner"><Exec><Command>pwsh.exe</Command><Arguments>$(& $escape $arguments)</Arguments></Exec></Actions>
</Task>
"@
    $stream=[IO.File]::Open($OutputPath,[IO.FileMode]::CreateNew)
    try { $bytes=[Text.UTF8Encoding]::new($false).GetBytes($xml); $stream.Write($bytes) } finally {$stream.Dispose()}
}
Export-ModuleMember -Function Invoke-PaperGateway,Export-PaperGatewayTask
