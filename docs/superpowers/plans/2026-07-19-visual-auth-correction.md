# SALAR Visual and Access Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the exact approved dark React Bits visual system and replace the installed desktop login wall with device provisioning plus one-time web/mobile pairing.

**Architecture:** FastAPI will add hashed, revocable device sessions and five-minute single-use pairing codes while retaining JWT login as recovery. The React client will use a platform-aware access state machine: Tauri always opens the dashboard and provisions from Settings, while browsers without a session see only the pairing surface. Visual tokens and effect props will be isolated and regression-tested so warm legacy styling cannot return.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, React 19, TypeScript, Vitest, React Bits LiquidEther/MagicRings, Tauri 2, Rust, Vite PWA, NSIS.

---

## File map

- `backend/app/models.py`: device session and pairing-code persistence.
- `backend/app/schemas.py`: provisioning, pairing, and session contracts.
- `backend/app/security.py`: bearer authentication for JWTs and hashed device secrets.
- `backend/app/api/auth.py`: provision, create/redeem pairing, validate, and revoke endpoints.
- `backend/app/config.py`: provisioning secret and pairing/session lifetimes.
- `backend/tests/test_pairing.py`: complete access-flow regression coverage.
- `frontend/src/access.ts`: platform-aware credential storage and access-state helpers.
- `frontend/src/access.test.ts`: desktop/browser state tests.
- `frontend/src/api.ts`: session, provisioning, and pairing API calls.
- `frontend/src/main.tsx`: non-blocking desktop shell, browser pairing, and Settings provisioning.
- `frontend/src/theme.css`: approved visual constants and smoke-glass surfaces.
- `frontend/src/theme.test.ts`: visual constant/legacy-color regression tests.
- `frontend/src/styles.css`: layout and responsive behavior using theme tokens.
- `.env.example`, `README.md`: provisioning and pairing deployment instructions.

