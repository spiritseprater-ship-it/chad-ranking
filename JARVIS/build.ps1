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

    Write-Step "Creating a clean virtual environment (.venv)"
    & $Python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the virtual environment." }
    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

    Write-Step "Installing requirements"
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Fail "pip install failed." }

    if ($WithBrowser) {
        Write-Step "Downloading Chromium for Playwright (about 150 MB)"
        & $VenvPython -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { Write-Warning "Chromium download failed - browser automation will be unavailable." }
    }

    if (-not $SkipTests) {
        Write-Step "Running the test suite"
        & $VenvPython -m pytest tests -q
        if ($LASTEXITCODE -ne 0) { Fail "Tests failed - the build is stopped." }
    }

    Write-Step "Running the environment check"
    & $VenvPython main.py --check

    Write-Step "Building with PyInstaller"
    if (Test-Path build) { Remove-Item -Recurse -Force build }
    if (Test-Path "$OutputDir\JARVIS") { Remove-Item -Recurse -Force "$OutputDir\JARVIS" }
    & $VenvPython -m PyInstaller --noconfirm --clean JARVIS.spec
    if ($LASTEXITCODE -ne 0) { Fail "PyInstaller failed." }

    $AppDir = Join-Path $OutputDir "JARVIS"
    if (-not (Test-Path $AppDir)) { Fail "The build did not produce $AppDir." }

    Write-Step "Measuring the build"
    $exeSize = (Get-Item (Join-Path $AppDir "JARVIS.exe")).Length
    $dirSize = (Get-ChildItem $AppDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
    Write-Host ("  JARVIS.exe          : {0:N2} MB" -f ($exeSize / 1MB))
    Write-Host ("  runtime folder      : {0:N2} MB" -f ($dirSize / 1MB))
    if ($dirSize -gt 400MB) {
        Write-Warning "The runtime folder is larger than the 50-100 MB target. See README.md for the size breakdown."
    }

    Write-Step "Packaging JARVIS-Windows.zip"
    $zipPath = Join-Path $Root "JARVIS-Windows.zip"
    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
    Compress-Archive -Path $AppDir -DestinationPath $zipPath -Force
    $zipSize = (Get-Item $zipPath).Length
    Write-Host ("  JARVIS-Windows.zip  : {0:N2} MB" -f ($zipSize / 1MB))

    Write-Host ""
    Write-Host "DONE." -ForegroundColor Green
    Write-Host "  Run it by double-clicking $AppDir\JARVIS.exe"
    Write-Host "  Zip: $zipPath"
}
catch {
    Fail $_.Exception.Message
}
finally {
    Pop-Location
}
