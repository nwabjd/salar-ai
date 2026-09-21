param(
  [string]$ApiUrl = "https://salar-backend.onrender.com"
)
$ErrorActionPreference = "Stop"
$Workspace = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Workspace "dist"
$Website = Join-Path $Dist "website"
$Installer = Join-Path $Dist "installer"

Push-Location (Join-Path $Workspace "backend")
$PreviousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = (Get-Location).Path
if (-not $env:SALAR_GEMINI_API_KEY) { $env:SALAR_GEMINI_API_KEY = "release-test-placeholder" }
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
if ($null -eq $PreviousPythonPath) { Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue } else { $env:PYTHONPATH = $PreviousPythonPath }
Pop-Location

Push-Location (Join-Path $Workspace "frontend")
$env:VITE_API_URL = $ApiUrl
npm ci
if ($LASTEXITCODE -ne 0) { throw "Frontend install failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Pop-Location

$ResolvedDist = [System.IO.Path]::GetFullPath($Dist)
foreach ($Target in @($Website, $Installer)) {
  $ResolvedTarget = [System.IO.Path]::GetFullPath($Target)
  if (-not $ResolvedTarget.StartsWith($ResolvedDist, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean release directory outside dist: $ResolvedTarget"
  }
  if (Test-Path -LiteralPath $ResolvedTarget) {
    Remove-Item -LiteralPath $ResolvedTarget -Recurse -Force
  }
  New-Item -ItemType Directory -Force $ResolvedTarget | Out-Null
}
Copy-Item -Path (Join-Path $Workspace "frontend\dist\*") -Destination $Website -Recurse -Force

Push-Location (Join-Path $Workspace "desktop")
npm ci
if ($LASTEXITCODE -ne 0) { throw "Desktop install failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Desktop build failed" }
Pop-Location

$Downloads = Join-Path $Website "downloads"
New-Item -ItemType Directory -Force $Downloads | Out-Null

$Published = @()

# Windows: stage the NSIS installer under a stable name.
#   desktop/src-tauri/target/release/bundle/nsis  SALAR_*.exe
$NsisDir = Join-Path $Workspace "desktop\src-tauri\target\release\bundle\nsis"
$Exe = Get-ChildItem -LiteralPath $NsisDir -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Exe) {
  $StablePath = Join-Path $Downloads "SALAR-Setup.exe"
  Copy-Item -LiteralPath $Exe.FullName -Destination $StablePath -Force
  Copy-Item -LiteralPath $Exe.FullName -Destination (Join-Path $Installer $Exe.Name) -Force
  $Hash = Get-FileHash -LiteralPath $StablePath -Algorithm SHA256
  Set-Content -LiteralPath "$($StablePath).sha256" -Value "$($Hash.Hash.ToLower())  SALAR-Setup.exe"
  Write-Host "Published Windows download: $StablePath ($($Hash.Hash.ToLower()))"
  $Published += "SALAR-Setup.exe"
}

# macOS: zip the .app bundle under a stable name (the unsigned app ships as a
# zip, matching the current salaar.cloud download).
#   desktop/src-tauri/target/release/bundle/macos  SALAR.app
$MacBundleDir = Join-Path $Workspace "desktop\src-tauri\target\release\bundle\macos"
$AppBundle = Get-ChildItem -LiteralPath $MacBundleDir -Filter "*.app" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
if ($AppBundle) {
  $StablePath = Join-Path $Downloads "SALAR.app.zip"
  Compress-Archive -Path $AppBundle.FullName -DestinationPath $StablePath -Force
  Copy-Item -LiteralPath $StablePath -Destination (Join-Path $Installer "SALAR.app.zip") -Force
  $Hash = Get-FileHash -LiteralPath $StablePath -Algorithm SHA256
  Set-Content -LiteralPath "$($StablePath).sha256" -Value "$($Hash.Hash.ToLower())  SALAR.app.zip"
  Write-Host "Published macOS download: $StablePath ($($Hash.Hash.ToLower()))"
  $Published += "SALAR.app.zip"
}

if ($Published.Count -eq 0) {
  throw "Tauri did not produce an NSIS installer or a macOS .app bundle"
}
Write-Host "Website: $Website"
Write-Host "Installer: $Installer"
Write-Host "Website downloads: $($Published -join ', ')"
