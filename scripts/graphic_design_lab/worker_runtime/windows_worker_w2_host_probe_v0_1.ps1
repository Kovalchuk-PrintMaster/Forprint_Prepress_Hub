# READ ONLY: PowerShell 5.1, run remotely through verified SSH from s01.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$root = 'D:\ForPrint_Automation\GraficsDesignLab\Automation'
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='D:'" -ErrorAction Stop
$keys = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')
$apps = @(Get-ItemProperty -Path $keys -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match '^Adobe Illustrator|^Adobe Acrobat|^CorelDRAW Graphics Suite' } | Select-Object DisplayName,DisplayVersion | Sort-Object DisplayName,DisplayVersion -Unique)
$fontKeys = @('HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts', 'HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')
$fonts = @()
foreach ($k in $fontKeys) {
    if (Test-Path -LiteralPath $k) {
        $fonts += @( (Get-ItemProperty -LiteralPath $k).PSObject.Properties | Where-Object { $_.Name -match 'Zapf|Corsiva' } | ForEach-Object { $_.Name } )
    }
}
$fonts = @($fonts | Sort-Object -Unique)
$sessions = @()
try { $sessions = @(& quser.exe 2>$null) } catch { $sessions = @() }
$active = @($sessions | Where-Object { $_ -match '\sActive\s' }).Count
$scheduler = Get-Service -Name Schedule -ErrorAction SilentlyContinue
$sshService = Get-Service -Name sshd -ErrorAction SilentlyContinue
$r = [ordered]@{
    schema_version = 'gdl_windows_w2_host_inspection_v0_1'
    origin = 'WINDOWS_READ_ONLY_SSH_PROBE'
    host_name = $env:COMPUTERNAME
    ssh_account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    os_build = [Environment]::OSVersion.Version.Build
    drive_d = [ordered]@{ present = ($null -ne $disk); file_system = $(if ($disk) { $disk.FileSystem } else { $null }); size_bytes = $(if ($disk) { [int64]$disk.Size } else { $null }); free_bytes = $(if ($disk) { [int64]$disk.FreeSpace } else { $null }) }
    worker_root = [ordered]@{ path = $root; exists = (Test-Path -LiteralPath $root) }
    registered_graphics_software = @($apps)
    registered_relevant_fonts = @($fonts)
    zapfchanceryc_registered = (@($fonts | Where-Object { $_ -match '^ZapfChanceryC\s*\(' }).Count -gt 0)
    active_quser_session_count = $active
    task_scheduler_status = $(if ($scheduler) { [string]$scheduler.Status } else { 'NOT_FOUND' })
    sshd_status = $(if ($sshService) { [string]$sshService.Status } else { 'NOT_FOUND' })
    illustrator_font_api_verified = $false
    interactive_gui_execution_verified = $false
    smb_private_access_verified = $false
    windows_write_requested = $false
}
[Console]::Out.WriteLine(($r | ConvertTo-Json -Depth 6 -Compress))
