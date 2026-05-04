param(
  [string]$ApiUrl = "https://fideon-staging-apim.azure-api.net/stg",
  [string]$FrontendUrl = "https://fideon-staging-frontend-gnbwcnhmhbeqbmhq.centralus-01.azurewebsites.net",
  [string]$BackendDocsUrl = "https://fideon-staging-apim.azure-api.net/stg/docs",
  [string]$PackageLabel = "staging",
  [switch]$SkipInstall,
  [switch]$SkipFrontendBuild,
  [switch]$SkipZip
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendDir = Join-Path $root "frontend"
$electronDir = Join-Path $root "electron"

if (!(Test-Path $frontendDir)) {
  throw "Frontend folder not found: $frontendDir"
}

if (!(Test-Path $electronDir)) {
  throw "Electron folder not found: $electronDir"
}

Write-Host "Using API URL: $ApiUrl" -ForegroundColor Cyan
$env:NEXT_PUBLIC_API_URL = $ApiUrl
Write-Host "Using Frontend URL (reference): $FrontendUrl" -ForegroundColor Cyan
$env:NEXT_PUBLIC_FRONTEND_URL = $FrontendUrl
Write-Host "Using Backend Swagger URL (reference): $BackendDocsUrl" -ForegroundColor Cyan
$env:NEXT_PUBLIC_BACKEND_DOCS_URL = $BackendDocsUrl
$env:NEXT_STANDALONE = "1"

# Sync Electron main process API URL with the build parameter.
Write-Host "Configuring Electron main process API URL..." -ForegroundColor Cyan
$electronEnvPath = Join-Path $electronDir ".env"
"ELECTRON_API_BASE_URL=$ApiUrl" | Set-Content -Path $electronEnvPath -Encoding utf8

# Prevent file-lock issues during repackaging (app.asar is inside the exe folder).
# If the process isn't running, `taskkill` writes an error; ignore it so the script keeps going.
$oldEap = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
taskkill /IM "Fideon OS.exe" /F | Out-Null
$ErrorActionPreference = $oldEap

Write-Host "Building frontend..." -ForegroundColor Yellow
if (-not $SkipFrontendBuild) {
  Push-Location $frontendDir
  if (-not $SkipInstall) {
    npm install
  }
  npm run build
  Pop-Location
} else {
  Write-Host "SkipFrontendBuild enabled: not rebuilding frontend." -ForegroundColor Yellow
}

Write-Host "Building and packaging Electron..." -ForegroundColor Yellow
Push-Location $electronDir
if (-not $SkipInstall) {
  npm install
}

# Ensure electron-builder Windows icon meets minimum size requirements.
# (electron-builder requires >= 256x256 for Windows icons.)
$iconPath = Join-Path $electronDir "build\\icon-256.png"
if (!(Test-Path $iconPath)) {
  Write-Host "Generating 256x256 icon for electron-builder..." -ForegroundColor Yellow
  powershell -ExecutionPolicy Bypass -File (Join-Path $electronDir "generate-icon-256.ps1")
}

npm run build

# electron-builder may fail in your environment during the winCodeSign step
# (symlink privilege). The portable files we need for QA are still usually produced,
# so we continue packaging even if dist exits non-zero.
& npm run dist
$distExitCode = $LASTEXITCODE
if ($distExitCode -ne 0) {
  Write-Host "Warning: electron-builder exited with code $distExitCode. Continuing to package QA artifacts." -ForegroundColor Yellow
}

# Fix: Next standalone can overwrite the root package.json inside app.asar.
# Electron needs its own package.json (main=dist/main.js) at app.asar root.
$asarPath = Join-Path $electronDir "release\\win-unpacked\\resources\\app.asar"
if (Test-Path $asarPath) {
  $tempDir = Join-Path $env:TEMP ("asar-patch-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
  if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir
  }
  New-Item -ItemType Directory -Path $tempDir | Out-Null

  Write-Host "Patching app.asar package.json for Electron startup..." -ForegroundColor Yellow
  npx asar extract $asarPath $tempDir | Out-Null
  Copy-Item -Path (Join-Path $electronDir "package.json") -Destination (Join-Path $tempDir "package.json") -Force
  npx asar pack $tempDir $asarPath | Out-Null
  Remove-Item -Recurse -Force $tempDir
} else {
  Write-Host "Skip asar patch: not found at $asarPath" -ForegroundColor Yellow
}
Pop-Location

$releaseDir = Join-Path $electronDir "release"
$setupExe = Get-ChildItem -Path $releaseDir -Filter "*Setup*.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
$appExe = Get-ChildItem -Path (Join-Path $releaseDir "win-unpacked") -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1

$shareDir = Join-Path $releaseDir "qa-share"
if (Test-Path $shareDir) {
  Remove-Item -Path $shareDir -Recurse -Force
}
New-Item -ItemType Directory -Path $shareDir | Out-Null

if ($setupExe) {
  Copy-Item -Path $setupExe.FullName -Destination $shareDir -Force
}

if ($appExe) {
  $unpackedSource = Join-Path $releaseDir "win-unpacked"
  $unpackedDestination = Join-Path $shareDir "win-unpacked"
  Copy-Item -Path $unpackedSource -Destination $unpackedDestination -Recurse -Force
}

# Ensure tray icon exists in the packaged runtime.
# (Electron tray loads from `process.resourcesPath/fideon-tray.png`.)
$srcTrayIcon = Join-Path $electronDir "build\\icon-256.png"
$dstTrayIcon1 = Join-Path $releaseDir "win-unpacked\\resources\\fideon-tray.png"
$dstTrayIcon2 = Join-Path $releaseDir "win-unpacked\\fideon-tray.png"
$dstShareTrayIcon1 = Join-Path $shareDir "win-unpacked\\resources\\fideon-tray.png"
$dstShareTrayIcon2 = Join-Path $shareDir "win-unpacked\\fideon-tray.png"
if (Test-Path $srcTrayIcon) {
  if (!(Test-Path (Split-Path -Parent $dstTrayIcon1))) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $dstTrayIcon1) | Out-Null
  }
  Copy-Item -Path $srcTrayIcon -Destination $dstTrayIcon1 -Force
  Copy-Item -Path $srcTrayIcon -Destination $dstTrayIcon2 -Force

  if (!(Test-Path (Split-Path -Parent $dstShareTrayIcon1))) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $dstShareTrayIcon1) | Out-Null
  }
  Copy-Item -Path $srcTrayIcon -Destination $dstShareTrayIcon1 -Force
  Copy-Item -Path $srcTrayIcon -Destination $dstShareTrayIcon2 -Force
}

