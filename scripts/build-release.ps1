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

# Stage every platform bundle the host produced. Each OS builds its own
# bundle target set: base tauri.conf.json targets "nsis" on Windows, while
# tauri.macos.conf.json overrides to ["app", "dmg"] on macOS.
#   Windows -> desktop/src-tauri/target/release/bundle/nsis  *.exe
#   macOS   -> desktop/src-tauri/target/release/bundle/dmg   *.dmg
$Artifacts = @(
  @{ Dir = Join-Path $Workspace "desktop\src-tauri\target\release\bundle\nsis"; Filter = "*.exe"; Stable = "SALAR-Setup.exe"; Platform = "Windows" },
  @{ Dir = Join-Path $Workspace "desktop\src-tauri\target\release\bundle\dmg";  Filter = "*.dmg"; Stable = "SALAR-Setup.dmg"; Platform = "macOS" }
)
$Published = @()
foreach ($Artifact in $Artifacts) {
  $Found = @(Get-ChildItem -LiteralPath $Artifact.Dir -Filter $Artifact.Filter -ErrorAction SilentlyContinue)
  if ($Found.Count -eq 0) { continue }
  $Versioned = $Found | Select-Object -First 1
  Copy-Item -LiteralPath $Versioned.FullName -Destination (Join-Path $Installer $Versioned.Name) -Force
  $StablePath = Join-Path $Downloads $Artifact.Stable
  Copy-Item -LiteralPath $Versioned.FullName -Destination $StablePath -Force
  $Hash = Get-FileHash -LiteralPath $StablePath -Algorithm SHA256
  Set-Content -LiteralPath "$($StablePath).sha256" -Value "$($Hash.Hash.ToLower())  $($Artifact.Stable)"
  Write-Host "Published $($Artifact.Platform) download: $StablePath ($($Hash.Hash.ToLower()))"
  $Published += $Artifact.Stable
}
if ($Published.Count -eq 0) {
  throw "Tauri did not produce an NSIS installer or a macOS DMG"
}
Write-Host "Website: $Website"
Write-Host "Installer: $Installer"
Write-Host "Website downloads: $($Published -join ', ')"
