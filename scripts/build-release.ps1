param(
  [string]$ApiUrl = "https://api.salar.example.com"
)
$ErrorActionPreference = "Stop"
$Workspace = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Workspace "dist"
$Website = Join-Path $Dist "website"
$Installer = Join-Path $Dist "installer"

Push-Location (Join-Path $Workspace "backend")
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed" }
Pop-Location

Push-Location (Join-Path $Workspace "frontend")
$env:VITE_API_URL = $ApiUrl
npm ci
if ($LASTEXITCODE -ne 0) { throw "Frontend install failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Pop-Location

New-Item -ItemType Directory -Force $Website, $Installer | Out-Null
Copy-Item -Path (Join-Path $Workspace "frontend\dist\*") -Destination $Website -Recurse -Force

Push-Location (Join-Path $Workspace "desktop")
npm ci
if ($LASTEXITCODE -ne 0) { throw "Desktop install failed" }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Desktop build failed" }
Pop-Location

$Bundle = Join-Path $Workspace "desktop\src-tauri\target\release\bundle\nsis"
Copy-Item -Path (Join-Path $Bundle "*.exe") -Destination $Installer -Force
Write-Host "Website: $Website"
Write-Host "Installer: $Installer"
