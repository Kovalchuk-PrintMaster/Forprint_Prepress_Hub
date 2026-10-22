# ForPrint GDL W2.3 local workspace: explicit single-host, new-only guarded initialization.
# PowerShell 5.1, Windows only. No private assets, no SMB, no GUI, no cleanup.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Mode = '__FORPRINT_W2_3_MODE__'
$Root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$Shared = 'D:\ForPrint_Automation'
$Lab = 'D:\ForPrint_Automation\GraficsDesignLab'
$Dirs = @('runtime','jobs','cache','logs','config')
$All = @($Shared, $Lab, $Root) + @($Dirs | ForEach-Object { Join-Path $Root $_ })
$AllowedSids = @('S-1-5-18', 'S-1-5-32-544', 'S-1-5-21-3087849371-1068859030-1179031902-1001')

function Block([string]$Reason) {
    throw "W2_3_BLOCKED:$Reason"
}

function Check-Path([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.PSIsContainer) { Block 'NON_DIRECTORY_IN_TARGET_TREE' }
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { Block 'REPARSE_POINT_IN_TARGET_TREE' }
    return $true
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
function Test-StrictAcl([string]$Path, [bool]$ExpectedProtected) {
    return (Assert-ApprovedAcl $Path $ExpectedProtected)
}

function New-StrictRootAcl {
    $acl = New-Object System.Security.AccessControl.DirectorySecurity
    $acl.SetAccessRuleProtection($true, $false)
    $inherit = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
    foreach ($sidString in $AllowedSids) {
        $sid = [Security.Principal.SecurityIdentifier]::new($sidString)
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $sid,
            [Security.AccessControl.FileSystemRights]::FullControl,
            $inherit,
            [Security.AccessControl.PropagationFlags]::None,
            [Security.AccessControl.AccessControlType]::Allow
        )
        $acl.AddAccessRule($rule)
    }
    return $acl
}

try {
    if ($Mode -notin @('check', 'initialize')) { Block 'INVALID_MODE' }
    if ($env:COMPUTERNAME -ine 'PREPRESS') { Block 'UNEXPECTED_HOST' }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    if ($identity.Name -ine 'PREPRESS\Work') { Block 'UNEXPECTED_WINDOWS_IDENTITY' }
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { Block 'ADMIN_TOKEN_REQUIRED' }
    $volume = Get-Volume -DriveLetter D -ErrorAction Stop
    if ($volume.FileSystem -ne 'NTFS' -or $volume.SizeRemaining -lt 10737418240) { Block 'NTFS_OR_FREE_SPACE_REQUIREMENT' }
    if (-not (Check-Path 'D:\')) { Block 'D_DRIVE_ABSENT' }
    $existing = @($All | Where-Object { Check-Path $_ })
    $status = $null
    $createdNow = $false
    if ($existing.Count -eq 0) {
        $status = 'READY_TO_INITIALIZE'
        if ($Mode -eq 'initialize') {
            # Create the FIRST new directory atomically with a protected ACL.
            # Directory.CreateDirectory(path, DirectorySecurity) applies its ACL on creation.
            [void][IO.Directory]::CreateDirectory($Shared, (New-StrictRootAcl))
            [void](Test-StrictAcl $Shared $true)
            foreach ($p in @($Lab,$Root) + @($Dirs | ForEach-Object { Join-Path $Root $_ })) {
                [void][IO.Directory]::CreateDirectory($p)
            }
            $createdNow = $true
        }
    } elseif ($existing.Count -eq $All.Count) {
        $status = 'ALREADY_INITIALIZED_SAFE'
    } else {
        Block 'PARTIAL_TREE_REVIEW_REQUIRED'
    }
    if ($existing.Count -eq $All.Count -or $createdNow) {
        foreach ($p in $All) { [void](Check-Path $p) }
        [void](Test-StrictAcl $Shared $true)
        foreach ($p in $All | Select-Object -Skip 1) { [void](Test-StrictAcl $p $false) }
        if ($createdNow) { $status = 'INITIALIZED_SAFE' }
    }
    $out = [ordered]@{
        schema_version = 'gdl_windows_w2_3_workspace_report_v0_1'
        mode = $Mode
        state = $status
        root = $Root
        host = $env:COMPUTERNAME
        ssh_account = $identity.Name
        directory_count = $All.Count
        windows_mutation = $createdNow
        smb_mutation = $false
        client_files_touched = $false
        illustrator_execution = $false
        cleanup_executed = $false
        production_ready = $false
    }
    Write-Output (ConvertTo-Json -InputObject $out -Depth 5 -Compress)
    exit 0
} catch {
    # Do not expose raw Windows trace, credentials or private paths.
    $message = [string]$_.Exception.Message
    if ($message -notlike 'W2_3_BLOCKED:*') { $message = 'W2_3_BLOCKED:HOST_OPERATION_FAILED_OR_PARTIAL_REVIEW_REQUIRED' }
    [Console]::Error.WriteLine($message)
    exit 2
}

# NO_AUTOMATIC_DELETE_SENTINEL: never remove files or directories in this stage.
