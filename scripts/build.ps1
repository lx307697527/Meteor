# VoiceIME Build Script — PyInstaller single-file .exe
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build.ps1

param(
    [switch]$Clean = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== VoiceIME Build ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

# Check PyInstaller
$pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# Clean previous build
if ($Clean) {
    Write-Host "Cleaning previous build..." -ForegroundColor Yellow
    $dirs = @("build", "dist")
    foreach ($dir in $dirs) {
        $path = Join-Path $ProjectRoot $dir
        if (Test-Path $path) {
            Remove-Item -Recurse -Force $path
        }
    }
}

# Build
Set-Location $ProjectRoot

$args = @(
    "--noconfirm",
    "--clean"
)
if ($Verbose) {
    $args += "--log-level=DEBUG"
}

Write-Host "Building VoiceIME.exe..." -ForegroundColor Green
pyinstaller @args voiceime.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build FAILED with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}

$exePath = Join-Path $ProjectRoot "dist\VoiceIME.exe"
if (Test-Path $exePath) {
    $size = (Get-Item $exePath).Length / 1MB
    Write-Host ""
    Write-Host "Build SUCCESS" -ForegroundColor Green
    Write-Host "Output: $exePath ($size MB)" -ForegroundColor Green
} else {
    Write-Host "Build completed but exe not found at expected path" -ForegroundColor Red
    exit 1
}
