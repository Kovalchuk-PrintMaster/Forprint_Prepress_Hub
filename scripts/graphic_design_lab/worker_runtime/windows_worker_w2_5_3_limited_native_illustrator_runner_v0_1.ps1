# W2.5.3 task action. Runs only in pre-existing interactive user session.
# Never auto-retries, no customer/SMB content. No deletion or app.quit.
param([Parameter(Mandatory=$true)][int]$ExpectedSessionId)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$TaskId = 'gdl-w253-limited-native-001'
$AttemptId = 'a0001'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Here = Join-Path (Join-Path (Join-Path $Root 'jobs') $TaskId) $AttemptId
$Jsx = Join-Path $Here 'input\native_probe.jsx'
$Report = Join-Path $Here 'export\native_runner_result.json'
$AiFile = Join-Path $Here 'export\native_probe.ai'
$SourceHash = '__JSX_SOURCE_SHA__'
$RunnerHash = (Get-FileHash -LiteralPath $MyInvocation.MyCommand.Path -Algorithm SHA256).Hash.ToLowerInvariant()
$RunState = 'BLOCKED_NATIVE_EXECUTION'
$Proof = $false
$AiBytes = 0
$AiHash = $null
$FontName = 'ZapfChanceryC'
$Session = [Diagnostics.Process]::GetCurrentProcess().SessionId
$User = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$ProcessIdBefore = $null
$ErrorCode = 'UNSTARTED'
$Phase = 'STAGE_RUNNER_START'
$IsElevated = $null
$ElevationType = $null
$LimitedToken = $false
try {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ForPrintElevationW253 {
  [DllImport("advapi32.dll", SetLastError=true)]
  public static extern bool GetTokenInformation(IntPtr handle, int cls, out int value, int length, out int returned);
}
'@
    $Phase = 'STAGE_TOKEN_ELEVATION'
    $token = [Security.Principal.WindowsIdentity]::GetCurrent().Token
    $value = 0; $returned = 0
    if (-not [ForPrintElevationW253]::GetTokenInformation($token,20,[ref]$value,4,[ref]$returned)) {
        throw 'TOKEN_ELEVATION_QUERY_FAILED'
    }
    $IsElevated = ([int]$value -eq 1)
    if (-not [ForPrintElevationW253]::GetTokenInformation($token,18,[ref]$value,4,[ref]$returned)) {
        throw 'TOKEN_TYPE_QUERY_FAILED'
    }
    $ElevationType = [int]$value
    if ($IsElevated -or $ElevationType -ne 3) { throw 'TOKEN_NOT_LIMITED' }
    $LimitedToken = $true
    $Phase = 'STAGE_SESSION_VALIDATE'
    if ($env:COMPUTERNAME -ine 'PREPRESS' -or $User -ine 'PREPRESS\Work') { throw 'IDENTITY_INVALID' }
    if ($Session -le 0 -or $Session -ne $ExpectedSessionId) { throw 'SESSION_MISMATCH' }
    if (-not [Environment]::UserInteractive) { throw 'GUI_SESSION_NOT_INTERACTIVE' }
    if (-not (Test-Path -LiteralPath $Jsx -PathType Leaf)) { throw 'JSX_MISSING' }
    if (Test-Path -LiteralPath $Report) { throw 'RESULT_ALREADY_PRESENT' }
    if (Test-Path -LiteralPath $AiFile) { throw 'AI_ALREADY_PRESENT' }
    if ((Get-FileHash -LiteralPath $Jsx -Algorithm SHA256).Hash.ToLowerInvariant() -ne $SourceHash) { throw 'JSX_DIGEST_CHANGED' }
    $Phase = 'STAGE_PROCESS_PRESENT'
    $illustrators=@(Get-Process -Name Illustrator -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq $Session })
    if ($illustrators.Count -ne 1) { throw 'ILLUSTRATOR_PROCESS_NOT_UNIQUE' }
    $ProcessIdBefore = $illustrators[0].Id
    # Attach to the already running Illustrator; NEVER create a second instance.
    $Phase = 'STAGE_COM_ROT_LOOKUP'
    $app = [Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')
    if ($null -eq $app) { throw 'COM_OBJECT_MISSING' }
    $fixedJsx = $Jsx.Replace('\','/')
    $snippet = '$.evalFile(new File(' + "'" + $fixedJsx + "'" + '));'
    $Phase = 'STAGE_JSX_EXECUTE'
    $returnValue = [string]$app.DoJavaScript($snippet)
    if ($returnValue -ne 'FORPRINT_NATIVE_AI_REOPENED') {
        if ($returnValue -match '^W253_JSX_FAIL_[A-Z_]+$') { $ErrorCode = $returnValue }
        throw 'JSX_RESULT_MISMATCH'
    }
    $Phase = 'STAGE_AI_ARTIFACT_VERIFY'
    $after=@(Get-Process -Name Illustrator -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq $Session })
    if ($after.Count -ne 1 -or $after[0].Id -ne $ProcessIdBefore) { throw 'ILLUSTRATOR_INSTANCE_CHANGED' }
    if (-not (Test-Path -LiteralPath $AiFile -PathType Leaf)) { throw 'AI_OUTPUT_MISSING' }
    $fi=Get-Item -LiteralPath $AiFile -Force
    if ($fi.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'AI_OUTPUT_REPARSE' }
    $AiBytes=[long]$fi.Length
    if ($AiBytes -lt 1000) { throw 'AI_OUTPUT_TOO_SMALL' }
    $AiHash=(Get-FileHash -LiteralPath $AiFile -Algorithm SHA256).Hash.ToLowerInvariant()
    $Phase = 'STAGE_DONE'
    $Proof=$true
    $RunState='PASS_NATIVE_AI_REOPENED'
    $ErrorCode='NONE'
} catch {
    # No private text or raw COM exception is ever written into the machine result.
    if ($ErrorCode -eq 'UNSTARTED') { $ErrorCode='NATIVE_STAGE_FAILED_REQUIRES_REVIEW' }
} finally {
    $doc=[ordered]@{
        schema_version='gdl_windows_w2_5_3_native_runner_v0_1'
        task_id=$TaskId
        attempt_id=$AttemptId
        host=$env:COMPUTERNAME
        windows_account=$User
        session_id=$Session
        state=$RunState
        error_code=$ErrorCode
        phase=$Phase
        token_elevated=$IsElevated
        token_elevation_type=$ElevationType
        token_limited_verified=$LimitedToken
        jsx_sha256=$SourceHash
        runner_sha256=$RunnerHash
        illustrator_executed=$Proof
        native_ai_saved_reopened=$Proof
        editable_area_text=$Proof
        font_name=$FontName
        ai_sha256=$AiHash
        ai_bytes=$AiBytes
        preexisting_illustrator_pid=$ProcessIdBefore
        production_ready=$false
        smb_mutation=$false
        client_files_touched=$false
        cleanup_executed=$false
    }
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $doc -Compress -Depth 5))
    # CreateNew prevents overwriting prior result even if task is invoked again.
    $f=[IO.File]::Open($Report,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $f.Write($bytes,0,$bytes.Length) } finally { $f.Dispose() }
}
if (-not $Proof) { exit 2 }
exit 0
