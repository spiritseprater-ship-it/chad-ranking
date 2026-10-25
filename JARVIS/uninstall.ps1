<#
.SYNOPSIS
    Uninstall JARVIS (removes the application, its startup entry and shortcuts).

.DESCRIPTION
    Safe by default:
      * removes the JARVIS folder you point it at
      * removes the per-user "Run" registry entry created by "Launch at startup"
      * removes the Start Menu and Desktop shortcuts
      * keeps your data (conversation history, task history, screenshots, photos,
        the stored API key) unless you pass -Purge

    Run it as the same user who installed JARVIS - no administrator rights needed.

        powershell -ExecutionPolicy Bypass -File uninstall.ps1 -AppDir "C:\Program Files\JARVIS"
        powershell -ExecutionPolicy Bypass -File uninstall.ps1 -AppDir "C:\Program Files\JARVIS" -Purge
#>

[CmdletBinding()]
param(
    [string]$AppDir = (Join-Path $env:LOCALAPPDATA "JARVIS"),
    [switch]$Purge,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Confirm-OrExit([string]$Message) {
    if ($Force) { return }
    $answer = Read-Host "$Message (y/N)"
    if ($answer -notmatch "^(y|yes)$") {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "JARVIS uninstaller" -ForegroundColor Cyan

if (-not (Test-Path $AppDir)) {
    Write-Host "Nothing to remove at $AppDir" -ForegroundColor Yellow
}
else {
    Confirm-OrExit "Remove $AppDir ?"
    Remove-Item -Recurse -Force $AppDir
    Write-Host "Removed $AppDir" -ForegroundColor Green
}

# per-user startup entry (no admin rights required)
$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
if (Test-Path $runKey) {
    $registry = Get-ItemProperty -Path $runKey
    if ($null -ne $registry.JARVIS) {
        Confirm-OrExit "Remove the JARVIS startup entry from the Windows Run key ?"
        Remove-ItemProperty -Path $runKey -Name "JARVIS" -ErrorAction SilentlyContinue
        Write-Host "Startup entry removed" -ForegroundColor Green
    }
}

# shortcuts
$shortcutTargets = @(
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\JARVIS"),
    (Join-Path $env:USERPROFILE "Desktop\JARVIS.lnk"),
    (Join-Path $env:USERPROFILE "Desktop\JARVIS (uninstall).lnk")
)
foreach ($target in $shortcutTargets) {
    if (Test-Path $target) {
        Remove-Item -Recurse -Force $target -ErrorAction SilentlyContinue
    }
}

if ($Purge) {
    Write-Host "Removing user data (history, screenshots, photos, stored key)..." -ForegroundColor Cyan
    foreach ($path in @("$env:LOCALAPPDATA\JARVIS", "$env:APPDATA\JARVIS", (Join-Path $env:USERPROFILE ".jarvis"))) {
        if (Test-Path $path) {
            Remove-Item -Recurse -Force $path -ErrorAction SilentlyContinue
            Write-Host "Removed $path" -ForegroundColor Green
        }
    }
}
else {
    Write-Host "Your JARVIS data was kept. Re-run with -Purge to delete it as well." -ForegroundColor Yellow
}

Write-Host "Uninstall complete." -ForegroundColor Green
