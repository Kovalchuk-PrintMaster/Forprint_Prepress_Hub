# GDL W2 operator ACL migration, isolated root DACL only. No task or client mutations.
# Source is delivered over SSH stdin. Check first, apply only after exact confirmation.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Mode = '__ACL_MODE__'
$Shared = 'D:\ForPrint_Automation'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$OperatorSid = 'S-1-5-21-3087849371-1068859030-1179031902-1001'
$Names = @($Shared, (Join-Path $Shared 'GraficsDesignLab'), $Root) + @(
    'runtime','jobs','cache','logs','config' | ForEach-Object { Join-Path $Root $_ })
$SysSid = 'S-1-5-18'
$AdminSid = 'S-1-5-32-544'
$WantFlags = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
$Full = [int][Security.AccessControl.FileSystemRights]::FullControl
$Rx = [int][Security.AccessControl.FileSystemRights]::ReadAndExecute
$Sync = [int][Security.AccessControl.FileSystemRights]::Synchronize

function Block([string]$reason) { throw ('W2_ACL_BLOCKED:' + $reason) }
function SameRights([int]$actual, [int]$required, [int]$allowed) {
    return (($actual -band $required) -eq $required -and ($actual -band (-bnot $allowed)) -eq 0)
}
function Inspect-Dir([string]$p, [bool]$protected) {
    if (-not (Test-Path -LiteralPath $p -PathType Container)) { Block 'DIRECTORY_MISSING' }
    $item = Get-Item -LiteralPath $p -Force
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { Block 'DIRECTORY_UNSAFE' }
    $acl=Get-Acl -LiteralPath $p -ErrorAction Stop
    $owner=$acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
    if ($owner -ne $AdminSid) { Block 'OWNER_CHANGED' }
    if ([bool]$acl.AreAccessRulesProtected -ne $protected) { Block 'INHERITANCE_CHANGED' }
    $rules=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
    if ($rules.Count -ne 3) { Block 'ACE_COUNT_UNEXPECTED' }
    $seen=@{}
    $operatorIsFull=$false
    $operatorIsRx=$false
    $operatorRule=$null
    foreach ($r in $rules) {
        $who=$r.IdentityReference.Value
        if ($who -notin @($SysSid,$AdminSid,$OperatorSid) -or $seen.ContainsKey($who)) { Block 'SID_UNEXPECTED_OR_DUPLICATED' }
        $seen[$who]=$true
        if ($r.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow -or
            $r.InheritanceFlags -ne $WantFlags -or
            $r.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None -or
            [bool]$r.IsInherited -eq $protected) { Block 'ACE_FLAGS_UNEXPECTED' }
        $rights=[int]$r.FileSystemRights
        if ($who -eq $OperatorSid) {
            $operatorRule=$r
            $operatorIsFull=SameRights $rights $Full $Full
            $operatorIsRx=SameRights $rights $Rx ($Rx -bor $Sync)
            if (-not $operatorIsFull -and -not $operatorIsRx) { Block 'OPERATOR_RIGHTS_UNEXPECTED' }
        } elseif (-not (SameRights $rights $Full $Full)) { Block 'PRIVILEGED_RIGHTS_UNEXPECTED' }
    }
    foreach ($sid in @($SysSid,$AdminSid,$OperatorSid)) {
        if (-not $seen.ContainsKey($sid)) { Block 'REQUIRED_SID_ABSENT' }
    }
    return [pscustomobject]@{
        path=$p
        state=$(if ($operatorIsFull) {'LEGACY_OPERATOR_FULL_CONTROL'} else {'OPERATOR_READ_EXECUTE'})
        acl=$acl
        operator_rule=$operatorRule
    }
}
function Inspect-Tree {
    $rows=@()
    for ($j=0; $j -lt $Names.Count; $j++) {
        $rows+=Inspect-Dir $Names[$j] ($j -eq 0)
    }
    if ($rows.Count -ne 8) { Block 'DIRECTORY_COUNT_CHANGED' }
    $states=@($rows | Select-Object -ExpandProperty state -Unique)
    if ($states.Count -ne 1) { Block 'MIXED_ACL_REVIEW_REQUIRED' }
    return [pscustomobject]@{state=$states[0];rows=$rows}
}
try {
    if ($Mode -notin @('check','apply')) { Block 'MODE_INVALID' }
    $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
    if ($env:COMPUTERNAME -ine 'PREPRESS' -or
        $identity.Name -ine 'PREPRESS\Work' -or
        $identity.User.Value -ne $OperatorSid) { Block 'HOST_OR_OPERATOR_IDENTITY_CHANGED' }
    $principal=New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Block 'ADMIN_TOKEN_REQUIRED' }
    # ACL transition is forbidden while a W2 pilot task is running or if a W2.5
    # attempt was already admitted since its last read-only preflight.
    $w24=Get-ScheduledTask -TaskName 'ForPrint-GDL-W2-4-GUI-Probe' -ErrorAction SilentlyContinue
    if ($null -ne $w24 -and [string]$w24.State -eq 'Running') { Block 'W24_TASK_STILL_RUNNING' }
    $w25=Get-ScheduledTask -TaskName 'ForPrint-GDL-W2-5-Illustrator-Probe' -ErrorAction SilentlyContinue
    if ($null -ne $w25 -or (Test-Path -LiteralPath (Join-Path (Join-Path $Root 'jobs') 'gdl-w25-illustrator-native-001'))) {
        Block 'W25_ATTEMPT_ALREADY_PRESENT'
    }
    $before=Inspect-Tree
    $prior=$before.state
    $changed=$false
    if ($Mode -eq 'apply') {
        if ($prior -ne 'LEGACY_OPERATOR_FULL_CONTROL') { Block 'MIGRATION_NOT_IN_EXPECTED_LEGACY_STATE' }
        # The only write: remove the exact operator FULL ACE and add its RX replacement
        # on the protected shared root. All child ACEs must remain inherited.
        $parent=$before.rows[0]
        $acl=$parent.acl
        $acl.RemoveAccessRuleSpecific($parent.operator_rule)
        $newAce=[Security.AccessControl.FileSystemAccessRule]::new(
            [Security.Principal.SecurityIdentifier]::new($OperatorSid),
            [Security.AccessControl.FileSystemRights]::ReadAndExecute,
            $WantFlags,
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow)
        $acl.AddAccessRule($newAce)
        Set-Acl -LiteralPath $Shared -AclObject $acl -ErrorAction Stop
        $changed=$true
    }
    $after=Inspect-Tree
    if ($Mode -eq 'apply' -and $after.state -ne 'OPERATOR_READ_EXECUTE') { Block 'POST_MIGRATION_POLICY_NOT_REACHED' }
    if ($Mode -eq 'check' -and $prior -ne $after.state) { Block 'READ_ONLY_CHECK_DETECTED_RACE' }
    $state=if ($after.state -eq 'OPERATOR_READ_EXECUTE') {
        'OPERATOR_READ_EXECUTE_VERIFIED'
    } else { 'READY_FOR_LEAST_PRIVILEGE_MIGRATION' }
    $out=[ordered]@{
        schema_version='gdl_windows_worker_acl_migration_v0_2'
        policy_id='gdl_windows_operator_read_execute_v0_2'
        mode=$Mode
        state=$state
        prior_state=$prior
        host=$env:COMPUTERNAME
        ssh_account=$identity.Name
        root=$Root
        directories_checked=$after.rows.Count
        root_inheritance_protected=$true
        operator_sid_verified=$true
        windows_mutation=$changed
        client_files_touched=$false
        scheduled_tasks_mutated=$false
        smb_mutation=$false
        illustrator_execution=$false
        cleanup_executed=$false
        production_ready=$false
    }
    Write-Output (ConvertTo-Json -InputObject $out -Depth 4 -Compress)
    exit 0
} catch {
    $message=[string]$_.Exception.Message
    if (-not $message.StartsWith('W2_ACL_BLOCKED:')) { $message='W2_ACL_BLOCKED:ACL_OPERATION_FAILED_INSPECT_BEFORE_ANY_RETRY' }
    [Console]::Error.WriteLine($message)
    exit 2
}
# NO_AUTOMATIC_CLEANUP. No recursive chmod, no broad icacls, no ACL Reset.
