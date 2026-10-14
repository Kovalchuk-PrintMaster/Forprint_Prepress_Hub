[CmdletBinding()]
param([string]$SshAlias = 's01', [string]$ShareName = 'In_Progress')

$ErrorActionPreference = 'Stop'
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8

# The launcher is located DIRECTLY in _forprint_automation/input.
$Workspace = Split-Path -Parent $PSScriptRoot
if ((Split-Path -Leaf $PSScriptRoot) -ne 'input' -or
    (Split-Path -Leaf $Workspace) -ne '_forprint_automation') {
    throw 'Launcher must live in _forprint_automation\input.'
}

$Pattern = '^\\\\[^\\]+\\' + [regex]::Escape($ShareName) + '\\'
$Match = [regex]::Match($Workspace, $Pattern,
    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
if (-not $Match.Success) {
    throw 'Open the launcher using the SMB UNC path (not a mapped drive).'
}
$Relative = $Workspace.Substring($Match.Length).Replace([char]92, '/')
$Encoded = [Convert]::ToBase64String(
    [System.Text.Encoding]::UTF8.GetBytes($Relative)
).TrimEnd('=').Replace('+','-').Replace('/','_')

$Repository = '/srv/software_development/forprint-project/forprint_prepress_hub'
$Remote = "cd $Repository && make gdl-greeting-card-smb-queue SHARE=$ShareName WORKSPACE_RELATIVE_B64=$Encoded"
Write-Host 'GDL_GC14_SMB_WORKSPACE_QUEUE=START'
$Old = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & ssh.exe -o BatchMode=yes -o ConnectTimeout=10 $SshAlias $Remote 2>&1 |
        ForEach-Object { Write-Host ([string]$_) }
    $Rc = $LASTEXITCODE
}
finally { $ErrorActionPreference = $Old }
if ($Rc -ne 0) { throw "GC14 SMB queue requires operator attention (exit $Rc)." }
Write-Host 'GDL_GC14_SMB_WORKSPACE_QUEUE=COMPLETE'