$readmePath = Join-Path $shareDir "README-QA.txt"
$readme = @"
Fideon OS - QA/Client Build Package

Environment:
- Frontend URL (reference): $FrontendUrl
- Backend API base URL: $ApiUrl
- Backend Swagger docs: $BackendDocsUrl

How to run on Windows:
1) Preferred: run the installer EXE (if available in this folder).
2) If installer is not present, open win-unpacked and run the main EXE.
3) Keep all files inside win-unpacked together.

Notes:
- If Windows SmartScreen shows a warning, click More info -> Run anyway.
- If you don’t see a window: check the Windows system tray (bottom-right). Right-click the tray icon and choose `Show Fideon OS`.
- This build is intended for QA/client testing.
"@
Set-Content -Path $readmePath -Value $readme -Encoding utf8

# Helper launcher (useful when double-click seems to do nothing)
$batPath = Join-Path $shareDir "run-qa.bat"
$batContent = @"
@echo off
taskkill /IM \"Fideon OS.exe\" /F >nul 2>&1
start \"Fideon OS\" /D \"%~dp0\\win-unpacked\" \"Fideon OS.exe\"
"@
Set-Content -Path $batPath -Value $batContent -Encoding ascii

$zipPath = $null
if (-not $SkipZip) {
  $timestamp = Get-Date -Format "yyyyMMdd-HHmm"
  $safeLabel = ($PackageLabel -replace "[^a-zA-Z0-9_-]", "_")
  $zipName = "FideonOS-$safeLabel-$timestamp.zip"
  $zipPath = Join-Path $releaseDir $zipName
  if (Test-Path $zipPath) {
    Remove-Item -Path $zipPath -Force
  }
  Compress-Archive -Path (Join-Path $shareDir "*") -DestinationPath $zipPath -Force
}

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "Artifacts folder: $releaseDir"
Write-Host "Share folder: $shareDir"

if ($setupExe) {
  Write-Host "Installer EXE: $($setupExe.FullName)"
}

if ($appExe) {
  Write-Host "Unpacked app EXE: $($appExe.FullName)"
}

if (-not $setupExe -and -not $appExe) {
  Write-Host "No EXE found. Check build logs in electron/release." -ForegroundColor Red
}

if ($zipPath) {
  Write-Host "Share ZIP: $zipPath" -ForegroundColor Green
}
