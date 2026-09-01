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

$Bundle = Join-Path $Workspace "desktop\src-tauri\target\release\bundle\nsis"
Copy-Item -Path (Join-Path $Bundle "*.exe") -Destination $Installer -Force
$VersionedInstaller = Get-ChildItem -LiteralPath $Installer -Filter "*.exe" | Select-Object -First 1
if (-not $VersionedInstaller) { throw "Tauri did not produce an NSIS installer" }
$WebsiteDownloads = Join-Path $Website "downloads"
New-Item -ItemType Directory -Force $WebsiteDownloads | Out-Null
$StableInstaller = Join-Path $WebsiteDownloads "SALAR-Setup.exe"
Copy-Item -LiteralPath $VersionedInstaller.FullName -Destination $StableInstaller -Force
$Hash = Get-FileHash -LiteralPath $StableInstaller -Algorithm SHA256
Set-Content -LiteralPath (Join-Path $WebsiteDownloads "SALAR-Setup.exe.sha256") -Value "$($Hash.Hash.ToLower())  SALAR-Setup.exe"
Write-Host "Website: $Website"
Write-Host "Installer: $Installer"
Write-Host "Website download: $StableInstaller"
