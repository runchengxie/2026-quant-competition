# PowerShell 7. All arguments are parsed inside the redacting error boundary.
$ErrorActionPreference='Stop'
try {
    $options=@{}
    if ($args.Count -eq 1 -and $args[0] -in @('--help','-Help')) {
        Write-Output 'Start-PaperGateway.ps1 -Action check|dry-run|status|prepare|start|ensure -PythonPath <python.exe> -ConfigPath <launcher.json> -WorkspacePath <workspace.toml> [-ApiConnectionPath <paper-connection.json>]'
        exit 0
    }
    if ($args.Count -notin @(8,10)) {throw 'Invalid arguments'}
    for($i=0;$i -lt $args.Count;$i+=2) {
        $name=$args[$i]
        if ($name -notin @('-Action','-PythonPath','-ConfigPath','-WorkspacePath','-ApiConnectionPath') -or $options.ContainsKey($name.Substring(1))) {throw 'Invalid arguments'}
        $options[$name.Substring(1)]=$args[$i+1]
    }
    if ($options.Action -notin @('check','dry-run','status','prepare','start','ensure')) {throw 'Invalid arguments'}
    if(($options.Action -eq 'ensure') -ne $options.ContainsKey('ApiConnectionPath')) {throw 'Invalid arguments'}
} catch {
    Write-Output '{"state":"blocked","code":"INVALID_ARGUMENTS","exit_code":2}'
    exit 2
}
try {
    Import-Module (Join-Path $PSScriptRoot 'PaperGateway.psm1') -Force
    $result=Invoke-PaperGateway @options
    $result | ConvertTo-Json -Compress
    if ($result.ContainsKey('exit_code')) {exit $result.exit_code}
    exit 0
} catch {
    Write-Output '{"state":"blocked","code":"LAUNCHER_CHECK_FAILED","exit_code":2}'
    exit 2
}
