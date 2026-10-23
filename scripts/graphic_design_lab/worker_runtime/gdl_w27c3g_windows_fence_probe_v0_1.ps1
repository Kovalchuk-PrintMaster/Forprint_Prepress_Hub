# GDL W2.7-C3G. Synthetic-only Windows CreateNew fence proof in FRESH isolated job.
# NO_COM, NO_JSX, NO_SCHEDULER, NO_CLIENT_FILES, NO_CLEANUP, NO_DISPATCH.
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$Mode='__MODE__'
$ProbeTask='gdl-w27g-synthetic-fence-001'
$ProbeAttempt='a0001'
$NativeTask='gdl-w27c-native-001'
$NativeAttempt='a0001'
$NativePackageSha='d1949844b3ab2d68936facf8012e6b8fba1ecd1134597f2e6f4139ef1449b3e7'
$NativeReceiptSha='0c025e0132795c7f0e7011fbe52fdf17c44f9f19fc01dcd34f77684e4b11e827'
$ExpectedProbeSha='__EXPECTED_PROBE_SHA__'
$Shared='D:\ForPrint_Automation'
$Root=Join-Path $Shared 'GraficsDesignLab\Automation'
$Jobs=Join-Path $Root 'jobs'
$Task=Join-Path $Jobs $ProbeTask
$Attempt=Join-Path $Task $ProbeAttempt
$Work=Join-Path $Attempt 'work'
$Claim=Join-Path $Work 'fence_probe.json'
$Native=Join-Path (Join-Path $Jobs $NativeTask) $NativeAttempt
$NativePkg=Join-Path (Join-Path $Native 'input') 'task_package.zip'
$NativeReceipt=Join-Path (Join-Path $Native 'work') 'staging_receipt.json'
$OperatorSid='S-1-5-21-3087849371-1068859030-1179031902-1001'
function Block([string]$code){throw ('C3G_BLOCKED:'+ $code)}
function SafeDir([string]$path,[bool]$protected){
    if(-not (Test-Path -LiteralPath $path -PathType Container)){Block 'DIR_MISSING'}
    $item=Get-Item -LiteralPath $path -Force
    if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Block 'DIR_REPARSE'}
    $acl=Get-Acl -LiteralPath $path
    if([bool]$acl.AreAccessRulesProtected -ne $protected){Block 'ACL_INHERITANCE_CHANGED'}
    $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if($owner -notin @('S-1-5-32-544',$OperatorSid)){Block 'ACL_OWNER_CHANGED'}
    if($path -in @($Shared,$Root,$Jobs) -and $owner -ne 'S-1-5-32-544'){Block 'ROOT_OWNER_CHANGED'}
    $aces=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if($aces.Count -ne 3){Block 'ACL_COUNT_CHANGED'}
    $full=[int][Security.AccessControl.FileSystemRights]::FullControl
    $flags=[Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
    $wanted=@('S-1-5-18','S-1-5-32-544',$OperatorSid)
    $seen=@{}
    foreach($ace in $aces){
        $sid=$ace.IdentityReference.Value
        if($sid -notin $wanted -or $seen.ContainsKey($sid)){Block 'ACL_SID_CHANGED'}
        $seen[$sid]=$true
        $rights=[int]$ace.FileSystemRights
        if($ace.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
           $ace.InheritanceFlags -ne $flags -or
           $ace.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
           [bool]$ace.IsInherited -eq $protected -or
           ($rights -band $full) -ne $full -or
           ($rights -band (-bnot $full)) -ne 0){Block 'ACL_RIGHTS_CHANGED'}
    }
    foreach($sid in $wanted){if(-not $seen.ContainsKey($sid)){Block 'ACL_REQUIRED_SID_MISSING'}}
}
function SafeFile([string]$path){
    if(-not (Test-Path -LiteralPath $path -PathType Leaf)){Block 'FILE_MISSING'}
    $item=Get-Item -LiteralPath $path -Force
    if(($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0){Block 'FILE_REPARSE'}
    return $item
}
function Sha([byte[]]$bytes){
    $h=[Security.Cryptography.SHA256]::Create()
    try{return [BitConverter]::ToString($h.ComputeHash($bytes)).Replace('-','').ToLowerInvariant()}
    finally{$h.Dispose()}
}
function WriteOnce([string]$path,[byte[]]$bytes){
    $f=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$f.Write($bytes,0,$bytes.Length);$f.Flush($true)}finally{$f.Dispose()}
}
try{
    if($Mode -notin @('check','probe','verify')){Block 'MODE'}
    $who=[Security.Principal.WindowsIdentity]::GetCurrent()
    if($env:COMPUTERNAME -ine 'PREPRESS' -or $who.Name -ine 'PREPRESS\Work' -or
       $who.User.Value -ne $OperatorSid){Block 'IDENTITY_CHANGED'}
    SafeDir $Shared $true
    SafeDir $Root $false
    SafeDir $Jobs $false
    foreach($path in @($Native,(Join-Path $Native 'input'),(Join-Path $Native 'work'))){SafeDir $path $false}
    $nativeZip=SafeFile $NativePkg
    $nativeReceiptFile=SafeFile $NativeReceipt
    if($nativeZip.Length -ne 5120 -or
       (Get-FileHash -LiteralPath $NativePkg -Algorithm SHA256).Hash.ToLowerInvariant() -cne $NativePackageSha -or
       (Get-FileHash -LiteralPath $NativeReceipt -Algorithm SHA256).Hash.ToLowerInvariant() -cne $NativeReceiptSha){
       Block 'STAGED_NATIVE_BINDING_CHANGED'
    }
    $changed=$false
    $duplicateDenied=$false
    $claimSha=$null
    if($Mode -eq 'check' -or $Mode -eq 'probe'){
        if(Test-Path -LiteralPath $Task){Block 'PROBE_TASK_ALREADY_EXISTS_NO_RETRY'}
        $state='READY_FOR_ISOLATED_SYNTHETIC_FENCE_PROBE'
        if($Mode -eq 'probe'){
            foreach($dir in @($Task,$Attempt,$Work)){
                if(Test-Path -LiteralPath $dir){Block 'PARTIAL_PROBE_EXISTS'}
                [void][IO.Directory]::CreateDirectory($dir)
                SafeDir $dir $false
            }
            $record=[ordered]@{
                schema_version='gdl_w27c3g_windows_fence_claim_v0_1'
                state='ISOLATED_SYNTHETIC_FENCE_NO_WORKER_LAUNCH'
                task_id=$ProbeTask;attempt_id=$ProbeAttempt
                native_task_id=$NativeTask;native_attempt_id=$NativeAttempt
                native_package_sha256=$NativePackageSha
                native_receipt_sha256=$NativeReceiptSha
                host='PREPRESS';windows_account='PREPRESS\Work'
                atomic_create_new=$true;duplicate_create_denied=$true
                runner_executed=$false;dispatch_authorized=$false
                execution_authorized=$false;production_ready=$false
                customer_files_touched=$false;cleanup_executed=$false
            }
            $bytes=[Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $record -Compress -Depth 5))
            WriteOnce $Claim $bytes
            $claimSha=Sha ([IO.File]::ReadAllBytes($Claim))
            try{
                $second=[IO.File]::Open($Claim,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
                try{Block 'DUPLICATE_CREATE_UNEXPECTEDLY_SUCCEEDED'}finally{$second.Dispose()}
            }catch [System.IO.IOException]{$duplicateDenied=$true}
            if(-not $duplicateDenied){Block 'DUPLICATE_NOT_DENIED'}
            $changed=$true
            $state='ISOLATED_FENCE_PROBE_WRITTEN_DUPLICATE_DENIED'
        }
    }else{
        foreach($dir in @($Task,$Attempt,$Work)){SafeDir $dir $false}
        $item=SafeFile $Claim
        if($item.Length -lt 200 -or $item.Length -gt 4096){Block 'CLAIM_SIZE_INVALID'}
        $bytes=[IO.File]::ReadAllBytes($Claim)
        $claimSha=Sha $bytes
        if($claimSha -cne $ExpectedProbeSha){Block 'INDEPENDENT_CLAIM_SHA_MISMATCH'}
        $r=[Text.Encoding]::UTF8.GetString($bytes)|ConvertFrom-Json
        $expected=@(
          'schema_version','state','task_id','attempt_id','native_task_id','native_attempt_id',
          'native_package_sha256','native_receipt_sha256','host','windows_account',
          'atomic_create_new','duplicate_create_denied','runner_executed',
          'dispatch_authorized','execution_authorized','production_ready',
          'customer_files_touched','cleanup_executed'
        )
        $names=@($r.PSObject.Properties.Name)
        if($names.Count -ne $expected.Count -or @($expected|Where-Object {$names -cnotcontains $_}).Count -gt 0){Block 'CLAIM_SCHEMA_CHANGED'}
        if($r.schema_version -cne 'gdl_w27c3g_windows_fence_claim_v0_1' -or
           $r.state -cne 'ISOLATED_SYNTHETIC_FENCE_NO_WORKER_LAUNCH' -or
           $r.task_id -cne $ProbeTask -or $r.attempt_id -cne $ProbeAttempt -or
           $r.native_task_id -cne $NativeTask -or $r.native_attempt_id -cne $NativeAttempt -or
           $r.native_package_sha256 -cne $NativePackageSha -or
           $r.native_receipt_sha256 -cne $NativeReceiptSha -or
           $r.host -ne 'PREPRESS' -or $r.windows_account -ne 'PREPRESS\Work' -or
           $r.atomic_create_new -ne $true -or $r.duplicate_create_denied -ne $true -or
           $r.runner_executed -ne $false -or $r.dispatch_authorized -ne $false -or
           $r.execution_authorized -ne $false -or $r.production_ready -ne $false -or
           $r.customer_files_touched -ne $false -or $r.cleanup_executed -ne $false){
           Block 'CLAIM_BINDING_CHANGED'
        }
        $duplicateDenied=$true
        $state='ISOLATED_FENCE_PROBE_SHA_VERIFIED_NOT_EXECUTED'
    }
    $result=[ordered]@{
        schema_version='gdl_w27c3g_windows_fence_probe_report_v0_1'
        mode=$Mode;state=$state;host='PREPRESS';windows_account=$who.Name
        task_id=$ProbeTask;attempt_id=$ProbeAttempt
        native_task_id=$NativeTask;native_attempt_id=$NativeAttempt
        native_package_sha256=$NativePackageSha;native_receipt_sha256=$NativeReceiptSha
        claim_sha256=$claimSha;windows_mutation=$changed
        duplicate_create_denied=$duplicateDenied
        com_attach_performed=$false;jsx_execution=$false;runner_execution=$false
        scheduler_mutated=$false;dispatch_authorized=$false
        execution_authorized=$false;retry_authorized=$false
        production_ready=$false;accepted=$false
        client_files_touched=$false;smb_mutation=$false;cleanup_executed=$false
    }
    [Console]::Out.WriteLine((ConvertTo-Json -InputObject $result -Compress -Depth 6))
    exit 0
}catch{
    [Console]::Error.WriteLine('C3G_BLOCKED:WINDOWS_FENCE_PROBE_FAILED_PRESERVE_EVIDENCE')
    exit 2
}
# NO_AUTOMATIC_CLEANUP. NO_TASK_SCHEDULER. NO_COM. NO_JSX.
