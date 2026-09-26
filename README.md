# SALAR — Personal Intelligence

SALAR is a private, multi-device AI assistant. The desktop application, installable web app, and mobile browser experience all use one authenticated public FastAPI backend. That backend keeps Ollama, memory, documents, and permission-aware device commands behind a single secure API.

## What is included

- FastAPI backend with revocable device sessions, one-time pairing, recovery authentication, SQLite persistence, Ollama coordination, conversations, layered memory, projects, document extraction/search, audit records, and typed device commands.
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

SALAR Desktop opens directly without an account form. On first setup, open **Settings**, set the public API address to your backend, and sign in with your Supabase account. The hosted Supabase sign-in runs outside the client window and the resulting access token is stored locally by the client.

The web app and mobile clients sign in directly through Supabase with the same account. Email/password authentication remains available through Supabase for recovery but is not part of the normal client experience.

## Local model (Gemma 4 on-device brain)

Local mode routes chat through the SALAR desktop app to Ollama on the user's PC (`127.0.0.1:11434`), where the model can call the same PC-control tools as the cloud brain. The default local model is **`salar-gemma4-e2b`** (Gemma 4 E2B, ~7.2 GB, 2.3B effective params — built for laptops/edge), with **`salar-gemma4-e4b`** (4.5B effective, more reliable tool-calling) available as an alternative in the local-mode dropdown.

Install on any machine with Ollama:

```powershell
.\scripts\install-local-models.ps1          # pulls gemma4:e2b/e4b + creates salar-gemma4-*
.\scripts\install-local-models.ps1 -SkipPull # recreate the models without re-downloading
```

The Modelfiles (`Modelfile.gemma4-e2b`, `Modelfile.gemma4-e4b`) carry the SALAR PC-control persona; Gemma 4's native function calling and system-role support mean no custom chat template is needed. The default model name is configurable via `SALAR_OLLAMA_DEFAULT_MODEL` (server) and is passed through the desktop app unchanged.

## Model Context Protocol (MCP)

MCP is used **by SALAR, for SALAR** — it extends what SALAR can do for you; SALAR's own capabilities stay inside the assistant and are never exposed as a service for other assistants.

**SALAR as an MCP client** — SALAR's agent can call tools on external MCP servers (GitHub, filesystem, browser, databases…) via its own `mcp_tools` / `mcp_call` agent tools. Configure the servers once:

```
SALAR_MCP_SERVERS='[{"name":"github","command":"npx","args":["-y","@modelcontextprotocol/server-github"],"env":{"GITHUB_PERSONAL_ACCESS_TOKEN":"..."}}]'
```

then ask SALAR in chat: *"list what the github MCP server can do"* / *"use the github server to open an issue"*.

Developer note: the backend also ships `app/mcp_server.py`, a stdio server exposing the same tool set — used only for SALAR's own internal automation (e.g., connecting to itself on the desktop), not as a product surface for other assistants.

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
