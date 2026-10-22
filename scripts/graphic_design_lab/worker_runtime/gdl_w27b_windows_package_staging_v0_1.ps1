# GDL W2.7-B: opaque verified synthetic ZIP staged on PREPRESS. NEVER executes JSX.
# One bounded attempt, no customer files, no Task Scheduler, no SMB, no cleanup.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Mode = '__MODE__'
$ArchiveB64 = '__ARCHIVE_B64__'
$ArchiveSha = '__ARCHIVE_SHA__'
$ArchiveLength = __ARCHIVE_BYTES__
$TaskId = '__TASK_ID__'
$AttemptId = '__ATTEMPT_ID__'
$Shared = 'D:\ForPrint_Automation'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Jobs = Join-Path $Root 'jobs'
$TaskDir = Join-Path $Jobs $TaskId
$AttemptDir = Join-Path $TaskDir $AttemptId
$InputDir = Join-Path $AttemptDir 'input'
$WorkDir = Join-Path $AttemptDir 'work'
$ExportDir = Join-Path $AttemptDir 'export'
$Package = Join-Path $InputDir 'task_package.zip'
$Receipt = Join-Path $WorkDir 'staging_receipt.json'
$OperatorSid = 'S-1-5-21-3087849371-1068859030-1179031902-1001'
function Block([string]$code) { throw ('W27B_BLOCKED:' + $code) }
function SafeDir([string]$path, [bool]$requireProtected) {
    if(-not (Test-Path -LiteralPath $path -PathType Container)) { Block 'DIR_MISSING' }
    $item = Get-Item -LiteralPath $path -Force
    if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Block 'DIR_REPARSE' }
    $acl = Get-Acl -LiteralPath $path
    if([bool]$acl.AreAccessRulesProtected -ne $requireProtected) { Block 'ACL_INHERITANCE_CHANGED' }
    $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if($owner -notin @('S-1-5-32-544',$OperatorSid)) { Block 'ACL_OWNER_CHANGED' }
    if($path -in @($Shared,$Root,$Jobs) -and $owner -ne 'S-1-5-32-544') { Block 'WORKSPACE_OWNER_CHANGED' }
    $r = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if($r.Count -ne 3) { Block 'ACL_COUNT_CHANGED' }
    $want = @('S-1-5-18','S-1-5-32-544',$OperatorSid)
    $seen=@{}
    $flags=[Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
    $full=[int][Security.AccessControl.FileSystemRights]::FullControl
    foreach($ace in $r) {
        $who=$ace.IdentityReference.Value
        $rights=[int]$ace.FileSystemRights
        if($want -notcontains $who -or $seen.ContainsKey($who)) { Block 'ACL_PRINCIPAL_INVALID' }
        $seen[$who]=$true
        if($ace.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
           $ace.InheritanceFlags -ne $flags -or
           $ace.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
           [bool]$ace.IsInherited -eq $requireProtected -or
           ($rights -band $full) -ne $full -or ($rights -band (-bnot $full)) -ne 0) { Block 'ACL_RIGHTS_INVALID' }
    }
    foreach($who in $want) { if(-not $seen.ContainsKey($who)) { Block 'ACL_REQUIRED_PRINCIPAL_ABSENT' } }
}
function SafeFile([string]$path) {
    if(-not (Test-Path -LiteralPath $path -PathType Leaf)) { Block 'STAGED_FILE_ABSENT' }
    $item=Get-Item -LiteralPath $path -Force
    if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Block 'STAGED_FILE_REPARSE' }
}
function Sha([byte[]]$bytes) {
    $hasher=[Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($hasher.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() }
    finally { $hasher.Dispose() }
}
function WriteOnce([string]$path,[byte[]]$bytes) {
    $f=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $f.Write($bytes,0,$bytes.Length); $f.Flush($true) } finally { $f.Dispose() }
}
try {
    if($Mode -notin @('check','stage','verify')) { Block 'MODE_INVALID' }
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    if($env:COMPUTERNAME -ine 'PREPRESS' -or $identity.Name -ine 'PREPRESS\Work' -or
       $identity.User.Value -ne $OperatorSid) { Block 'HOST_OR_ACCOUNT_CHANGED' }
    if($TaskId -cnotmatch '^[a-z][a-z0-9-]{3,63}$' -or
       $AttemptId -cnotmatch '^a[0-9]{4}$') { Block 'IDENTITY_INVALID' }
    SafeDir $Shared $true
    SafeDir $Root $false
    SafeDir $Jobs $false
    $bytes=[Convert]::FromBase64String($ArchiveB64)
    if($ArchiveLength -le 200 -or $ArchiveLength -gt 262144 -or
       $bytes.Length -ne $ArchiveLength -or (Sha $bytes) -ne $ArchiveSha) { Block 'ARCHIVE_SOURCE_DIGEST_MISMATCH' }
    $changed=$false
    $receiptSha=$null
    if($Mode -eq 'check' -or $Mode -eq 'stage') {
        if((Test-Path -LiteralPath $TaskDir) -or (Test-Path -LiteralPath $AttemptDir)) {
            Block 'TASK_EXISTS_NO_RESTAGE'
        }
        $state='READY_FOR_SYNTHETIC_STAGE'
        if($Mode -eq 'stage') {
            foreach($path in @($TaskDir,$AttemptDir,$InputDir,$WorkDir,$ExportDir)) {
                if(Test-Path -LiteralPath $path) { Block 'PARTIAL_ATTEMPT_EXISTS' }
                [void][IO.Directory]::CreateDirectory($path)
                SafeDir $path $false
            }
            WriteOnce $Package $bytes
            $staged=[IO.File]::ReadAllBytes($Package)
            if($staged.Length -ne $ArchiveLength -or (Sha $staged) -ne $ArchiveSha) { Block 'STAGED_ARCHIVE_CHANGED' }
            $receiptDoc=[ordered]@{
                schema_version='gdl_w27b_windows_stage_receipt_v0_1'
                state='SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED'
                task_id=$TaskId;attempt_id=$AttemptId;archive_sha256=$ArchiveSha
                archive_bytes=$ArchiveLength;host='PREPRESS';windows_account='PREPRESS\Work'
                payload_extracted=$false;illustrator_execution=$false
                worker_launch_authorized=$false;production_ready=$false
                client_files_touched=$false;smb_mutation=$false;cleanup_executed=$false
            }
            $receiptBytes=[Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $receiptDoc -Compress -Depth 4))
            WriteOnce $Receipt $receiptBytes
            $receiptSha=Sha $receiptBytes
            $changed=$true
            $state='SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED'
        }
    } else {
        foreach($p in @($TaskDir,$AttemptDir,$InputDir,$WorkDir,$ExportDir)) { SafeDir $p $false }
        SafeFile $Package
        SafeFile $Receipt
        $staged=[IO.File]::ReadAllBytes($Package)
        if($staged.Length -ne $ArchiveLength -or (Sha $staged) -ne $ArchiveSha) { Block 'STAGED_ARCHIVE_CHANGED' }
        $receiptBytes=[IO.File]::ReadAllBytes($Receipt)
        if($receiptBytes.Length -lt 100 -or $receiptBytes.Length -gt 8192) { Block 'STAGING_RECEIPT_SIZE' }
        $receiptSha=Sha $receiptBytes
        $r=[Text.Encoding]::UTF8.GetString($receiptBytes) | ConvertFrom-Json
        if($r.schema_version -ne 'gdl_w27b_windows_stage_receipt_v0_1' -or
           $r.state -ne 'SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED' -or
           $r.task_id -cne $TaskId -or $r.attempt_id -cne $AttemptId -or
           $r.archive_sha256 -cne $ArchiveSha -or [long]$r.archive_bytes -ne $ArchiveLength -or
           $r.host -ne 'PREPRESS' -or $r.windows_account -ne 'PREPRESS\Work' -or
           $r.payload_extracted -ne $false -or $r.illustrator_execution -ne $false -or
           $r.worker_launch_authorized -ne $false -or $r.production_ready -ne $false -or
           $r.client_files_touched -ne $false -or $r.smb_mutation -ne $false -or
           $r.cleanup_executed -ne $false) { Block 'STAGING_RECEIPT_BINDING_MISMATCH' }
        $state='SYNTHETIC_STAGE_SHA_VERIFIED_NOT_EXECUTED'
    }
    $out=[ordered]@{
        schema_version='gdl_w27b_windows_stage_controller_v0_1'
        mode=$Mode;state=$state;host='PREPRESS';ssh_account=$identity.Name
        task_id=$TaskId;attempt_id=$AttemptId;archive_sha256=$ArchiveSha
        archive_bytes=$ArchiveLength;staging_receipt_sha256=$receiptSha
        windows_mutation=$changed;payload_extracted=$false;illustrator_execution=$false
        worker_launch_authorized=$false;production_ready=$false;accepted=$false
        scheduled_tasks_mutated=$false;client_files_touched=$false;smb_mutation=$false
        cleanup_executed=$false
    }
    [Console]::Out.WriteLine((ConvertTo-Json -InputObject $out -Compress -Depth 6))
    exit 0
} catch {
    [Console]::Error.WriteLine('W27B_BLOCKED:WINDOWS_STAGE_FAILED_PRESERVE_PARTIAL_EVIDENCE')
    exit 2
}
# NO_AUTOMATIC_CLEANUP, NO_TASK_SCHEDULER, NO_JSX_EXECUTION.
