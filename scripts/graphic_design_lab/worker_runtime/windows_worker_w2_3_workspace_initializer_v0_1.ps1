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
$AllowedSids = @('S-1-5-18', 'S-1-5-32-544')

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

function Test-StrictAcl([string]$Path, [bool]$ExpectedProtected) {
    $acl = Get-Acl -LiteralPath $Path
    if ([bool]$acl.AreAccessRulesProtected -ne $ExpectedProtected) { Block 'ACL_INHERITANCE_UNEXPECTED' }
    $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    if ($rules.Count -eq 0) { Block 'ACL_RULES_EMPTY' }
    foreach ($rule in $rules) {
        if ($AllowedSids -notcontains $rule.IdentityReference.Value) { Block 'ACL_UNEXPECTED_PRINCIPAL' }
        if ($rule.AccessControlType -ne [Security.AccessControl.AccessControlType]::Allow) { Block 'ACL_UNEXPECTED_DENY' }
    }
    foreach ($sid in $AllowedSids) {
        $found = @($rules | Where-Object {
            $_.IdentityReference.Value -eq $sid -and
            (($_.FileSystemRights -band [Security.AccessControl.FileSystemRights]::FullControl) -eq [Security.AccessControl.FileSystemRights]::FullControl)
        })
        if ($found.Count -eq 0) { Block 'ACL_FULL_CONTROL_MISSING' }
    }
    return $true
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
