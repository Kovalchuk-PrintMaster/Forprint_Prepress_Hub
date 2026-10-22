# ForPrint W2.4 bounded synthetic GUI Task Scheduler proof controller, PS 5.1.
# Via SSH stdin. This never runs Illustrator, touches SMB or cleans up evidence.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Mode = '__MODE__'
$SourceB64 = '__PAYLOAD_B64__'
$ExpectedSha = '__PAYLOAD_SHA__'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$TaskName = 'ForPrint-GDL-W2-4-GUI-Probe'
$TaskId = 'gdl-w24-gui-probe-001'
$AttemptId = 'a0001'
$AttemptDir = Join-Path (Join-Path (Join-Path $Root 'jobs') $TaskId) $AttemptId
$InputDir = Join-Path $AttemptDir 'input'
$WorkDir = Join-Path $AttemptDir 'work'
$ExportDir = Join-Path $AttemptDir 'export'
$ScriptPath = Join-Path $InputDir 'gui_probe.ps1'
$ResultPath = Join-Path $ExportDir 'gui_probe_result.json'
$ResumeClaimPath = Join-Path $WorkDir 'resume_start_claim.json'
$PowerShellExe = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'

function Stop-Probe([string]$Code) { throw "W2_4_BLOCKED:$Code" }
function Is-DirSafe([string]$p) {
    if (-not (Test-Path -LiteralPath $p)) { return $false }
    $i=Get-Item -LiteralPath $p -Force
    if (-not $i.PSIsContainer -or (($i.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
        Stop-Probe 'TARGET_DIRECTORY_REPARSE_OR_NOT_DIRECTORY'
    }
    return $true
}
$OperatorSid = 'S-1-5-21-3087849371-1068859030-1179031902-1001'
# Approved GDL W2 local-pilot ACL: SYSTEM/Admin=FullControl; Work=ReadAndExecute.
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
            if (($rights -band $rx) -ne $rx -or ($rights -band (-bnot ($rx -bor $sync))) -ne 0) {
                throw 'W2_ACL_OPERATOR_NOT_READ_EXECUTE'
            }
        } elseif (($rights -band $full) -ne $full -or ($rights -band (-bnot $full)) -ne 0) {
            throw 'W2_ACL_PRIVILEGED_FULL_CONTROL_MISSING'
        }
    }
    foreach ($who in $expect) { if (-not $seen.ContainsKey($who)) { throw 'W2_ACL_REQUIRED_PRINCIPAL_MISSING' } }
    return $true
}
function Assert-StrictRoot {
    foreach ($p in @('D:\ForPrint_Automation', $Root, (Join-Path $Root 'jobs'))) {
        if (-not (Is-DirSafe $p)) { Stop-Probe 'WORKSPACE_MISSING' }
        $protected = ($p -eq 'D:\ForPrint_Automation')
        try { [void](Assert-ApprovedAcl $p $protected) }
        catch { Stop-Probe 'WORKSPACE_ACL_POLICY_MISMATCH' }
    }
}
function Active-WorkSession {
    $lines = @(& quser.exe 2>&1 | ForEach-Object { [string]$_ })
    if ($LASTEXITCODE -ne 0) { Stop-Probe 'QUSER_UNAVAILABLE' }
    $sessionIds = @()
    foreach ($line in $lines) {
        $m=[regex]::Match($line,'(?i)^\s*>?\s*work\s+\S+\s+(\d+)\s+Active\b')
        if ($m.Success) { $sessionIds += [int]$m.Groups[1].Value }
    }
    if ($sessionIds.Count -ne 1) { Stop-Probe 'INTERACTIVE_WORK_SESSION_NOT_UNIQUE_OR_NOT_ACTIVE' }
    $sid=$sessionIds[0]
    if ($sid -le 0) { Stop-Probe 'SESSION_ZERO_UNSAFE' }
    $explorer=@(Get-Process -Name explorer -ErrorAction SilentlyContinue |
        Where-Object { $_.SessionId -eq $sid })
    if ($explorer.Count -lt 1) { Stop-Probe 'INTERACTIVE_EXPLORER_NOT_PRESENT' }
    return $sid
}
function Payload-Bytes {
    $bytes=[Convert]::FromBase64String($SourceB64)
    $memory = [IO.MemoryStream]::new($bytes)
    try { $h=[Security.Cryptography.SHA256]::Create(); try {
        $got=[BitConverter]::ToString($h.ComputeHash($memory)).Replace('-','').ToLowerInvariant()
    } finally { $h.Dispose() } } finally { $memory.Dispose() }
    if ($got -ne $ExpectedSha) { Stop-Probe 'PAYLOAD_DIGEST_MISMATCH' }
    return ,$bytes
}
function Action-Args([int]$sid) {
    return ('-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $ScriptPath + '" -ExpectedSessionId ' + $sid)
}
function Task-Metadata([int]$sid) {
    $foundTasks=@(Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop)
    if ($foundTasks.Count -ne 1) { Stop-Probe 'SCHEDULED_TASK_NOT_UNIQUE' }
    $task=$foundTasks[0]
    if ($task.TaskPath -cne '\') { Stop-Probe 'SCHEDULED_TASK_WRONG_PATH' }
    # Task Scheduler may normalize PREPRESS\Work to Work. Check stable SID instead.
    try {
        $owner=New-Object Security.Principal.NTAccount($task.Principal.UserId)
        $taskSid=$owner.Translate([Security.Principal.SecurityIdentifier]).Value
    } catch { Stop-Probe 'SCHEDULED_TASK_OWNER_SID_UNRESOLVED' }
    $expectedSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    if ($taskSid -ne $expectedSid) { Stop-Probe 'SCHEDULED_TASK_OWNER_SID_MISMATCH' }
    if (@($task.Actions).Count -ne 1 -or
        [string]$task.Principal.LogonType -ne 'Interactive' -or
        [string]$task.Principal.RunLevel -ne 'Highest' -or
        $task.Actions[0].Execute -ine $PowerShellExe -or
        $task.Actions[0].Arguments -cne (Action-Args $sid) -or
        @($task.Triggers | Where-Object { $null -ne $_ }).Count -ne 0) { Stop-Probe 'SCHEDULED_TASK_DEFINITION_MISMATCH' }
    return $task
}
function Assert-ExistingUnrunAttempt([int]$sid) {
    if (-not (Is-DirSafe $AttemptDir) -or -not (Is-DirSafe $InputDir) -or
        -not (Is-DirSafe $WorkDir) -or -not (Is-DirSafe $ExportDir)) {
        Stop-Probe 'RESUME_ATTEMPT_TREE_MISSING_OR_UNSAFE'
    }
    if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
        Stop-Probe 'RESUME_STAGED_SCRIPT_MISSING'
    }
    $file=Get-Item -LiteralPath $ScriptPath -Force
    if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        Stop-Probe 'RESUME_STAGED_SCRIPT_REPARSE'
    }
    $got=(Get-FileHash -LiteralPath $ScriptPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($got -ne $ExpectedSha) { Stop-Probe 'RESUME_STAGED_SCRIPT_SHA_MISMATCH' }
    if (Test-Path -LiteralPath $ResultPath) { Stop-Probe 'RESUME_RESULT_ALREADY_PRESENT' }
    if (Test-Path -LiteralPath $ResumeClaimPath) { Stop-Probe 'RESUME_START_ALREADY_CLAIMED' }
    $task=Task-Metadata $sid
    $info=Get-ScheduledTaskInfo -TaskName $TaskName -ErrorAction Stop
    if ([string]$task.State -ne 'Ready' -or
        $info.LastTaskResult -ne 267011 -or
        $info.LastRunTime -ge ([datetime]::new(2000,1,1))) {
        Stop-Probe 'RESUME_TASK_NOT_PROVEN_NEVER_RUN'
    }
    return $task
}
function Claim-ResumeStart([int]$sid) {
    $claim=[ordered]@{
        schema_version='gdl_windows_w2_4_resume_start_claim_v0_1'
        task_name=$TaskName
        task_id=$TaskId
        attempt_id=$AttemptId
        source_sha256=$ExpectedSha
        expected_session_id=$sid
        state='START_REQUESTED_SINGLE_USE'
    }
    $json=ConvertTo-Json -InputObject $claim -Compress -Depth 4
    $bytes=[Text.UTF8Encoding]::new($false).GetBytes($json)
    $file=[IO.File]::Open($ResumeClaimPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $file.Write($bytes,0,$bytes.Length) } finally { $file.Dispose() }
}
try {
    if ($Mode -notin @('check','launch','verify','resume-check','resume-start')) { Stop-Probe 'INVALID_MODE' }
    if ($env:COMPUTERNAME -ine 'PREPRESS' -or
        [Security.Principal.WindowsIdentity]::GetCurrent().Name -ine 'PREPRESS\Work') {
        Stop-Probe 'HOST_OR_ACCOUNT_MISMATCH'
    }
    $admin=(New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { Stop-Probe 'ADMIN_TOKEN_REQUIRED' }
    Assert-StrictRoot
    if ((Get-Service Schedule).Status -ne 'Running') { Stop-Probe 'TASK_SCHEDULER_STOPPED' }
    $bytes=Payload-Bytes
    $task=Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    $exists=(Test-Path -LiteralPath $AttemptDir)
    $state='UNSET'
    $sid=$null
    $result=$null
    $created=$false
    $resumed=$false
    if ($Mode -eq 'check' -or $Mode -eq 'launch') {
        if ($null -ne $task -or $exists) { Stop-Probe 'PILOT_BOUNDARY_EXISTS_USE_VERIFY' }
        $sid=Active-WorkSession
        $state='READY_FOR_SYNTHETIC_TASK'
        if ($Mode -eq 'launch') {
            # Explicitly new-only task/attempt. No deletions, no overwrite, no retry.
            foreach ($p in @((Join-Path (Join-Path $Root 'jobs') $TaskId),$AttemptDir,$InputDir,$WorkDir,$ExportDir)) {
                if (Test-Path -LiteralPath $p) { Stop-Probe 'ATTEMPT_PARTIAL_CREATION_REVIEW' }
                [void][IO.Directory]::CreateDirectory($p)
            }
            $file=[IO.File]::Open($ScriptPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
            try { $file.Write($bytes,0,$bytes.Length) } finally { $file.Dispose() }
            $actual=(Get-FileHash -LiteralPath $ScriptPath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($actual -ne $ExpectedSha) { Stop-Probe 'STAGED_SCRIPT_SHA_MISMATCH' }
            $pr=New-ScheduledTaskPrincipal -UserId 'PREPRESS\Work' -LogonType Interactive -RunLevel Highest
            $ac=New-ScheduledTaskAction -Execute $PowerShellExe -Argument (Action-Args $sid)
            $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -MultipleInstances IgnoreNew
            Register-ScheduledTask -TaskName $TaskName -Principal $pr -Action $ac -Settings $settings | Out-Null
            [void](Task-Metadata $sid)
            $created=$true
            Start-ScheduledTask -TaskName $TaskName
            $state='TASK_STARTED_RESULT_NOT_YET_VERIFIED'
        }
    } elseif ($Mode -in @('resume-check','resume-start')) {
        if ($null -eq $task -or -not $exists) { Stop-Probe 'RESUME_TASK_OR_ATTEMPT_ABSENT' }
        # The task must still target the SAME currently active interactive session.
        $sid=Active-WorkSession
        [void](Assert-ExistingUnrunAttempt $sid)
        $state='READY_TO_RESUME_EXISTING_UNRUN_TASK'
        if ($Mode -eq 'resume-start') {
            # Fail-closed single-use fence: even an SSH timeout cannot restart this attempt.
            Claim-ResumeStart $sid
            $resumed=$true
            Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
            $state='TASK_RESUMED_RESULT_NOT_YET_VERIFIED'
        }
    } else {
        if ($null -eq $task -or -not (Is-DirSafe $AttemptDir) -or
            -not (Is-DirSafe $InputDir) -or -not (Is-DirSafe $WorkDir) -or
            -not (Is-DirSafe $ExportDir)) { Stop-Probe 'PILOT_BOUNDARY_PARTIAL_OR_MISSING' }
        if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) { Stop-Probe 'STAGED_SCRIPT_MISSING' }
        $got=(Get-FileHash -LiteralPath $ScriptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($got -ne $ExpectedSha) { Stop-Probe 'STAGED_SCRIPT_SHA_MISMATCH' }
        if (Test-Path -LiteralPath $ResultPath -PathType Leaf) {
            $result=Get-Content -LiteralPath $ResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $sid=[int]$result.expected_session_id
            [void](Task-Metadata $sid)
            $taskInfo=Get-ScheduledTaskInfo -TaskName $TaskName
            if ($result.state -eq 'PASS_SYNTHETIC_INTERACTIVE' -and
                $taskInfo.LastTaskResult -eq 0 -and [string]$task.State -ne 'Running') {
                $state='SYNTHETIC_GUI_RESULT_REPORTED'
            } else { $state='SYNTHETIC_GUI_RESULT_REQUIRES_REVIEW' }
        } else {
            $state='WAITING_FOR_SYNTHETIC_RESULT'
        }
    }
    $doc=[ordered]@{
        schema_version='gdl_windows_w2_4_controller_report_v0_1'
        mode=$Mode
        state=$state
        host=$env:COMPUTERNAME
        ssh_account=[Security.Principal.WindowsIdentity]::GetCurrent().Name
        task_name=$TaskName
        task_id=$TaskId
        attempt_id=$AttemptId
        expected_source_sha256=$ExpectedSha
        session_id=$sid
        registered_and_started=$created
        resumed_existing=$resumed
        windows_mutation=[bool]($created -or $resumed)
        illustrator_execution=$false
        smb_mutation=$false
        client_files_touched=$false
        cleanup_executed=$false
        production_ready=$false
        gui_result=$result
    }
    Write-Output (ConvertTo-Json -InputObject $doc -Depth 7 -Compress)
    exit 0
} catch {
    $m=[string]$_.Exception.Message
    if (-not $m.StartsWith('W2_4_BLOCKED:')) { $m='W2_4_BLOCKED:HOST_OPERATION_FAILED_REVIEW_PARTIAL_EVIDENCE' }
    [Console]::Error.WriteLine($m)
    exit 2
}
# W2.4: no automatic cleanup / no client SMB / no Illustrator startup.
