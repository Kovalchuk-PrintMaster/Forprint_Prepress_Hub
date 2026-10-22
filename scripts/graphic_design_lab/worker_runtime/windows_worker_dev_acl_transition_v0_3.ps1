# GDL DEVELOPMENT ONLY. Migrate the existing protected Windows worker root RX -> Work FullControl.
# No SMB, other drives, client content, Task Scheduler writes, or cleanup. Single parent DACL write.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Mode = '__DEV_ACL_MODE__'
$Shared = 'D:\ForPrint_Automation'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$OperatorSid = 'S-1-5-21-3087849371-1068859030-1179031902-1001'
$SysSid = 'S-1-5-18'
$AdminSid = 'S-1-5-32-544'
$Dirs = @($Shared, (Join-Path $Shared 'GraficsDesignLab'), $Root) + @(
    'runtime','jobs','cache','logs','config' | ForEach-Object { Join-Path $Root $_ })
$Flags = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
$Full = [int][Security.AccessControl.FileSystemRights]::FullControl
$Rx = [int][Security.AccessControl.FileSystemRights]::ReadAndExecute
$Sync = [int][Security.AccessControl.FileSystemRights]::Synchronize
function Block([string]$why) { throw ('W2_DEV_ACL_BLOCKED:' + $why) }
function Inspect-Path([string]$path, [bool]$protected) {
    $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Block 'PATH_UNSAFE_OR_NOT_DIRECTORY'
    }
    $acl = Get-Acl -LiteralPath $path -ErrorAction Stop
    if ($acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -ne $AdminSid -or
        [bool]$acl.AreAccessRulesProtected -ne $protected) { Block 'OWNER_OR_INHERITANCE_CHANGED' }
    $rules = @($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 3) { Block 'ACL_RULE_COUNT_UNEXPECTED' }
    $seen = @{}
    $workRule = $null
    $mode = $null
    foreach ($r in $rules) {
        $sid = $r.IdentityReference.Value
        if ($sid -notin @($SysSid,$AdminSid,$OperatorSid) -or $seen.ContainsKey($sid)) {
            Block 'UNEXPECTED_OR_DUPLICATE_PRINCIPAL'
        }
        $seen[$sid] = $true
        if ($r.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $r.InheritanceFlags -ne $Flags -or
            $r.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
            ([bool]$r.IsInherited -eq $protected)) { Block 'ACL_FLAGS_UNEXPECTED' }
        $rights = [int]$r.FileSystemRights
        if ($sid -ne $OperatorSid) {
            if ($rights -ne $Full) { Block 'SYSTEM_OR_ADMIN_NOT_FULL' }
        } else {
            $workRule = $r
            if ($rights -eq $Full) { $mode = 'DEV_FULL' }
            elseif (($rights -band $Rx) -eq $Rx -and ($rights -band (-bnot ($Rx -bor $Sync))) -eq 0) {
                $mode = 'CURRENT_RX'
            } else { Block 'OPERATOR_ACCESS_UNRECOGNIZED' }
        }
    }
    if ($seen.Count -ne 3 -or $null -eq $workRule) { Block 'ACL_REQUIRED_PRINCIPAL_ABSENT' }
    return [pscustomobject]@{ path=$path; mode=$mode; work_rule=$workRule; acl=$acl }
}
function Inspect-Tree {
    $rows = @()
    for ($i=0; $i -lt $Dirs.Count; $i++) { $rows += Inspect-Path $Dirs[$i] ($i -eq 0) }
    if ($rows.Count -ne 8) { Block 'TREE_COUNT_UNEXPECTED' }
    $modes = @($rows | Select-Object -ExpandProperty mode -Unique)
    if ($modes.Count -ne 1) { Block 'MIXED_ACL_TREE_REVIEW_REQUIRED' }
    return [pscustomobject]@{ rows=$rows; mode=$modes[0] }
}
try {
    if ($Mode -notin @('check','apply')) { Block 'MODE_NOT_ALLOWED' }
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    if ($env:COMPUTERNAME -ine 'PREPRESS' -or $id.Name -ine 'PREPRESS\Work' -or
        $id.User.Value -ne $OperatorSid) { Block 'HOST_OR_SID_UNEXPECTED' }
    if (-not (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)) { Block 'ELEVATED_ADMIN_REQUIRED' }
    foreach ($taskName in @('ForPrint-GDL-W2-4-GUI-Probe',
          'ForPrint-GDL-W2-5-Illustrator-Probe','ForPrint-GDL-W2-5-1-COM-Attach-Probe',
          'ForPrint-GDL-W2-5-2-Limited-COM-Attach')) {
        $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($null -ne $task -and [string]$task.State -eq 'Running') { Block 'EXISTING_PROBE_STILL_RUNNING' }
    }
    $before = Inspect-Tree
    $prior = $before.mode
    $changed = $false
    if ($Mode -eq 'apply') {
        if ($prior -ne 'CURRENT_RX') { Block 'APPLY_REQUIRES_EXACT_CURRENT_RX_STATE' }
        $parent = $before.rows[0]
        $acl = $parent.acl
        $acl.RemoveAccessRuleSpecific($parent.work_rule)
        $new = [Security.AccessControl.FileSystemAccessRule]::new(
            [Security.Principal.SecurityIdentifier]::new($OperatorSid),
            [Security.AccessControl.FileSystemRights]::FullControl, $Flags,
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow)
        [void]$acl.AddAccessRule($new)
        Set-Acl -LiteralPath $Shared -AclObject $acl -ErrorAction Stop
        $changed = $true
    }
    $after = Inspect-Tree
    if ($Mode -eq 'apply' -and $after.mode -ne 'DEV_FULL') { Block 'POST_APPLY_NOT_DEV_FULL' }
    if ($Mode -eq 'check' -and $after.mode -ne $prior) { Block 'READ_ONLY_RACE_DETECTED' }
    $state = if ($after.mode -eq 'DEV_FULL') {'DEV_FULL_CONTROL_VERIFIED'} else {'READY_FOR_DEV_FULL_CONTROL'}
    $report = [ordered]@{
        schema_version='gdl_windows_worker_dev_acl_transition_v0_3'
        policy_id='gdl_windows_operator_full_control_dev_v0_3'
        mode=$Mode; state=$state; previous_state=$prior
        host=$env:COMPUTERNAME; ssh_account=$id.Name
        boundary=$Shared; gdl_root=$Root; directories_checked=$after.rows.Count
        operator_sid_verified=$true; root_inheritance_protected=$true
        windows_mutation=$changed; scheduled_tasks_mutated=$false
        client_files_touched=$false; smb_mutation=$false; illustrator_execution=$false
        cleanup_executed=$false; production_ready=$false
    }
    Write-Output (ConvertTo-Json -InputObject $report -Compress -Depth 4)
    exit 0
} catch {
    $msg = [string]$_.Exception.Message
    if (-not $msg.StartsWith('W2_DEV_ACL_BLOCKED:')) {
        $msg = 'W2_DEV_ACL_BLOCKED:OPERATION_FAILED_INSPECT_BEFORE_RETRY'
    }
    [Console]::Error.WriteLine($msg)
    exit 2
}
# NO_AUTOMATIC_CLEANUP. NO_SMB_CHANGES. NO_SCHEDULED_TASK_CHANGES.