### Task 1: Persist device sessions and pairing codes

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/tests/test_pairing.py`

- [ ] **Step 1: Write the failing persistence and contract test**

```python
def test_desktop_provisioning_returns_device_session(client):
    response = client.post(
        "/api/auth/desktop/provision",
        json={"provisioning_key": "test-provisioning-key", "name": "Studio PC"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["access_token"].startswith("sds_")
    assert body["device"]["name"] == "Studio PC"
```

- [ ] **Step 2: Run the test and verify the endpoint is missing**

Run: `cd backend; python -m pytest tests/test_pairing.py::test_desktop_provisioning_returns_device_session -q`

Expected: FAIL with status `404`.

- [ ] **Step 3: Add configuration and database models**

Add settings:

```python
provisioning_key: str = "salar-local-setup"
pairing_code_minutes: int = 5
device_session_days: int = 365
```

Add `DeviceSession` with `user_id`, `name`, `platform`, `token_hash`, `expires_at`, `revoked_at`, `last_seen_at`, and timestamps. Add `PairingCode` with `user_id`, `code_hash`, `expires_at`, `redeemed_at`, and timestamps. Store only SHA-256 hashes.

- [ ] **Step 4: Add Pydantic contracts**

```python
class DesktopProvisionRequest(BaseModel):
    provisioning_key: str
    name: str = "SALAR Desktop"

class PairingRedeemRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    name: str
    platform: str = "web"

class DeviceSessionToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    device: DeviceResponse
```

- [ ] **Step 5: Run the focused test to confirm models import but endpoint remains red**

Run: `cd backend; python -m pytest tests/test_pairing.py::test_desktop_provisioning_returns_device_session -q`

Expected: FAIL with status `404`, with no model/config import error.

- [ ] **Step 6: Commit the persistence slice**

```powershell
git add backend/app/models.py backend/app/config.py backend/app/schemas.py backend/tests/test_pairing.py
git commit -m "test: define device pairing contracts"
```

### Task 2: Implement provisioning and dual bearer authentication

**Files:**
- Modify: `backend/app/security.py`
- Modify: `backend/app/api/auth.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_pairing.py`

- [ ] **Step 1: Add failing authorization tests**

```python
def test_device_session_authenticates_existing_api(client, provisioned_session):
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {provisioned_session}"},
    )
    assert response.status_code == 200

def test_wrong_provisioning_key_is_rejected(client):
    response = client.post(
        "/api/auth/desktop/provision",
        json={"provisioning_key": "wrong", "name": "Unknown PC"},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd backend; python -m pytest tests/test_pairing.py -q`

Expected: FAIL because provisioning and device bearer lookup are not implemented.

- [ ] **Step 3: Implement device secret creation and authentication**

Create raw secrets as `sds_` plus `secrets.token_urlsafe(32)`, hash them with SHA-256, return them once, and extend `get_current_user`:

```python
if credentials.credentials.startswith("sds_"):
    digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    session = db.scalar(select(DeviceSession).where(
        DeviceSession.token_hash == digest,
        DeviceSession.revoked_at.is_(None),
        DeviceSession.expires_at > datetime.now(timezone.utc),
    ))
    if session is None:
        raise HTTPException(status_code=401, detail="Device session is invalid or expired")
    return db.get(User, session.user_id)
```

- [ ] **Step 4: Implement `/api/auth/desktop/provision` and `/api/auth/session`**

Provision only when `secrets.compare_digest(payload.provisioning_key, settings.provisioning_key)` succeeds. Attach the new session to the configured bootstrap owner, audit `auth.desktop_provisioned`, and return the raw secret once. `/api/auth/session` returns the current user and session validity through the shared dependency.

- [ ] **Step 5: Run pairing and legacy authentication tests**

Run: `cd backend; python -m pytest tests/test_pairing.py tests/test_auth.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/security.py backend/app/api/auth.py backend/tests/conftest.py backend/tests/test_pairing.py
git commit -m "feat: provision secure desktop sessions"
```

### Task 3: Implement single-use browser pairing and revocation

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_pairing.py`

- [ ] **Step 1: Add failing pairing lifecycle tests**

```python
def test_pairing_code_is_single_use(client, device_headers):
    created = client.post("/api/auth/pairing", headers=device_headers).json()
    first = client.post("/api/auth/pairing/redeem", json={
        "code": created["code"], "name": "JD iPhone", "platform": "ios"
    })
    replay = client.post("/api/auth/pairing/redeem", json={
        "code": created["code"], "name": "Replay", "platform": "web"
    })
    assert first.status_code == 201
    assert replay.status_code == 409

def test_revoked_device_session_is_rejected(client, device_headers, device_session_id):
    assert client.delete(f"/api/auth/devices/{device_session_id}", headers=device_headers).status_code == 204
    assert client.get("/api/auth/session", headers=device_headers).status_code == 401
```

- [ ] **Step 2: Run tests and verify missing endpoints**

Run: `cd backend; python -m pytest tests/test_pairing.py -q`

Expected: FAIL with `404` on pairing endpoints.

- [ ] **Step 3: Implement code generation, redemption, listing, and revocation**

Generate cryptographically random six-digit codes, hash before storage, expire after `pairing_code_minutes`, mark `redeemed_at` in the same transaction that creates the browser session, and reject replay with `409`. Provide authenticated device listing and revocation. Add audit events for create, redeem, reject, and revoke.

- [ ] **Step 4: Verify pairing and all backend regressions**

Run: `cd backend; python -m pytest -q`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/api/auth.py backend/app/schemas.py backend/tests/test_pairing.py
git commit -m "feat: add one-time device pairing"
```

### Task 4: Add the client access state machine

**Files:**
- Create: `frontend/src/access.ts`
- Create: `frontend/src/access.test.ts`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: Add Vitest and failing access-state tests**

```typescript
import { describe, expect, it } from 'vitest'
import { resolveAccessState } from './access'

describe('resolveAccessState', () => {
  it('opens an unprovisioned desktop shell', () => {
    expect(resolveAccessState({ desktop: true, token: '' })).toBe('desktop-disconnected')
  })
  it('requires pairing for an unpaired browser', () => {
    expect(resolveAccessState({ desktop: false, token: '' })).toBe('pairing')
  })
  it('connects either platform with a device session', () => {
    expect(resolveAccessState({ desktop: false, token: 'sds_example' })).toBe('connected')
  })
})
```

- [ ] **Step 2: Run tests and verify missing module failure**

Run: `cd frontend; npm test -- access.test.ts`

Expected: FAIL because `access.ts` does not exist.

- [ ] **Step 3: Implement access helpers and API methods**

```typescript
export type AccessState = 'checking' | 'connected' | 'desktop-disconnected' | 'pairing'
export function isDesktop() { return Boolean((window as any).__TAURI_INTERNALS__) }
export function resolveAccessState(input:{desktop:boolean;token:string}):AccessState {
  if (input.token) return 'connected'
  return input.desktop ? 'desktop-disconnected' : 'pairing'
}
```

Add `provisionDesktop`, `createPairingCode`, `redeemPairingCode`, `validateSession`, `listDeviceSessions`, and `revokeDeviceSession` to `SalarApi`. Store the returned `sds_` secret under `salar.deviceSession`.

- [ ] **Step 4: Run frontend tests**

Run: `cd frontend; npm test`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/package.json frontend/package-lock.json frontend/src/access.ts frontend/src/access.test.ts frontend/src/api.ts
git commit -m "feat: add platform-aware access state"
```

### Task 5: Replace the login wall with pairing and Settings provisioning

**Files:**
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/access.test.ts`

- [ ] **Step 1: Add failing client behavior assertions**

Extend tests to assert desktop-disconnected is a dashboard-capable state and browser pairing remains blocking. Add source-level assertions that `main.tsx` does not render `type="email"` or the `Enter SALAR` heading.

- [ ] **Step 2: Run tests and verify the legacy login assertion fails**

Run: `cd frontend; npm test`

Expected: FAIL because the legacy email login still exists.

- [ ] **Step 3: Implement `PairingPortal`**

Render six numeric cells, paste support, expiry/error copy, and a `Pair device` action. On redemption, persist the returned session and enter the dashboard.

- [ ] **Step 4: Make desktop launch non-blocking**

Remove `Login`. Initialize access from `salar.deviceSession`; always render the desktop dashboard. When disconnected, show a compact status and keep backend-dependent commands disabled with inline guidance to Settings.

- [ ] **Step 5: Add Settings provisioning and pairing controls**

Settings accepts API URL and one-time provisioning key only while disconnected. After connection it shows `Create pairing code`, the five-minute code, registered device sessions, and revoke controls. Never persist the provisioning key.

- [ ] **Step 6: Run tests**

Run: `cd frontend; npm test`

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/main.tsx frontend/src/styles.css frontend/src/access.test.ts
git commit -m "feat: replace login with device pairing"
```

### Task 6: Restore and lock the approved visual system

**Files:**
- Create: `frontend/src/theme.css`
- Create: `frontend/src/theme.test.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Add failing visual regression tests**

```typescript
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

const theme = readFileSync(new URL('./theme.css', import.meta.url), 'utf8')
const main = readFileSync(new URL('./main.tsx', import.meta.url), 'utf8')

describe('approved SALAR visual system', () => {
  it('locks the dark canvas and exact effect colors', () => {
    expect(theme).toContain('--canvas: #050308')
    expect(main).toContain("['#5227FF','#FF9FFC','#B497CF']")
    expect(main).toContain('color="#fc42ff" colorTwo="#42fcff"')
  })
  it('excludes legacy warm palette values', () => {
    for (const legacy of ['#edc9bd', '#f0d1c7', '#f5d8cb']) expect(theme).not.toContain(legacy)
  })
})
```

- [ ] **Step 2: Run tests and verify missing theme failure**

Run: `cd frontend; npm test -- theme.test.ts`

Expected: FAIL because `theme.css` is missing.

- [ ] **Step 3: Implement visual tokens and remove warm overlays**

```css
:root {
  --canvas: #050308;
  --canvas-live: #03030a;
  --ink: #f7f4ff;
  --muted: #aaa4b4;
  --glass: rgba(12, 10, 18, .46);
  --glass-strong: rgba(8, 7, 13, .72);
  --line: rgba(255, 255, 255, .10);
}
```

Remove `.app-shell:after` and every warm gradient/tint. Keep Liquid Ether unfiltered and full-opacity. Use only neutral smoke surfaces, white typography, and component-native color.

- [ ] **Step 4: Preserve exact effect isolation**

Dashboard mounts Liquid Ether only. Live Mode unmounts the dashboard and mounts Magic Rings only. Loading mounts Strands only. No effect shares a screen with another effect.

- [ ] **Step 5: Run unit and production builds**

Run: `cd frontend; npm test; npm run build`

Expected: tests PASS and Vite/PWA build succeeds.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/theme.css frontend/src/theme.test.ts frontend/src/main.tsx frontend/src/styles.css
git commit -m "fix: restore approved SALAR visual system"
```

### Task 7: Document deployment and migration

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Document the provisioning secret**

Add `SALAR_PROVISIONING_KEY` with instructions to generate at least 32 random bytes, use it only once per desktop, rotate after provisioning, and never embed it in the website build.

- [ ] **Step 2: Document the user flow**

Describe desktop direct launch, Settings provisioning, browser/iPhone pairing, session revocation, and recovery JWT endpoint. Remove the normal-flow default email/password instructions.

- [ ] **Step 3: Verify documentation contains no production default secret**

Run: `rg -n "ChangeMeImmediately|salar-local-setup" README.md .env.example`

Expected: no matches.

- [ ] **Step 4: Commit**

```powershell
git add .env.example README.md
git commit -m "docs: explain secure SALAR device pairing"
```

### Task 8: Rebuild, inspect, and package corrected releases

**Files:**
- Modify generated output: `dist/website/**`
- Modify generated output: `dist/installer/SALAR_1.0.0_x64-setup.exe`

- [ ] **Step 1: Run the complete verification suite**

Run:

```powershell
cd backend; python -m pytest -q
cd ..\frontend; npm test; npm run build
cd ..\desktop\src-tauri; cargo test --quiet
```

Expected: every command exits `0`.

- [ ] **Step 2: Build both release artifacts**

Run: `.\scripts\build-release.ps1 -ApiUrl "https://api.salar.example.com"`

Expected: the website directory and NSIS installer are produced.

- [ ] **Step 3: Inspect the packaged website**

Serve `dist/website`, open it in the local browser, and verify: near-black canvas; exact Liquid Ether; no email/password form on desktop; pairing on web; exact Magic Rings after entering Live Mode; no warm overlay.

- [ ] **Step 4: Verify artifact integrity**

Run:

```powershell
Get-FileHash -Algorithm SHA256 dist\installer\SALAR_1.0.0_x64-setup.exe
git diff --check
git status --short
```

Expected: installer hash is printed, diff check is clean, and only intentionally ignored release artifacts remain outside Git.

- [ ] **Step 5: Commit any final source-only corrections and report exact artifact paths**

```powershell
git add -u
git commit -m "fix: ship corrected SALAR experience"
```
