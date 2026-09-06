# SALAR Build, Push & Deploy Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commit upgrade changes, build the desktop installer, push to GitHub, and deploy to Render + Hostinger.

**Architecture:** Git push triggers Render auto-deploy (backend). Frontend is built as static files and uploaded to Hostinger via zip/TUS. Desktop is built via `tauri build` producing a Windows NSIS installer.

**Tech Stack:** Git, Tauri 2, Vite, PowerShell scripts, Render (Docker), Hostinger (static hosting)

---

### Task 1: Commit Upgrade Changes

**Files:**
- Modify: All files from the 5-item upgrade (backend + desktop)

- [ ] **Step 1: Stage all upgrade files**

```powershell
cd "C:\Users\JD\Documents\SALAR AI"
git add backend/.env.example backend/app/api/auth.py backend/app/api/auth_relay.py backend/app/api/devices.py backend/app/config.py backend/app/main.py backend/app/rate_limit.py backend/pyproject.toml backend/requirements.txt desktop/src-tauri/tauri.conf.json
```

- [ ] **Step 2: Verify staged changes**

```powershell
git status
```

Expected: All 10 files staged (9 modified + 1 new `rate_limit.py`)

- [ ] **Step 3: Commit**

```powershell
git commit -m "feat(security): add rate limiting, structured logging, CORS hardening, CSP

- Add slowapi rate limiting (5/min login, 10/min device/handshake)
- Add python-json-logger for structured JSON log output
- Remove wildcard CORS allow_origin_regex, make configurable via env
- Add strict CSP policy to Tauri desktop config
- Bump websockets 12 to 13
- New env vars: SALAR_LOG_LEVEL, SALAR_CORS_ALLOW_REGEX, SALAR_RATE_LIMIT"
```

- [ ] **Step 4: Verify commit**

```powershell
git log --oneline -1
```

Expected: New commit at HEAD with the message above

---

### Task 2: Push to GitHub

- [ ] **Step 1: Push to origin**

```powershell
git push origin main
```

Expected: Push succeeds, GitHub shows the new commit

- [ ] **Step 2: Verify Render will auto-deploy**

Render is configured with `render.yaml` and watches the repo. After push, Render should automatically start a new deployment. Verify by checking https://dashboard.render.com or running:

```powershell
# Check if Render auto-deploys (Render webhook triggers on push)
git log --oneline -1
```

Note: If Render doesn't auto-deploy, manually trigger from the Render dashboard.

---

### Task 3: Build Frontend for Hostinger

- [ ] **Step 1: Build website with production API URL**

```powershell
cd "C:\Users\JD\Documents\SALAR AI"
.\scripts\build-website.ps1 -ApiUrl "https://salar-backend.onrender.com"
```

Expected: `dist/website/` is populated with built frontend files

- [ ] **Step 2: Verify build output**

```powershell
Get-ChildItem dist\website | Select-Object Name
```

Expected: `index.html`, `assets/`, `downloads/` (if installer was previously built)

- [ ] **Step 3: Zip for Hostinger upload**

```powershell
$zipPath = "C:\Users\JD\Documents\SALAR AI\dist\salar-website.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath }
Compress-Archive -Path "C:\Users\JD\Documents\SALAR AI\dist\website\*" -DestinationPath $zipPath
Write-Host "Zip created: $zipPath"
Write-Host "Size: $([math]::Round((Get-Item $zipPath).Length / 1MB, 2)) MB"
```

Expected: Zip file created at `dist/salar-website.zip`

- [ ] **Step 4: Upload to Hostinger**

The user must manually upload via Hostinger File Manager or hPanel:
1. Log in to Hostinger hPanel
2. Go to File Manager → the domain's public_html directory
3. Delete old files in public_html
4. Upload `dist/salar-website.zip`
5. Extract the zip in public_html
6. Verify https://salaar.cloud loads

---

### Task 4: Build Desktop App

- [ ] **Step 1: Install desktop dependencies**

```powershell
cd "C:\Users\JD\Documents\SALAR AI\desktop"
npm ci
```

Expected: Dependencies installed without errors

- [ ] **Step 2: Build Tauri release**

```powershell
cd "C:\Users\JD\Documents\SALAR AI\desktop"
$env:TAURI_SIGNING_PRIVATE_KEY = ""
npm run build
```

Note: `TAURI_SIGNING_PRIVATE_KEY=""` disables signing for now (installer is not code-signed per README).

Expected: Build completes, NSIS installer produced at `desktop/src-tauri/target/release/bundle/nsis/`

- [ ] **Step 3: Verify installer**

```powershell
Get-ChildItem desktop\src-tauri\target\release\bundle\nsis\*.exe | Select-Object Name, Length
```

Expected: One `.exe` file (SALAR_1.0.0_x64-setup.exe or similar)

- [ ] **Step 4: Copy installer to dist**

```powershell
$installer = Get-ChildItem desktop\src-tauri\target\release\bundle\nsis\*.exe | Select-Object -First 1
$dest = "C:\Users\JD\Documents\SALAR AI\dist\installer"
if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force }
Copy-Item -LiteralPath $installer.FullName -Destination "$dest\SALAR-Setup.exe" -Force
Write-Host "Installer: $($installer.FullName)"
Write-Host "Size: $([math]::Round($installer.Length / 1MB, 2)) MB"
```

---

### Task 5: Push Installer to GitHub Release (Optional)

- [ ] **Step 1: Create git tag**

```powershell
cd "C:\Users\JD\Documents\SALAR AI"
git tag -a v1.0.0 -m "Release v1.0.0 with security upgrades"
git push origin v1.0.0
```

- [ ] **Step 2: Create GitHub release with installer**

```powershell
gh release create v1.0.0 "dist\installer\SALAR-Setup.exe" --title "SALAR v1.0.0" --notes "Security upgrades: rate limiting, structured logging, CORS hardening, CSP"
```

Note: Requires `gh` CLI authenticated. If not available, create release manually at https://github.com/nwabjd/salar-ai/releases/new

---

### Task 6: Post-Deploy Verification

- [ ] **Step 1: Verify backend health**

```powershell
Invoke-RestMethod -Uri "https://salar-backend.onrender.com/api/health" | ConvertTo-Json
```

Expected: `{"status":"ok","service":"salar-backend","version":"0.1.0"}`

- [ ] **Step 2: Verify frontend loads**

Open https://salaar.cloud in browser. Expected: Login page loads, no console errors.

- [ ] **Step 3: Verify rate limiting**

```powershell
# Try 6 rapid login attempts (should hit 5/min limit)
1..6 | ForEach-Object {
    try {
        Invoke-RestMethod -Uri "https://salar-backend.onrender.com/api/auth/login" -Method POST -ContentType "application/json" -Body '{"email":"test@test.com","password":"wrong"}'
    } catch {
        Write-Host "Attempt $_`: $($_.Exception.Response.StatusCode)"
    }
}
```

Expected: First 5 return 401, 6th returns 429 (rate limited)

- [ ] **Step 4: Verify structured logging**

Check Render logs at https://dashboard.render.com → salar-backend → Logs. Expected: JSON-formatted log entries like `{"asctime":"...","levelname":"INFO","name":"salar.backend","message":"..."}`

- [ ] **Step 5: Test desktop installer**

Download and run `SALAR-Setup.exe`. Expected: App installs, launches, connects to backend.
