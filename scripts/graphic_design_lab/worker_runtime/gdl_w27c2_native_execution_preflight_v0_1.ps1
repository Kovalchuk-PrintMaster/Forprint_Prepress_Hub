# W2.7-C2: READ ONLY staged synthetic Illustrator execution preflight.
# No Task Scheduler mutation, COM, JSX execution, file writing, cleanup, or customer access.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$TaskId = '__TASK_ID__'
$AttemptId = '__ATTEMPT_ID__'
$ArchiveSha = '__ARCHIVE_SHA__'
$ArchiveBytes = __ARCHIVE_BYTES__
$JsxSha = '__JSX_SHA__'
$JsxBytes = __JSX_BYTES__
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Attempt = Join-Path (Join-Path (Join-Path $Root 'jobs') $TaskId) $AttemptId
$InputDir = Join-Path $Attempt 'input'
$WorkDir = Join-Path $Attempt 'work'
$ExportDir = Join-Path $Attempt 'export'
$Package = Join-Path $InputDir 'task_package.zip'
$Receipt = Join-Path $WorkDir 'staging_receipt.json'
function Block([string]$code) { throw ('W27C2_BLOCKED:' + $code) }
function Regular([string]$path) {
    $x = Get-Item -LiteralPath $path -Force -ErrorAction Stop
    if($x.PSIsContainer -or ($x.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Block 'UNSAFE_FILE' }
    return $x
}
function Directory([string]$path) {
    $x = Get-Item -LiteralPath $path -Force -ErrorAction Stop
    if(-not $x.PSIsContainer -or ($x.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Block 'UNSAFE_DIRECTORY' }
}
function Sha([byte[]]$bytes) {
    $h=[Security.Cryptography.SHA256]::Create()
    try {return [BitConverter]::ToString($h.ComputeHash($bytes)).Replace('-','').ToLowerInvariant()}
    finally {$h.Dispose()}
}
try {
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    if($env:COMPUTERNAME -ine 'PREPRESS' -or $identity.Name -ine 'PREPRESS\Work') { Block 'HOST_ACCOUNT_CHANGED' }
    if($TaskId -cnotmatch '^[a-z][a-z0-9-]{3,63}$' -or $AttemptId -cnotmatch '^a[0-9]{4}$') {Block 'BAD_ID'}
    foreach($dir in @('D:\ForPrint_Automation',$Root,(Join-Path $Root 'jobs'),
        (Join-Path (Join-Path $Root 'jobs') $TaskId),$Attempt,$InputDir,$WorkDir,$ExportDir)) { Directory $dir }
    $packageInfo=Regular $Package
    $receiptInfo=Regular $Receipt
    if($packageInfo.Length -ne $ArchiveBytes -or
        (Get-FileHash -LiteralPath $Package -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ArchiveSha) {Block 'STAGED_ZIP_DIGEST_MISMATCH'}
    if($receiptInfo.Length -lt 100 -or $receiptInfo.Length -gt 8192) {Block 'BAD_STAGING_RECEIPT_SIZE'}
    $r=Get-Content -LiteralPath $Receipt -Raw -Encoding UTF8 | ConvertFrom-Json
    if($r.schema_version -ne 'gdl_w27b_windows_stage_receipt_v0_1' -or
       $r.state -ne 'SYNTHETIC_PACKAGE_STAGED_NOT_EXECUTED' -or
       $r.task_id -cne $TaskId -or $r.attempt_id -cne $AttemptId -or
       $r.archive_sha256 -cne $ArchiveSha -or [long]$r.archive_bytes -ne $ArchiveBytes -or
       $r.host -ne 'PREPRESS' -or $r.windows_account -ne 'PREPRESS\Work' -or
       $r.payload_extracted -ne $false -or $r.illustrator_execution -ne $false -or
       $r.worker_launch_authorized -ne $false -or $r.production_ready -ne $false -or
       $r.client_files_touched -ne $false -or $r.smb_mutation -ne $false -or
       $r.cleanup_executed -ne $false) {Block 'STAGING_RECEIPT_BINDING_MISMATCH'}
    Add-Type -AssemblyName System.IO.Compression
    $fs=[IO.File]::Open($Package,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    try {
        $zip=[IO.Compression.ZipArchive]::new($fs,[IO.Compression.ZipArchiveMode]::Read,$false)
        try {
            if($zip.Entries.Count -ne 2) {Block 'PACKAGE_MEMBERS_CHANGED'}
            $names=@($zip.Entries | ForEach-Object { $_.FullName })
            if(@($names | Where-Object {$_ -eq 'task_manifest.json'}).Count -ne 1 -or
               @($names | Where-Object {$_ -eq 'input/main.jsx'}).Count -ne 1) {Block 'ZIP_ENTRY_IDENTITY'}
            $entry=$zip.GetEntry('input/main.jsx')
            if($null -eq $entry -or $entry.Length -ne $JsxBytes) {Block 'JSX_SIZE_MISMATCH'}
            $stm=$entry.Open()
            try {
                $mem=[IO.MemoryStream]::new()
                try {$stm.CopyTo($mem);$payload=$mem.ToArray()}
                finally {$mem.Dispose()}
            } finally {$stm.Dispose()}
            if($payload.Length -ne $JsxBytes -or (Sha $payload) -cne $JsxSha) {Block 'JSX_DIGEST_MISMATCH'}
            $manifestEntry=$zip.GetEntry('task_manifest.json')
            if($null -eq $manifestEntry -or $manifestEntry.Length -gt 32768) {Block 'MANIFEST_ENTRY_INVALID'}
            $reader=[IO.StreamReader]::new($manifestEntry.Open(),[Text.Encoding]::UTF8)
            try {$m=$reader.ReadToEnd() | ConvertFrom-Json}
            finally {$reader.Dispose()}
            if($m.schema_version -ne 'gdl_illustrator_task_package_v0_1' -or
               $m.state -ne 'PREPARED_NOT_DISPATCH_AUTHORIZED' -or
               $m.task_id -cne $TaskId -or $m.attempt_id -cne $AttemptId -or
               $m.data_class -ne 'SYNTHETIC_ONLY' -or $m.adapter_id -ne 'illustrator' -or
               $m.script_path -cne 'input/main.jsx' -or
               $m.authority.worker_launch -ne $false -or
               $m.authority.dispatch_authorized -ne $false -or
               $m.authority.production_publish -ne $false -or
               $m.authority.automatic_accept -ne $false -or
               $m.inputs.Count -ne 1 -or $m.inputs[0].path -cne 'input/main.jsx' -or
               $m.inputs[0].sha256 -cne $JsxSha -or [long]$m.inputs[0].bytes -ne $JsxBytes) {
                Block 'ARCHIVE_MANIFEST_BINDING_CHANGED'
            }
        } finally {$zip.Dispose()}
    } finally {$fs.Dispose()}
    # Never interpret an existing execution claim or output as permission to rerun.
    foreach($p in @((Join-Path $WorkDir 'start_claim.json'),
                    (Join-Path $ExportDir 'native_result.ai'),
                    (Join-Path $ExportDir 'worker_result.json'))) {
        if(Test-Path -LiteralPath $p) {Block 'EXISTING_EXECUTION_OR_OUTPUT_EVIDENCE'}
    }
    $session=$null
    $illustratorPid=$null
    $state='WAITING_FOR_INTERACTIVE_SESSION_NOT_AUTHORIZED'
    $lines=@(& quser.exe 2>&1 | ForEach-Object {[string]$_})
    if($LASTEXITCODE -eq 0) {
        $ids=@()
        foreach($line in $lines) {
            $match=[regex]::Match($line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b')
            if($match.Success) {$ids += [int]$match.Groups[1].Value}
        }
        if($ids.Count -eq 1 -and $ids[0] -gt 0) {
            $session=$ids[0]
            $explorers=@(Get-Process -Name explorer -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $session})
            $illustrators=@(Get-Process -Name Illustrator -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $session})
            if($explorers.Count -ge 1 -and $illustrators.Count -eq 1) {
                $illustratorPid=[int]$illustrators[0].Id
                $state='STAGED_NATIVE_HOST_PREREQUISITES_PRESENT_AUTHORITY_PENDING'
            } else {$state='WAITING_FOR_ILLUSTRATOR_OR_DESKTOP_NOT_AUTHORIZED'}
        }
    }
    $doc=[ordered]@{
        schema_version='gdl_w27c2_native_execution_preflight_v0_1'
        state=$state; task_id=$TaskId; attempt_id=$AttemptId; host='PREPRESS'
        windows_account=$identity.Name; archive_sha256=$ArchiveSha
        archive_bytes=$ArchiveBytes; jsx_sha256=$JsxSha; jsx_bytes=$JsxBytes
        staging_receipt_sha256=(Get-FileHash -LiteralPath $Receipt -Algorithm SHA256).Hash.ToLowerInvariant()
        session_id=$session; preexisting_illustrator_pid=$illustratorPid
        windows_mutation=$false; payload_extracted=$false; illustrator_execution=$false
        com_attach_performed=$false; scheduled_tasks_mutated=$false
        worker_launch_authorized=$false; dispatch_authorized=$false
        production_ready=$false; accepted=$false; cleanup_executed=$false
        client_files_touched=$false; smb_mutation=$false
    }
    [Console]::Out.WriteLine((ConvertTo-Json -InputObject $doc -Compress -Depth 6))
    exit 0
} catch {
    # Do not emit raw remote exceptions / absolute paths / input contents.
    [Console]::Error.WriteLine('W27C2_BLOCKED:READ_ONLY_PREFLIGHT_FAILED')
    exit 2
}
# NO_AUTOMATIC_CLEANUP; NO_COM_EXECUTION; NO_TASK_SCHEDULER_MUTATION.
