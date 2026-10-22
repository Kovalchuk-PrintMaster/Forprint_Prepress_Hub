# W2.5.1 standalone diagnostic controller over SSH stdin; never executes JSX.
# NO_AUTOMATIC_CLEANUP, no customer/SMB/files outside an isolated attempt.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Mode = '__MODE__'
$RunnerB64 = '__RUNNER_B64__'
$RunnerSha = '__RUNNER_SHA__'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$TaskName = 'ForPrint-GDL-W2-5-1-COM-Attach-Probe'
$TaskId = 'gdl-w251-com-attach-001'
$AttemptId = 'a0001'
$Attempt = Join-Path (Join-Path (Join-Path $Root 'jobs') $TaskId) $AttemptId
$InputDir = Join-Path $Attempt 'input'
$WorkDir = Join-Path $Attempt 'work'
$ExportDir = Join-Path $Attempt 'export'
$RunnerFile = Join-Path $InputDir 'com_attach_runner.ps1'
$ClaimFile = Join-Path $WorkDir 'launch_claim.json'
$ResultFile = Join-Path $ExportDir 'com_attach_result.json'
$PsExe = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$OperatorSid = 'S-1-5-21-3087849371-1068859030-1179031902-1001'
function Block([string]$code) { throw ('W251_BLOCKED:' + $code) }
function SafeDir([string]$path) {
    if(-not (Test-Path -LiteralPath $path -PathType Container)) { return $false }
    $i=Get-Item -LiteralPath $path -Force
    if(($i.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Block 'REPARSE_DIRECTORY' }
    return $true
}
function SafeFile([string]$path) {
    if(-not (Test-Path -LiteralPath $path -PathType Leaf)) { Block 'EXPECTED_FILE_MISSING' }
    $i=Get-Item -LiteralPath $path -Force
    if(($i.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Block 'REPARSE_FILE' }
}
function Assert-ApprovedAcl([string]$Path,[bool]$ExpectedProtected) {
    $acl=Get-Acl -LiteralPath $Path -ErrorAction Stop
    if($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne 'S-1-5-32-544') { Block 'ACL_OWNER_CHANGED' }
    if([bool]$acl.AreAccessRulesProtected -ne $ExpectedProtected) { Block 'ACL_PROTECTION_CHANGED' }
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if($rules.Count -ne 3) { Block 'ACL_RULE_COUNT' }
    $seen=@{}
    $want=@('S-1-5-18','S-1-5-32-544',$OperatorSid)
    $flags = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
    $full = [int][Security.AccessControl.FileSystemRights]::FullControl
    $rx = [int][Security.AccessControl.FileSystemRights]::ReadAndExecute
    $sync = [int][Security.AccessControl.FileSystemRights]::Synchronize
    foreach($r in $rules) {
        $who=$r.IdentityReference.Value
        if($want -notcontains $who -or $seen.ContainsKey($who)) { Block 'ACL_PRINCIPAL_UNEXPECTED' }
        $seen[$who]=$true
        if($r.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
           $r.InheritanceFlags -ne $flags -or
           $r.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
           [bool]$r.IsInherited -eq $ExpectedProtected) { Block 'ACL_FLAGS_UNEXPECTED' }
        $rights=[int]$r.FileSystemRights
        if($who -eq $OperatorSid) {
            if(($rights -band $full) -ne $full -or ($rights -band (-bnot $full)) -ne 0) { Block 'ACL_OPERATOR_NOT_DEV_FULL' }
        } elseif(($rights -band $full) -ne $full -or ($rights -band (-bnot $full)) -ne 0) {
            Block 'ACL_ADMIN_OR_SYSTEM_NOT_FULL'
        }
    }
    foreach($who in $want) { if(-not $seen.ContainsKey($who)) { Block 'ACL_SID_MISSING' } }
}
function StrictWorkspace {
    foreach($p in @('D:\ForPrint_Automation', $Root, (Join-Path $Root 'jobs'))) {
        if(-not (SafeDir $p)) { Block 'WORKSPACE_MISSING' }
        Assert-ApprovedAcl $p ($p -eq 'D:\ForPrint_Automation')
    }
}
function Active-WorkSession {
    $rows=@(& quser.exe 2>&1 | ForEach-Object {[string]$_})
    if($LASTEXITCODE -ne 0) { Block 'QUSER_FAILED' }
    $ids=@()
    foreach($line in $rows) {
        $m=[regex]::Match($line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b')
        if($m.Success) { $ids += [int]$m.Groups[1].Value }
    }
    if($ids.Count -ne 1 -or $ids[0] -le 0) { Block 'NO_UNIQUE_ACTIVE_WORK_SESSION' }
    $sid=$ids[0]
    if(@(Get-Process -Name explorer -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $sid}).Count -lt 1) {
        Block 'EXPLORER_NOT_PRESENT'
    }
    if(@(Get-Process -Name Illustrator -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $sid}).Count -ne 1) {
        Block 'ILLUSTRATOR_NOT_UNIQUE'
    }
    return $sid
}
function ActionArgs([int]$sid) {
    return '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $RunnerFile + '" -ExpectedSessionId ' + $sid
}
function BoundTask([int]$sid) {
    $task=Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    try {
        $u=New-Object Security.Principal.NTAccount($task.Principal.UserId)
        $taskSid=$u.Translate([Security.Principal.SecurityIdentifier]).Value
    } catch { Block 'SCHEDULER_IDENTITY_UNRESOLVED' }
    if($taskSid -ne [Security.Principal.WindowsIdentity]::GetCurrent().User.Value) { Block 'SCHEDULER_SID_MISMATCH' }
    if($task.TaskPath -cne '\' -or @($task.Actions).Count -ne 1 -or
       [string]$task.Principal.LogonType -ne 'Interactive' -or
       [string]$task.Principal.RunLevel -ne 'Highest' -or
       $task.Actions[0].Execute -ine $PsExe -or
       $task.Actions[0].Arguments -cne (ActionArgs $sid) -or
       @($task.Triggers | Where-Object {$null -ne $_}).Count -ne 0) { Block 'SCHEDULER_TASK_DEFINITION_CHANGED' }
    return $task
}
function WriteOnce([string]$path,[byte[]]$data) {
    $f=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $f.Write($data,0,$data.Length) } finally { $f.Dispose() }
}
try {
    if($Mode -notin @('check','launch','verify')) { Block 'MODE_INVALID' }
    if($env:COMPUTERNAME -ine 'PREPRESS' -or
       [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work') { Block 'HOST_USER_MISMATCH' }
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    $principal=New-Object Security.Principal.WindowsPrincipal($identity)
    if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Block 'ADMIN_TOKEN_REQUIRED' }
    StrictWorkspace
    if((Get-Service Schedule).Status -ne 'Running') { Block 'SCHEDULER_STOPPED' }
    $bytes=[Convert]::FromBase64String($RunnerB64)
    $got=(Get-FileHash -InputStream ([IO.MemoryStream]::new($bytes)) -Algorithm SHA256).Hash.ToLowerInvariant()
    if($got -ne $RunnerSha) { Block 'RUNNER_BYTES_CHANGED' }
    $sid=$null
    $changed=$false
    $result=$null
    if($Mode -in @('check','launch')) {
        $existing=Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if($null -ne $existing -or (Test-Path -LiteralPath (Join-Path (Join-Path $Root 'jobs') $TaskId))) {
            Block 'TASK_EXISTS_NO_RELAUNCH'
        }
        $sid=Active-WorkSession
        $state='READY_FOR_COM_ATTACH_PROBE'
        if($Mode -eq 'launch') {
            # New-only bounded attempt. Partial success => preserve evidence; no retry.
            foreach($p in @((Join-Path (Join-Path $Root 'jobs') $TaskId),$Attempt,$InputDir,$WorkDir,$ExportDir)) {
                if(Test-Path -LiteralPath $p) { Block 'PARTIAL_ATTEMPT_EXISTS' }
                [void][IO.Directory]::CreateDirectory($p)
            }
            WriteOnce $RunnerFile $bytes
            SafeFile $RunnerFile
            if((Get-FileHash -LiteralPath $RunnerFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $RunnerSha) {
                Block 'STAGED_RUNNER_CHANGED'
            }
            $pr=New-ScheduledTaskPrincipal -UserId 'PREPRESS\Work' -LogonType Interactive -RunLevel Highest
            $ac=New-ScheduledTaskAction -Execute $PsExe -Argument (ActionArgs $sid)
            $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
            Register-ScheduledTask -TaskName $TaskName -Principal $pr -Action $ac -Settings $settings | Out-Null
            [void](BoundTask $sid)
            $claim=[ordered]@{schema_version='gdl_w251_start_claim_v0_1';task_id=$TaskId;
                attempt_id=$AttemptId;runner_sha256=$RunnerSha;session_id=$sid;state='SINGLE_USE_START_REQUESTED'}
            WriteOnce $ClaimFile ([Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $claim -Compress)))
            Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
            $changed=$true
            $state='COM_ATTACH_TASK_STARTED_RESULT_PENDING'
        }
    } else {
        if(-not (SafeDir $Attempt) -or -not (SafeDir $InputDir) -or -not (SafeDir $WorkDir) -or
           -not (SafeDir $ExportDir)) { Block 'ATTEMPT_TREE_MISSING' }
        SafeFile $RunnerFile
        SafeFile $ClaimFile
        if((Get-FileHash -LiteralPath $RunnerFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $RunnerSha) {
            Block 'STAGED_RUNNER_HASH_MISMATCH'
        }
        $claim=Get-Content -LiteralPath $ClaimFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if($claim.task_id -ne $TaskId -or $claim.attempt_id -ne $AttemptId -or
           $claim.runner_sha256 -ne $RunnerSha) { Block 'START_CLAIM_MISMATCH' }
        $task=Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $info=Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
        if(Test-Path -LiteralPath $ResultFile) {
            SafeFile $ResultFile
            $result=Get-Content -LiteralPath $ResultFile -Raw -Encoding UTF8 | ConvertFrom-Json
            $sid=[int]$result.session_id
            [void](BoundTask $sid)
            if($result.state -eq 'PASS_COM_READONLY_ATTACH' -and $info.LastTaskResult -eq 0 -and
                [string]$task.State -ne 'Running') {
                $state='COM_READONLY_ATTACH_VERIFIED'
            } else { $state='COM_ATTACH_REQUIRES_REVIEW' }
        } else {
            $sid=[int]$claim.session_id
            [void](BoundTask $sid)
            if([string]$task.State -eq 'Running' -or $info.LastTaskResult -eq 267011) {
                $state='WAITING_FOR_COM_ATTACH_RESULT'
            } else { $state='COM_ATTACH_REQUIRES_REVIEW' }
        }
    }
    $doc=[ordered]@{
        schema_version='gdl_windows_w2_5_1_com_attach_controller_v0_1';mode=$Mode;state=$state
        host=$env:COMPUTERNAME;ssh_account=$identity.Name;task_name=$TaskName
        task_id=$TaskId;attempt_id=$AttemptId;runner_sha256=$RunnerSha
        session_id=$sid;windows_mutation=$changed;com_result=$result
        illustrator_document_mutation=$false;smb_mutation=$false;client_files_touched=$false
        cleanup_executed=$false;production_ready=$false
    }
    Write-Output (ConvertTo-Json -InputObject $doc -Compress -Depth 8)
    exit 0
} catch {
    $e=[string]$_.Exception.Message
    if(-not $e.StartsWith('W251_BLOCKED:')) { $e='W251_BLOCKED:REMOTE_OPERATION_FAILED_REVIEW_PARTIAL_EVIDENCE' }
    [Console]::Error.WriteLine($e)
    exit 2
}
