[CmdletBinding()]
param(
    [string]$SshAlias = "s01",
    [string]$ShareName = "In_Progress"
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom

$LauncherDir = $PSScriptRoot
$LabRoot = Split-Path -Parent $LauncherDir
$LogsDir = Join-Path $LabRoot "logs"

if (-not (Test-Path -LiteralPath $LogsDir -PathType Container)) {
    New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
}

$SupportedBundleNames = @(
    "accepted_constructor_bundle.yaml",
    "accepted_constructor_bundle.yml",
    "accepted_constructor_bundle.json"
)

$Candidates = @(
    $SupportedBundleNames |
        ForEach-Object { Join-Path $LabRoot $_ } |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf }
)

if ($Candidates.Count -eq 0) {
    throw "Accepted Constructor Bundle not found next to launcher lab root."
}
if ($Candidates.Count -ne 1) {
    throw "Expected exactly one Accepted Constructor Bundle; found $($Candidates.Count)."
}

$BundleFullPath = (Get-Item -LiteralPath $Candidates[0]).FullName
$SharePattern = '^\\\\[^\\]+\\' + [regex]::Escape($ShareName) + '\\'
$ShareMatch = [regex]::Match(
    $BundleFullPath,
    $SharePattern,
    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
)

if (-not $ShareMatch.Success) {
    throw "Bundle must be located inside SMB share '$ShareName'."
}

$RelativePath = $BundleFullPath.Substring($ShareMatch.Length).Replace([char]92, '/')
if ([string]::IsNullOrWhiteSpace($RelativePath)) {
    throw "Could not derive bundle path relative to SMB share."
}

$Utf8 = [System.Text.Encoding]::UTF8.GetBytes($RelativePath)
$RelativePathB64 = [Convert]::ToBase64String($Utf8).TrimEnd('=').Replace('+', '-').Replace('/', '_')

$Repo = "/srv/software_development/forprint-project/forprint_prepress_hub"
$RemoteCommand = (
    "cd $Repo && " +
    "make gdl-greeting-card-smb-launch " +
    "SHARE=$ShareName " +
    "RELATIVE_PATH_B64=$RelativePathB64"
)

$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path $LogsDir "gc_e2e_07_launcher_$Timestamp.log"

@(
    "FORPRINT_GDL_GC_E2E_07_WINDOWS_LAUNCH=START"
    "SSH_ALIAS=$SshAlias"
    "SMB_SHARE=$ShareName"
    "BUNDLE_NAME=$([System.IO.Path]::GetFileName($BundleFullPath))"
) | Set-Content -Encoding UTF8 -LiteralPath $LogPath

$PreviousErrorActionPreference = $ErrorActionPreference
try {
    # Windows PowerShell 5.1 wraps native stderr as ErrorRecord objects.
    # Keep collecting stderr so remote failures are fully logged instead
    # of terminating on the first stderr line.
    $ErrorActionPreference = "Continue"

    $Output = & ssh.exe `
        -o BatchMode=yes `
        -o ConnectTimeout=10 `
        $SshAlias `
        $RemoteCommand 2>&1

    $ExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
}
$Output | Tee-Object -FilePath $LogPath -Append | ForEach-Object { Write-Host $_ }

if ($ExitCode -ne 0) {
    "FORPRINT_GDL_GC_E2E_07_WINDOWS_LAUNCH=FAIL" |
        Add-Content -Encoding UTF8 -LiteralPath $LogPath
    throw "Remote launcher failed with exit code $ExitCode. See $LogPath"
}

"FORPRINT_GDL_GC_E2E_07_WINDOWS_LAUNCH=PASS" |
    Add-Content -Encoding UTF8 -LiteralPath $LogPath

Write-Host "FORPRINT_GDL_GC_E2E_07_WINDOWS_LAUNCH=PASS"
Write-Host "MANUAL_LINUX_PATH_ENTRY=false"
Write-Host "LOG=$LogPath"
