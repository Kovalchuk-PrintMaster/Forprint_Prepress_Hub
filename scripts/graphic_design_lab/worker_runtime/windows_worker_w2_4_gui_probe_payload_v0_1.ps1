# ForPrint W2.4 synthetic GUI session proof. Scheduled Task ONLY; no Adobe/SMB.
param([Parameter(Mandatory=$true)][int]$ExpectedSessionId)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$TaskId = 'gdl-w24-gui-probe-001'
$AttemptId = 'a0001'
$Schema = 'gdl_windows_w2_4_gui_probe_result_v0_1'
$ActualSession = [Diagnostics.Process]::GetCurrentProcess().SessionId
$Identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$Interactive = [Environment]::UserInteractive
$ExplorerSameSession = @((Get-Process -Name explorer -ErrorAction SilentlyContinue) | Where-Object { $_.SessionId -eq $ActualSession }).Count -gt 0
$SourcePath = $MyInvocation.MyCommand.Path
$ScriptSha256 = (Get-FileHash -LiteralPath $SourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
$AttemptDir = Split-Path -Parent $PSScriptRoot
$ExportDir = Join-Path $AttemptDir 'export'
$ResultPath = Join-Path $ExportDir 'gui_probe_result.json'
$Passed = ($env:COMPUTERNAME -ieq 'PREPRESS' -and $Identity -ieq 'PREPRESS\Work' -and
           $ActualSession -eq $ExpectedSessionId -and $ActualSession -gt 0 -and
           $Interactive -and $ExplorerSameSession)
$Result = [ordered]@{
    schema_version = $Schema
    task_id = $TaskId
    attempt_id = $AttemptId
    host = $env:COMPUTERNAME
    windows_account = $Identity
    expected_session_id = $ExpectedSessionId
    actual_session_id = $ActualSession
    user_interactive = [bool]$Interactive
    explorer_same_session = [bool]$ExplorerSameSession
    source_sha256 = $ScriptSha256
    state = $(if ($Passed) {'PASS_SYNTHETIC_INTERACTIVE'} else {'FAIL_GUI_CONTEXT'})
    illustrator_execution = $false
    smb_mutation = $false
    client_files_touched = $false
    production_ready = $false
    cleanup_executed = $false
}
if (-not (Test-Path -LiteralPath $ExportDir -PathType Container)) { exit 10 }
# New-only result: a stale proof must not be silently overwritten.
if (Test-Path -LiteralPath $ResultPath) { exit 11 }
$Json = ConvertTo-Json -InputObject $Result -Depth 5 -Compress
$Bytes = [Text.UTF8Encoding]::new($false).GetBytes($Json)
$Stream = [IO.File]::Open($ResultPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
try { $Stream.Write($Bytes,0,$Bytes.Length) } finally { $Stream.Dispose() }
if ($Passed) { exit 0 }
exit 3
