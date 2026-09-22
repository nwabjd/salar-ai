param(
  [string]$ApiUrl = "https://salar-backend.onrender.com"
)
$ErrorActionPreference = "Stop"
$Workspace = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Workspace "frontend"

Write-Host "Building SALAR website frontend against backend: $ApiUrl"
Push-Location $Frontend
$env:VITE_API_URL = $ApiUrl
if ($env:VITE_SUPABASE_URL) { Remove-Item Env:VITE_SUPABASE_URL -ErrorAction SilentlyContinue }
if ($env:VITE_SUPABASE_ANON_KEY) { Remove-Item Env:VITE_SUPABASE_ANON_KEY -ErrorAction SilentlyContinue }
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
Pop-Location

Write-Host "Syncing frontend/dist to dist/website"
$Website = Join-Path $Workspace "dist\website"
if (Test-Path -LiteralPath $Website) {
  Remove-Item -Path (Join-Path $Website "assets\*") -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force $Website | Out-Null
Copy-Item -Path (Join-Path $Frontend "dist\*") -Destination $Website -Recurse -Force

Write-Host "Done. Website source ready at dist\website (zip it and TUS-deploy to Hostinger)."