param(
  [switch]$SkipPull
)
# Installs SALAR's local-brain models (Gemma 4 E2B + E4B) into the local Ollama.
# 1. Pulls the base models (E2B ~7.2 GB, E4B ~9.6 GB) unless -SkipPull.
# 2. Creates the SALAR-branded models from the Modelfiles in this repo.
#
# Usage:  powershell -File scripts\install-local-models.ps1        (full install)
#         powershell -File scripts\install-local-models.ps1 -SkipPull  (recreate only)
$ErrorActionPreference = "Stop"
$Workspace = Split-Path -Parent $PSScriptRoot

$pairs = @(
  @{ Base = "gemma4:e2b"; Name = "salar-gemma4-e2b"; File = "Modelfile.gemma4-e2b" },
  @{ Base = "gemma4:e4b"; Name = "salar-gemma4-e4b"; File = "Modelfile.gemma4-e4b" }
)

if (-not $SkipPull) {
  foreach ($p in $pairs) {
    Write-Host "Pulling $($p.Base) ..."
    ollama pull $p.Base
    if ($LASTEXITCODE -ne 0) { throw "ollama pull $($p.Base) failed" }
  }
}

foreach ($p in $pairs) {
  $mf = Join-Path $Workspace $p.File
  if (-not (Test-Path -LiteralPath $mf)) { throw "Missing Modelfile: $mf" }
  Write-Host "Creating $($p.Name) from $($p.File)"
  ollama create $p.Name -f $mf
  if ($LASTEXITCODE -ne 0) { throw "ollama create $($p.Name) failed" }
}

Write-Host ""
Write-Host "Done. Local brain models ready:"
Write-Host "  salar-gemma4-e2b  (default local mode model)"
Write-Host "  salar-gemma4-e4b  (more reliable tool-calling; pick it in the local-mode dropdown)"