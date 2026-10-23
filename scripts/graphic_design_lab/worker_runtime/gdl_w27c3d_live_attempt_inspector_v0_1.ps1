# GDL W2.7-C3D: READ-ONLY Windows attempt evidence inspector (synthetic-only).
# No JSX, COM, Task Scheduler calls, process start, cleanup, customer or SMB access.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$TaskId = '__TASK_ID__'
$AttemptId = '__ATTEMPT_ID__'
$ArchiveSha = '__ARCHIVE_SHA__'
$ArchiveBytes = __ARCHIVE_BYTES__
$ReceiptSha = '__RECEIPT_SHA__'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Shared = 'D:\ForPrint_Automation'
$Jobs = Join-Path $Root 'jobs'
$Task = Join-Path $Jobs $TaskId
$Attempt = Join-Path $Task $AttemptId
$InputDir = Join-Path $Attempt 'input'
$WorkDir = Join-Path $Attempt 'work'
$ExportDir = Join-Path $Attempt 'export'
$Archive = Join-Path $InputDir 'task_package.zip'
$Receipt = Join-Path $WorkDir 'staging_receipt.json'
function Fail([string]$code) { throw ('W27C3D_BLOCKED:' + $code) }
function SafeDirectory([string]$path) {
    $i=Get-Item -LiteralPath $path -Force -ErrorAction Stop
    if(-not $i.PSIsContainer -or ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail 'DIRECTORY_UNSAFE' }
}
function SafeRegular([string]$path) {
    $i=Get-Item -LiteralPath $path -Force -ErrorAction Stop
    if($i.PSIsContainer -or ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Fail 'FILE_UNSAFE' }
    return $i
}
function Evidence([string]$path,[long]$maxBytes) {
    if(-not (Test-Path -LiteralPath $path)) {
        return [ordered]@{present=$false;bytes=$null;sha256=$null}
    }
    $i=SafeRegular $path
    if($i.Length -gt $maxBytes) { Fail 'EVIDENCE_SIZE_UNSAFE_PRESERVE' }
    return [ordered]@{
        present=$true
        bytes=[long]$i.Length
        sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    }
}
try {
    $who=[Security.Principal.WindowsIdentity]::GetCurrent()
    if($env:COMPUTERNAME -ine 'PREPRESS' -or $who.Name -ine 'PREPRESS\Work' -or
       $who.User.Value -ne 'S-1-5-21-3087849371-1068859030-1179031902-1001') { Fail 'IDENTITY_CHANGED' }
    if($TaskId -cnotmatch '^[a-z][a-z0-9-]{3,63}$' -or $AttemptId -cnotmatch '^a[0-9]{4}$') { Fail 'ID_INVALID' }
    foreach($path in @($Shared,$Root,$Jobs,$Task,$Attempt,$InputDir,$WorkDir,$ExportDir)) {
        SafeDirectory $path
    }
    $p=SafeRegular $Archive
    if($p.Length -ne $ArchiveBytes -or
       (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ArchiveSha) {
        Fail 'STAGED_ARCHIVE_CHANGED'
    }
    $r=SafeRegular $Receipt
    if($r.Length -lt 100 -or $r.Length -gt 8192 -or
       (Get-FileHash -LiteralPath $Receipt -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ReceiptSha) {
        Fail 'STAGING_RECEIPT_CHANGED'
    }
    $receipt=Get-Content -LiteralPath $Receipt -Raw -Encoding UTF8 | ConvertFrom-Json
    if($receipt.schema_version -ne 'gdl_w27b_windows_stage_receipt_v0_1' -or
       $receipt.state -ne 'SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED' -or
       $receipt.task_id -cne $TaskId -or $receipt.attempt_id -cne $AttemptId -or
       $receipt.archive_sha256 -cne $ArchiveSha -or [long]$receipt.archive_bytes -ne $ArchiveBytes -or
       $receipt.host -ne 'PREPRESS' -or $receipt.windows_account -ne 'PREPRESS\Work' -or
       $receipt.worker_launch_authorized -ne $false -or $receipt.production_ready -ne $false -or
       $receipt.payload_extracted -ne $false -or $receipt.illustrator_execution -ne $false -or
       $receipt.client_files_touched -ne $false -or $receipt.cleanup_executed -ne $false) {
        Fail 'STAGING_RECEIPT_BINDING_CHANGED'
    }
    $artifacts=[ordered]@{
        start_claim=(Evidence (Join-Path $WorkDir 'start_claim.json') 32768)
        execution_started=(Evidence (Join-Path $WorkDir 'execution_started.json') 32768)
        jsx=(Evidence (Join-Path $InputDir 'main.jsx') 262144)
        native_ai=(Evidence (Join-Path $ExportDir 'native_result.ai') 104857600)
        worker_result=(Evidence (Join-Path $ExportDir 'worker_result.json') 65536)
    }
    $hasEvidence=$false
    foreach($key in @($artifacts.Keys)) { if($artifacts[$key].present) { $hasEvidence=$true } }
    $state=if($hasEvidence) {'EXECUTION_EVIDENCE_PRESENT_RECONCILIATION_REQUIRED'} else {'STAGED_ATTEMPT_INERT_NO_EXECUTION_EVIDENCE'}
    $doc=[ordered]@{
        schema_version='gdl_w27c3d_live_attempt_inspection_v0_1'
        state=$state;task_id=$TaskId;attempt_id=$AttemptId;host='PREPRESS';windows_account=$who.Name
        archive_sha256=$ArchiveSha;archive_bytes=$ArchiveBytes;staging_receipt_sha256=$ReceiptSha
        artifacts=$artifacts;execution_evidence_present=$hasEvidence;live_observation=$true
        no_rerun_authorized=$true;worker_launch_authorized=$false;dispatch_authorized=$false
        production_ready=$false;accepted=$false;windows_mutation=$false
        jsx_executed_by_inspector=$false;com_attach_performed=$false
        scheduler_mutation=$false;cleanup_executed=$false;client_files_touched=$false;smb_mutation=$false
    }
    [Console]::Out.WriteLine((ConvertTo-Json -InputObject $doc -Depth 7 -Compress))
    exit 0
} catch {
    # Preserve partial evidence. Do not expose raw files, private paths or exception text.
    [Console]::Error.WriteLine('W27C3D_BLOCKED:READ_ONLY_ATTEMPT_INSPECTION_FAILED_PRESERVE_EVIDENCE')
    exit 2
}
# NO_AUTOMATIC_CLEANUP; NO_JSX_EXECUTION; NO_DISPATCH; NO_RETRY.
