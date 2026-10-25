<#
.SYNOPSIS
    Build the JARVIS Windows application (onedir) and package it as JARVIS-Windows.zip.

.DESCRIPTION
    Creates a clean virtual environment, installs the requirements, runs the test
    suite, builds with PyInstaller and zips the result together with README.txt.

    Run it from a Windows 11 x64 machine with Python 3.11 or 3.12 installed:

        powershell -ExecutionPolicy Bypass -File build.ps1
        powershell -ExecutionPolicy Bypass -File build.ps1 -WithBrowser
        powershell -ExecutionPolicy Bypass -File build.ps1 -SkipTests

    -WithBrowser additionally downloads Chromium for Playwright (~150 MB in the
    user profile). It is optional: browser automation can also be enabled later
    on the target PC with "playwright install chromium".

    The build is NOT verified here: this repository was developed and tested on
    Linux, where PyInstaller cannot produce a Windows executable. Run the script
    on Windows and report the measured size.
#>

[CmdletBinding()]
param(
    [switch]$WithBrowser,
    [switch]$SkipTests,
    # Run one stage at a time. CI calls these individually so a failure is
    # reported as the stage it happened in; the default runs everything.
    [ValidateSet("all", "preflight", "setup", "install", "test", "check", "build", "package")]
    [string]$Phase = "all",
    [string]$Python = "python",
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Push-Location $Root

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Fail([string]$Message) {
    Write-Host "FAILED: $Message" -ForegroundColor Red
    Pop-Location
    exit 1
}

try {
    Write-Step "Checking Python"
    $version = & $Python -c "import sys; print('%d.%d.%d' % sys.version_info[:3]); print(sys.executable)"
    if ($LASTEXITCODE -ne 0) { Fail "Python was not found. Install Python 3.11 or 3.12 (64-bit)." }
    Write-Host $version

    $major = [int]((& $Python -c "import sys; print(sys.version_info[0])"))
    $minor = [int]((& $Python -c "import sys; print(sys.version_info[1])"))
    if ($major -ne 3 -or ($minor -ne 11 -and $minor -ne 12)) {
        Fail "Python 3.11 or 3.12 is required (found $major.$minor)."
    }

    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

    if ($Phase -eq "preflight") {
        Pop-Location
        return
    }

    if ($Phase -in @("all", "setup")) {
        Write-Step "Creating a clean virtual environment (.venv)"
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { Fail "Could not create the virtual environment." }
    }

    if ($Phase -in @("all", "install")) {
        Write-Step "Installing requirements"
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { Fail "pip install failed." }

        if ($WithBrowser) {
            Write-Step "Downloading Chromium for Playwright (about 150 MB)"
            & $VenvPython -m playwright install chromium
            if ($LASTEXITCODE -ne 0) { Write-Warning "Chromium download failed - browser automation will be unavailable." }
        }
    }

    if (-not $SkipTests -and $Phase -in @("all", "test")) {
        Write-Step "Running the test suite"
        & $VenvPython -m pytest tests -q
        if ($LASTEXITCODE -ne 0) { Fail "Tests failed - the build is stopped." }
    }

    if ($Phase -in @("all", "check")) {
        Write-Step "Running the environment check"
        & $VenvPython main.py --check
        if ($LASTEXITCODE -ne 0) { Fail "The environment check failed." }
    }

    $AppDir = Join-Path $OutputDir "JARVIS"

    if ($Phase -in @("all", "build")) {
        Write-Step "Building with PyInstaller"
        if (Test-Path build) { Remove-Item -Recurse -Force build }
        if (Test-Path $AppDir) { Remove-Item -Recurse -Force $AppDir }
        $built = $false
        foreach ($attempt in 1..2) {
            & $VenvPython -m PyInstaller --noconfirm --clean JARVIS.spec
            if ($LASTEXITCODE -eq 0) { $built = $true; break }
            Write-Warning "PyInstaller attempt $attempt failed; retrying once."
            if (Test-Path build) { Remove-Item -Recurse -Force build }
            if (Test-Path $AppDir) { Remove-Item -Recurse -Force $AppDir }
            Start-Sleep -Seconds 10
        }
        if (-not $built) { Fail "PyInstaller failed." }
        if (-not (Test-Path $AppDir)) { Fail "The build did not produce $AppDir." }

        Write-Step "Measuring the build"
        $exeSize = (Get-Item (Join-Path $AppDir "JARVIS.exe")).Length
        $dirSize = (Get-ChildItem $AppDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
        Write-Host ("  JARVIS.exe          : {0:N2} MB" -f ($exeSize / 1MB))
        Write-Host ("  runtime folder      : {0:N2} MB" -f ($dirSize / 1MB))
        if ($dirSize -gt 400MB) {
            Write-Warning "The runtime folder is larger than the 50-100 MB target. See README.md for the size breakdown."
        }
    }

    if ($Phase -in @("all", "package")) {
        if (-not (Test-Path $AppDir)) { Fail "Packaging was requested but $AppDir does not exist." }

        Write-Step "Assembling the release folder"
        # The zip is laid out so that extracting it gives a single JARVIS folder.
        $ReleaseDir = Join-Path $Root "release"
        if (Test-Path $ReleaseDir) { Remove-Item -Recurse -Force $ReleaseDir }
        $ZipAppDir = Join-Path $ReleaseDir "JARVIS"
        New-Item -ItemType Directory -Path $ZipAppDir -Force | Out-Null
        Copy-Item -Path $AppDir -Destination $ZipAppDir -Recurse -Force

        foreach ($file in @("README.txt", ".env.example", "requirements.txt", "uninstall.ps1")) {
            $src = Join-Path $Root $file
            if (Test-Path $src) { Copy-Item -Path $src -Destination $ZipAppDir -Force }
        }
        # config template: the live config is created in the per-user data folder on
        # first run, so the application folder itself stays read-only if needed.
        $template = Join-Path $Root "config.json"
        if (Test-Path $template) {
            Copy-Item -Path $template -Destination (Join-Path $ZipAppDir "config.example.json") -Force
        }

        # Convenience launcher: double-clicking opens the app from any location.
        $bat = @"
@echo off
title JARVIS
cd /d "%~dp0"
"%~dp0JARVIS.exe"
"@
        Set-Content -Path (Join-Path $ZipAppDir "launch.bat") -Value $bat -Encoding ASCII

        $topReadme = @"
JARVIS - Windows 11 desktop assistant
=====================================

1. Extract this zip anywhere (for example C:\Users\<name>\JARVIS).
2. Open the JARVIS folder and double-click JARVIS.exe (or launch.bat).
3. On first run you will be asked for a Gemini API key, or you can add it to
   %LOCALAPPDATA%\JARVIS\.env as GEMINI_API_KEY=...
4. See JARVIS\README.txt for the full guide.

Safety: press Ctrl+Alt+J at any time to stop JARVIS instantly. The key never
leaves your PC except to Google's Gemini endpoint.
"@
        Set-Content -Path (Join-Path $ReleaseDir "README.txt") -Value $topReadme -Encoding UTF8

        Write-Step "Packaging JARVIS-Windows.zip"
        $zipPath = Join-Path $Root "JARVIS-Windows.zip"
        if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
        Compress-Archive -Path (Join-Path $ReleaseDir "*") -DestinationPath $zipPath -Force
        $zipSize = (Get-Item $zipPath).Length
        Write-Host ("  JARVIS-Windows.zip  : {0:N2} MB" -f ($zipSize / 1MB))

        # SHA-256 manifest so the download can be verified
        $sha = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash
        $exeHash = (Get-FileHash -Path (Join-Path $AppDir "JARVIS.exe") -Algorithm SHA256).Hash
        Set-Content -Path (Join-Path $ReleaseDir "SHA256SUMS.txt") -Encoding ASCII -Value @(
            "{0}  JARVIS-Windows.zip" -f $sha,
            "{0}  JARVIS\JARVIS.exe" -f $exeHash
        )
        Copy-Item -Path (Join-Path $ReleaseDir "SHA256SUMS.txt") -Destination $Root -Force
        Write-Host ("  SHA256 (zip)         : {0}" -f $sha)

        Write-Host ""
        Write-Host "DONE." -ForegroundColor Green
        Write-Host "  Run it by double-clicking $AppDir\JARVIS.exe"
        Write-Host "  Zip: $zipPath"
    }

}
catch {
    Fail $_.Exception.Message
}
finally {
    Pop-Location
}
