# SALAR — Personal Intelligence

SALAR is a private, multi-device AI assistant. The desktop application, installable web app, and mobile browser experience all use one authenticated public FastAPI backend. That backend keeps Ollama, memory, documents, and permission-aware device commands behind a single secure API.

## What is included

- FastAPI backend with JWT login, SQLite persistence, Ollama coordination, conversations, layered memory, projects, document extraction/search, audit records, and typed device commands.
- Responsive React client with the approved Liquid Ether dashboard, exact Magic Rings Live mode, continuous browser speech recognition, document upload, memory, device management, and runtime backend selection.
- Progressive Web App that can be installed on iPhone from Safari using **Add to Home Screen**.
- Tauri 2 Windows application with fullscreen first launch, a native safe command allow-list, automatic device registration, and background command polling.
- Docker Compose + Caddy deployment with automatic HTTPS.
- Original SALAR neural-aperture application icon and generated platform sizes.

## Local development

Backend:

```powershell
cd backend
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
$env:VITE_API_URL="http://127.0.0.1:8000"
npm run dev
```

The initial development login is `owner@salar.local` / `ChangeMeImmediately!`. Change both values before putting the backend on the internet.

## Deploy on your domain

1. Point two DNS records at the server: for example `salar.example.com` and `api.salar.example.com`.
2. Copy `.env.example` to `.env`, replace every secret and domain, and set `SALAR_WEB_DOMAIN` / `SALAR_API_DOMAIN`.
3. Ensure Ollama runs only on the backend machine or a private network. Do not expose port 11434 publicly.
4. Build the clients with the real public API URL:

```powershell
.\scripts\build-release.ps1 -ApiUrl "https://api.yourdomain.com"
```

5. Upload `dist/website` to any static host, or launch everything with:

```powershell
docker compose --env-file .env -f docker/docker-compose.yml up -d --build
```

Caddy obtains TLS certificates automatically after DNS is active. For remote desktop commands, SALAR Desktop must be running and logged in. Commands are restricted to explicit types; file-revealing and directory-creation actions require approval in the client that issued them.

## Release outputs

- Website/PWA: `dist/website`
- Windows installer: `dist/installer/SALAR_1.0.0_x64-setup.exe`
- Brand source: `assets/salar-icon.png`

The installer is not code-signed. Windows SmartScreen may warn until a trusted code-signing certificate is configured.
