# W2.5 controller via SSH stdin. One new-only synthetic Illustrator native proof.
# NO_AUTOMATIC_CLEANUP. No customer files, no SMB, no retries, no production.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Mode = '__MODE__'
$RunnerB64 = '__RUNNER_B64__'
$JsxB64 = '__JSX_B64__'
$RunnerSha = '__RUNNER_SHA__'
$JsxSha = '__JSX_SHA__'
$TaskName = 'ForPrint-GDL-W2-5-3-Limited-Native-Proof'
$TaskId = 'gdl-w253-limited-native-001'
$AttemptId = 'a0001'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Attempt = Join-Path (Join-Path (Join-Path $Root 'jobs') $TaskId) $AttemptId
$InputDir = Join-Path $Attempt 'input'
$WorkDir = Join-Path $Attempt 'work'
$ExportDir = Join-Path $Attempt 'export'
$RunnerFile = Join-Path $InputDir 'native_runner.ps1'
$JsxFile = Join-Path $InputDir 'native_probe.jsx'
$ResultFile = Join-Path $ExportDir 'native_runner_result.json'
$AiFile = Join-Path $ExportDir 'native_probe.ai'
$ClaimFile = Join-Path $WorkDir 'start_claim.json'
$PsExe = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
function Block([string]$code) { throw ('W253_BLOCKED:' + $code) }
function SafeDir([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return $false }
    $item=Get-Item -LiteralPath $path -Force
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Block 'UNSAFE_PATH_OR_REPARSE'
    }
    return $true
}
function SafeRegular([string]$path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { Block 'MISSING_SOURCE_OR_RESULT' }
    $item=Get-Item -LiteralPath $path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Block 'REPARSE_FILE' }
}
$OperatorSid = 'S-1-5-21-3087849371-1068859030-1179031902-1001'
# Approved GDL W2 local-pilot ACL: SYSTEM/Admin/Work=FullControl (DEV ONLY).
# This is not a portfolio-wide worker ownership or production policy.
function Assert-ApprovedAcl([string]$Path, [bool]$ExpectedProtected) {
    $acl = Get-Acl -LiteralPath $Path -ErrorAction Stop
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne 'S-1-5-32-544') { throw 'W2_ACL_OWNER_CHANGED' }
    if ([bool]$acl.AreAccessRulesProtected -ne $ExpectedProtected) { throw 'W2_ACL_INHERITANCE_MISMATCH' }
    $rules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 3) { throw 'W2_ACL_UNEXPECTED_RULE_COUNT' }
    $expect=@('S-1-5-18','S-1-5-32-544',$OperatorSid)
    $seen=@{}
    $wantFlags = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
    $full = [int][Security.AccessControl.FileSystemRights]::FullControl
    $rx = [int][Security.AccessControl.FileSystemRights]::ReadAndExecute
    $sync = [int][Security.AccessControl.FileSystemRights]::Synchronize
    foreach ($r in $rules) {
        $who=$r.IdentityReference.Value
        if ($expect -notcontains $who -or $seen.ContainsKey($who)) { throw 'W2_ACL_UNEXPECTED_PRINCIPAL' }
        $seen[$who]=$true
        if ($r.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $r.InheritanceFlags -ne $wantFlags -or
            $r.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
            [bool]$r.IsInherited -eq $ExpectedProtected) { throw 'W2_ACL_RULE_FLAGS_UNSAFE' }
        $rights=[int]$r.FileSystemRights
        if ($who -eq $OperatorSid) {
            if (($rights -band $full) -ne $full -or ($rights -band (-bnot $full)) -ne 0) {
                throw 'W2_ACL_OPERATOR_NOT_DEV_FULL'
            }
        } elseif (($rights -band $full) -ne $full -or ($rights -band (-bnot $full)) -ne 0) {
            throw 'W2_ACL_PRIVILEGED_FULL_CONTROL_MISSING'
        }
    }
    foreach ($who in $expect) { if (-not $seen.ContainsKey($who)) { throw 'W2_ACL_REQUIRED_PRINCIPAL_MISSING' } }
    return $true
}
function StrictWorkspace {
    foreach ($p in @('D:\ForPrint_Automation', $Root, (Join-Path $Root 'jobs'))) {
        if (-not (SafeDir $p)) { Block 'WORKSPACE_MISSING' }
        $protected = ($p -eq 'D:\ForPrint_Automation')
        try { [void](Assert-ApprovedAcl $p $protected) }
        catch { Block 'WORKSPACE_ACL_POLICY_MISMATCH' }
    }
}
function InteractiveSession {
    $rows=@(& quser.exe 2>&1 | ForEach-Object { [string]$_ })
    if($LASTEXITCODE -ne 0){ Block 'QUSER_FAILED' }
    $ids=@()
    foreach($line in $rows){
        $m=[regex]::Match($line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b')
        if($m.Success){$ids += [int]$m.Groups[1].Value}
    }
    if($ids.Count -ne 1 -or $ids[0] -le 0){ Block 'NO_UNIQUE_ACTIVE_SESSION' }
    $sid=$ids[0]
    if(@(Get-Process -Name explorer -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $sid}).Count -lt 1){
        Block 'NO_EXPLORER_IN_SESSION'
    }
    if(@(Get-Process -Name Illustrator -ErrorAction SilentlyContinue | Where-Object {$_.SessionId -eq $sid}).Count -ne 1){
        Block 'NO_UNIQUE_ILLUSTRATOR_IN_SESSION'
    }
    return $sid
}
function ActionArgs([int]$sid) {
    return ('-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
      $RunnerFile + '" -ExpectedSessionId ' + $sid)
}
function BoundSources {
    SafeRegular $JsxFile
    SafeRegular $RunnerFile
    if((Get-FileHash -LiteralPath $JsxFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $JsxSha){ Block 'STAGED_JSX_SHA_MISMATCH' }
    if((Get-FileHash -LiteralPath $RunnerFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $RunnerSha){ Block 'STAGED_RUNNER_SHA_MISMATCH' }
}
function BoundTask([int]$sid) {
    $task=Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $user=New-Object Security.Principal.NTAccount($task.Principal.UserId)
    try { $ownerSid=$user.Translate([Security.Principal.SecurityIdentifier]).Value }
    catch { Block 'TASK_OWNER_UNRESOLVED' }
    if($ownerSid -ne [Security.Principal.WindowsIdentity]::GetCurrent().User.Value){ Block 'TASK_OWNER_SID_MISMATCH' }
    if($task.TaskPath -cne '\' -or $task.Actions.Count -ne 1 -or
       [string]$task.Principal.LogonType -ne 'Interactive' -or
       [string]$task.Principal.RunLevel -ne 'Limited' -or
       $task.Actions[0].Execute -ine $PsExe -or
       $task.Actions[0].Arguments -cne (ActionArgs $sid) -or
       @($task.Triggers | Where-Object { $null -ne $_ }).Count -ne 0){ Block 'TASK_METADATA_MISMATCH' }
    return $task
}
function WriteOnce([string]$path, [byte[]]$data) {
    $f=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $f.Write($data,0,$data.Length) } finally { $f.Dispose() }
}
try {
    if($Mode -notin @('check','launch','verify')){ Block 'MODE_INVALID' }
    if($env:COMPUTERNAME -ine 'PREPRESS' -or
      [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work'){ Block 'HOST_USER_INVALID' }
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    if(-not (New-Object Security.Principal.WindowsPrincipal($identity)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
        Block 'ADMIN_TOKEN_REQUIRED'
    }
    StrictWorkspace
    if((Get-Service Schedule).Status -ne 'Running'){ Block 'TASK_SCHEDULER_STOPPED' }
    $bytesRunner=[Convert]::FromBase64String($RunnerB64)
    $bytesJsx=[Convert]::FromBase64String($JsxB64)
    if((Get-FileHash -InputStream ([IO.MemoryStream]::new($bytesRunner)) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $RunnerSha){ Block 'RUNNER_SOURCE_HASH_INVALID' }
    if((Get-FileHash -InputStream ([IO.MemoryStream]::new($bytesJsx)) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $JsxSha){ Block 'JSX_SOURCE_HASH_INVALID' }
    $state='UNSET'
    $sid=$null
    $native=$null
    $changed=$false
    if($Mode -eq 'check' -or $Mode -eq 'launch'){
        $task=Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if($null -ne $task -or (Test-Path -LiteralPath (Join-Path (Join-Path $Root 'jobs') $TaskId))){
            Block 'TASK_EXISTS_NO_RELAUNCH'
        }
        $sid=InteractiveSession
        $state='READY_FOR_LIMITED_NATIVE_PROOF'
        if($Mode -eq 'launch'){
            foreach($p in @((Join-Path (Join-Path $Root 'jobs') $TaskId), $Attempt, $InputDir, $WorkDir, $ExportDir)){
                if(Test-Path -LiteralPath $p){ Block 'PARTIAL_ATTEMPT_EXISTS' }
                [void][IO.Directory]::CreateDirectory($p)
            }
            WriteOnce $JsxFile $bytesJsx
            WriteOnce $RunnerFile $bytesRunner
            BoundSources
            $principal=New-ScheduledTaskPrincipal -UserId 'PREPRESS\Work' -LogonType Interactive -RunLevel Limited
            $action=New-ScheduledTaskAction -Execute $PsExe -Argument (ActionArgs $sid)
            $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 4) -MultipleInstances IgnoreNew
            Register-ScheduledTask -TaskName $TaskName -Principal $principal -Action $action -Settings $settings | Out-Null
            [void](BoundTask $sid)
            $claim=[ordered]@{ task_id=$TaskId; attempt_id=$AttemptId; state='START_REQUESTED_SINGLE_USE'; jsx_sha256=$JsxSha }
            WriteOnce $ClaimFile ([Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json -InputObject $claim -Compress)))
            Start-ScheduledTask -TaskName $TaskName
            $changed=$true
            $state='LIMITED_NATIVE_PROOF_STARTED_RESULT_PENDING'
        }
    } else {
        if(-not (SafeDir $Attempt) -or -not (SafeDir $InputDir) -or
           -not (SafeDir $WorkDir) -or -not (SafeDir $ExportDir)) { Block 'ATTEMPT_TREE_MISSING' }
        BoundSources
        if(-not (Test-Path -LiteralPath $ClaimFile -PathType Leaf)) { Block 'START_CLAIM_MISSING' }
        $task=Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        if(Test-Path -LiteralPath $ResultFile -PathType Leaf){
            SafeRegular $ResultFile
            $native=Get-Content -LiteralPath $ResultFile -Raw -Encoding UTF8 | ConvertFrom-Json
            $sid=[int]$native.session_id
            [void](BoundTask $sid)
            $info=Get-ScheduledTaskInfo -TaskName $TaskName
            if($native.state -eq 'PASS_NATIVE_AI_REOPENED' -and
               $info.LastTaskResult -eq 0 -and [string]$task.State -ne 'Running'){
                SafeRegular $AiFile
                $sha=(Get-FileHash -LiteralPath $AiFile -Algorithm SHA256).Hash.ToLowerInvariant()
                if($sha -ne $native.ai_sha256 -or (Get-Item -LiteralPath $AiFile).Length -ne $native.ai_bytes){
                    Block 'AI_ARTIFACT_HASH_OR_SIZE_CHANGED'
                }
                $state='LIMITED_NATIVE_AI_REOPENED_VERIFIED'
            } else { $state='LIMITED_NATIVE_RESULT_REQUIRES_REVIEW' }
        } else {
            $info=Get-ScheduledTaskInfo -TaskName $TaskName
            if([string]$task.State -eq 'Running' -or $info.LastTaskResult -eq 267011){
                $state='WAITING_FOR_LIMITED_NATIVE_RESULT'
            } else { $state='LIMITED_NATIVE_RESULT_REQUIRES_REVIEW' }
        }
    }
    $doc=[ordered]@{
        schema_version='gdl_windows_w2_5_3_native_controller_v0_1'
        mode=$Mode
        state=$state
        host=$env:COMPUTERNAME
        ssh_account=$identity.Name
        task_name=$TaskName
        task_id=$TaskId
        attempt_id=$AttemptId
        jsx_sha256=$JsxSha
        runner_sha256=$RunnerSha
        session_id=$sid
        windows_mutation=$changed
        smb_mutation=$false
        client_files_touched=$false
        cleanup_executed=$false
        production_ready=$false
        native_result=$native
        scheduler_run_level='Limited'
    }
    Write-Output (ConvertTo-Json -InputObject $doc -Depth 7 -Compress)
    exit 0
} catch {
    $m=[string]$_.Exception.Message
    if(-not $m.StartsWith('W253_BLOCKED:')) { $m='W253_BLOCKED:HOST_OPERATION_FAILED_REVIEW_PARTIAL_EVIDENCE' }
    [Console]::Error.WriteLine($m)
    exit 2
}
