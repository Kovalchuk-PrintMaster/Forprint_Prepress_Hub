# W2.5.1 synthetic diagnostic: same interactive Task Scheduler token as W2.5.
# NO Illustrator scripting, no document create/save/open, no customer/SMB.
param([Parameter(Mandatory=$true)][int]$ExpectedSessionId)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$TaskId='gdl-w251-com-attach-001'
$AttemptId='a0001'
$Root='D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Attempt=Join-Path (Join-Path (Join-Path $Root 'jobs') $TaskId) $AttemptId
$Report=Join-Path $Attempt 'export\com_attach_result.json'
$RunnerSha=(Get-FileHash -LiteralPath $MyInvocation.MyCommand.Path -Algorithm SHA256).Hash.ToLowerInvariant()
$TemplateSha='__RUNNER_SOURCE_SHA__'
$State='BLOCKED_COM_ATTACH'
$Phase='STAGE_RUNNER_START'
$ErrorCode='NOT_STARTED'
$ErrorHresult=$null
$Version=$null
$PidBefore=$null
$Session=[Diagnostics.Process]::GetCurrentProcess().SessionId
$Identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
try {
    $Phase='STAGE_SESSION_VALIDATE'
    if($env:COMPUTERNAME -ine 'PREPRESS' -or $Identity -ine 'PREPRESS\Work') { throw 'IDENTITY_GUARD' }
    if($Session -le 0 -or $Session -ne $ExpectedSessionId -or -not [Environment]::UserInteractive) {
        throw 'INTERACTIVE_SESSION_GUARD'
    }
    $Phase='STAGE_PROCESS_PRESENT'
    $apps=@(Get-Process -Name Illustrator -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $Session})
    if($apps.Count -ne 1) { throw 'ILLUSTRATOR_PROCESS_GUARD' }
    $PidBefore=[int]$apps[0].Id
    $Phase='STAGE_COM_ROT_LOOKUP'
    try {
        # GetActiveObject attaches only. It NEVER creates a new Illustrator process.
        $com=[Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')
        if($null -eq $com) { throw 'NULL_ACTIVE_COM_OBJECT' }
    } catch {
        $ErrorCode='COM_ROT_ATTACH_FAILED'
        $exc=$_.Exception
        if($null -ne $exc.InnerException) { $exc=$exc.InnerException }
        $ErrorHresult=[string]$exc.HResult
        throw 'COM_ATTACH_STAGE_FAILED'
    }
    $Phase='STAGE_COM_VERSION'
    try {
        # Read-only version property; no document API access.
        $Version=[string]$com.Version
        if([string]::IsNullOrWhiteSpace($Version) -or $Version.Length -gt 80) { throw 'VERSION_NOT_READABLE' }
    } catch {
        $ErrorCode='COM_VERSION_READ_FAILED'
        $exc=$_.Exception
        if($null -ne $exc.InnerException) { $exc=$exc.InnerException }
        $ErrorHresult=[string]$exc.HResult
        throw 'COM_VERSION_STAGE_FAILED'
    }
    $after=@(Get-Process -Name Illustrator -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $Session})
    if($after.Count -ne 1 -or [int]$after[0].Id -ne $PidBefore) { throw 'ILLUSTRATOR_PROCESS_CHANGED' }
    $Phase='STAGE_DONE'
    $ErrorCode='NONE'
    $State='PASS_COM_READONLY_ATTACH'
} catch {
    if($ErrorCode -eq 'NOT_STARTED') { $ErrorCode='LOCAL_GUARD_OR_PROCESS_FAILED' }
} finally {
    $doc=[ordered]@{
        schema_version='gdl_windows_w2_5_1_com_attach_runner_v0_1';task_id=$TaskId
        attempt_id=$AttemptId;host=$env:COMPUTERNAME;windows_account=$Identity
        session_id=$Session;state=$State;phase=$Phase;error_code=$ErrorCode
        error_hresult=$ErrorHresult;runner_sha256=$RunnerSha
        source_template_sha256=$TemplateSha;illustrator_version=$Version
        preexisting_illustrator_pid=$PidBefore
        illustrator_document_mutation=$false;production_ready=$false;smb_mutation=$false
        client_files_touched=$false;cleanup_executed=$false
    }
    $payload=[Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $doc -Depth 6 -Compress))
    $f=[IO.File]::Open($Report,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try {$f.Write($payload,0,$payload.Length)} finally {$f.Dispose()}
}
if($State -ne 'PASS_COM_READONLY_ATTACH') {exit 2}
exit 0
