# SALAR Multi-Tenant Redesign — Implementation Plan

Reference: `docs/superpowers/specs/2026-08-06-salar-multi-tenant-redesign-design.md` (approved design).

## Scope

Turn SALAR into a commercial multi-tenant SaaS:

- **A. Supabase-only auth** — no password login, no pairing codes, no desktop provisioning key. Browser/desktop sign in via Supabase; backend trusts Supabase JWTs and auto-creates users.
- **B. Chat-only dashboard** — single-screen chat + live overlay, with status cards (WhatsApp, calendar, memories, documents, devices, usage/billing).
- **C. Per-user isolation** — file storage, code sandbox, and WhatsApp sessions are namespaced per user; monitor and alerts become admin-only.
- **D. Enforced monthly quota** — free 500 / Pro 5,000 messages per calendar month, checked on `/api/chat`, `/api/chat/stream`, and `/api/agent`; HTTP 429 when exceeded.

Out of scope: Stripe/PayPal payment internals (only a usage endpoint is added), visual redesign of the chat UI beyond layout changes, iOS/Android apps.

## File Structure Map

```
backend/
  app/
    config.py                 # add supabase_url/jwt_secret/audience/admin_emails; remove provisioning_key, pairing_code_minutes
    security.py               # add verify_supabase_jwt(), require_admin()
    schemas.py                # add SupabaseExchangeRequest; remove LoginRequest, DesktopProvisionRequest, PairingCodeResponse, PairingRedeemRequest
    api/
      deps.py                 # NEW: month_usage(), quota_status(), check_quota()
      auth.py                 # add POST /api/auth/supabase; remove /login, /desktop/provision, /pairing, /pairing/redeem
      chat.py                 # add Depends(check_quota) to POST /api/chat + /api/chat/stream
      agent.py                # add Depends(check_quota) to POST /api/agent; scope _get_file_manager per user; admin-gate monitor/alert tools
      billing.py              # add GET /api/billing/usage; use monthly count in /status
      files.py                # scope FileManager root per user
      code_interpreter.py     # scope sandbox per user
      whatsapp.py             # thread user.id through all routes + webhook
      monitor.py              # require_admin on all routes
      alerts.py               # require_admin on all routes
    services/
      file_manager.py         # expose module-level DEFAULT_ROOT; keep _resolve guard
      code_interpreter.py     # add workdir/sandbox param
      whatsapp.py             # WhatsAppClient methods take user_id
    main.py                   # gate bootstrap user to non-production
  whatsapp/
    bridge.js                 # rewrite: per-user sessions keyed by user_id
  tests/
    conftest.py               # test supabase settings; auth_headers via /api/auth/supabase; supabase_token fixture
    test_auth.py              # rewrite for Supabase exchange
    test_pairing.py           # DELETE
    test_quota.py             # NEW
    test_isolation.py         # NEW (files, code sandbox, whatsapp routing, admin-only monitor/alerts)
    test_billing.py           # extend /usage + monthly count
frontend/
  src/
    api.ts                    # remove login/redeem/provision/pairing; add supabaseLogin(token), usage(); drop 30s stream concerns unchanged
    access.ts                 # collapse states: checking | connected | signed-out
    main.tsx                  # chat-only shell; remove PairingPortal, View union, sidebar nav, connection tab
    components/SalaarLanding.tsx  # Supabase sign-in gate (email OTP) instead of ?app entry
    src/tests/access.test.ts  # rewrite for new state machine
docs/superpowers/specs/2026-08-06-salar-multi-tenant-redesign-design.md  # approved design (read-only)
```

## Feature Test Plan

| Area | What we verify |
|---|---|
| Auth | `/api/auth/supabase` with a valid Supabase HS256 JWT creates a user and returns an app token; invalid/expired JWT → 401; `/me` requires bearer; existing user re-login is idempotent; first login auto-admin when email in `admin_emails` |
| Quota | Free user at/over limit → 429 `{quota_exceeded, used, limit, reset_at}` on all three message endpoints; admin exempt; pro/team limit from `pro_monthly_quota`; usage counts only current calendar month; `GET /api/billing/usage` shape |
| Isolation | Two users have disjoint file roots; traversal blocked; per-user code sandboxes; WhatsApp bridge keyed by `user_id`; non-admin gets 403 on `/api/monitor/*` and `/api/alerts/*` |
| Frontend | `access.ts` state machine collapses to 3 states; `api.ts` exposes `supabaseLogin`/`usage` and no longer exposes password/pairing methods; dashboard renders chat-only |
| Regression | `pytest backend/tests` (minus deleted files) and `npm test` green after each phase |

Run backend tests with `cd backend && python -m pytest tests -q`. Run frontend tests with `cd frontend && npm test`.

---

## Phase 1 — Supabase-only Auth

### Task 1.1: Config — Supabase settings, drop provisioning

**Goal:** Settings carries Supabase connection + admin list; old shared-secret auth settings removed.

**Files:** `backend/app/config.py`

**Edit** `backend/app/config.py`:

- Remove line 36 `provisioning_key: str = "salar-local-setup"` and line 37 `pairing_code_minutes: int = 5`.
- Add after `jwt_secret` / `token_minutes` block:

```python
    supabase_url: Optional[str] = None
    supabase_jwt_secret: Optional[str] = None
    supabase_audience: str = "authenticated"
    admin_emails: List[str] = Field(default_factory=list)
```

Keep `bootstrap_email`/`bootstrap_password` (used only for the non-prod bootstrap seed).

**Tests:** none directly (covered by conftest in 1.5).

**Commit:** `chore(config): add supabase settings, drop provisioning/pairing keys`

---

### Task 1.2: security.py — Supabase JWT verification + require_admin

**Goal:** A trust-bridge helper that validates a Supabase HS256 access token and an admin guard dependency.

**Files:** `backend/app/security.py`

**Add** (after existing helpers; `jwt` is already imported for `create_access_token`):

```python
def verify_supabase_jwt(token: str, settings) -> tuple[str, str]:
    """Return (sub, email) for a valid Supabase HS256 access token, else raise 401."""
    if not settings.supabase_url or not settings.supabase_jwt_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase is not configured")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=settings.supabase_audience,
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
            options={"require": ["exp", "sub", "email"]},
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return str(payload["sub"]), str(payload["email"]).lower()


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
```

**Tests:** covered by 1.5 (invalid token) and Phase 3 (admin-only 403).

**Commit:** `feat(security): verify supabase HS256 tokens; add require_admin`

---

### Task 1.3: Schemas — add SupabaseExchangeRequest, drop old auth schemas

**Files:** `backend/app/schemas.py`

- Add:

```python
class SupabaseExchangeRequest(BaseModel):
    token: str
```

- Remove `LoginRequest`, `DesktopProvisionRequest`, `PairingRedeemRequest`, `PairingCodeResponse`.
- Keep `TokenResponse`, `UserResponse`, `DeviceSessionResponse`, `DeviceSessionToken`.

**Commit:** `refactor(schemas): swap password/pairing schemas for supabase exchange`

---

### Task 1.4: auth.py — Supabase exchange endpoint; remove password/pairing/provisioning

**Goal:** `/api/auth/supabase` is the only way in. Auto-create users on first login. Admin is derived from `admin_emails`.

**Files:** `backend/app/api/auth.py`

**Add** the endpoint (keep existing `/me`, `/session`, `/devices`, `/devices/{device_id}`):

```python
@router.post("/supabase", response_model=TokenResponse)
def supabase_login(payload: SupabaseExchangeRequest, request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    sub, email = verify_supabase_jwt(payload.token, settings)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(id=sub, email=email, is_admin=email in settings.admin_emails)
        db.add(user)
        db.commit()
        db.refresh(user)
    db.add(AuditEvent(user_id=user.id, action="auth.supabase_login", detail_json="{}"))
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user, settings.jwt_secret, settings.token_minutes)
    )
```

**Remove** the decorators + bodies of: `POST /login` (lines 19–31), `POST /desktop/provision` (62–75), `POST /pairing` (83–90), `POST /pairing/redeem` (93–111). Remove now-unused helpers `_new_device_session` (39–55) and `_code_digest` (58–59).

**Update imports:** drop `hashlib`, `secrets`, `PairingCode`, and the removed schemas; import `verify_supabase_jwt` from `..security` and `SupabaseExchangeRequest` from `..schemas`. Keep `datetime`, `timezone` (used by revoke), `timedelta` only if still referenced — otherwise drop it. Delete the empty `PairingCode` references.

Note: `DeviceSession` rows will no longer be created (no provisioning/pairing), but the model + list/revoke routes stay for compatibility with existing rows.

**Tests:** 1.5.

**Commit:** `feat(auth): supabase exchange endpoint; remove password/pairing/provisioning`

---

### Task 1.5: main.py — bootstrap only in non-production

**Goal:** Production has no seeded password account; admins come from Supabase + `admin_emails`.

**Files:** `backend/app/main.py`

**Edit** the lifespan bootstrap block (lines 66–83): wrap the `try:` that creates the owner user in:

```python
if active_settings.environment != "production":
    try:
        ... existing owner-user block ...
    except Exception as e:
        log.error("Bootstrap user setup failed: %s", e)
```

If `hash_password` is then unused at module scope, keep the import (still used inside the block).

**Commit:** `fix(main): seed bootstrap user only in non-production`

---

### Task 1.6: Tests — Supabase exchange, drop pairing

**Goal:** Tests mint real Supabase-style JWTs and log in through the exchange endpoint.

**Files:** `backend/tests/conftest.py`, `backend/tests/test_auth.py`; delete `backend/tests/test_pairing.py`

**conftest.py:**

- When constructing the test app's `Settings`, override with:

```python
Settings(
    environment="test",
    database_url="sqlite://",   # keep existing test db strategy
    supabase_url="https://test.supabase.co",
    supabase_jwt_secret="test-supabase-secret",
    supabase_audience="authenticated",
    admin_emails=["admin@example.com"],
    ...existing overrides...
)
```

- Add a `supabase_token` fixture that mints a valid token for a given sub/email:

```python
import time
import jwt as pyjwt

def make_supabase_token(settings, email="tester@example.com", sub="11111111-2222-3333-4444-555555555555", expires_in=3600):
    now = int(time.time())
    return pyjwt.encode(
        {
            "sub": sub,
            "email": email,
            "aud": settings.supabase_audience,
            "iss": f"{settings.supabase_url.rstrip('/')}/auth/v1",
            "iat": now,
            "exp": now + expires_in,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
```

- Rewrite the `auth_headers` fixture: POST the supabase token to `/api/auth/supabase`, take the returned `access_token`, return `{"Authorization": f"Bearer {access_token}"}`. Provide a second fixture `admin_headers` that exchanges `email="admin@example.com"`.

**test_auth.py** — rewrite the 3 tests to:

1. `test_supabase_exchange_creates_user` — valid token → 200, `token_type == "bearer"`, user row exists with the supabase `sub` as id; `/me` with returned token returns the email.
2. `test_supabase_exchange_rejects_invalid_token` — garbage token and expired token (`expires_in=-1`) → 401.
3. `test_me_requires_bearer` — no header → 401.
4. `test_first_login_admin_from_admin_emails` — `email="admin@example.com"` → `/me.is_admin` true.

Delete `test_pairing.py` (pairing endpoints no longer exist).

**Commit:** `test(auth): supabase exchange coverage; drop pairing tests`

---

## Phase 2 — Enforced Monthly Quota

### Task 2.1: deps.py — usage query + quota guard

**Goal:** Shared monthly-usage calculation and a `Depends` guard that raises 429.

**Files:** `backend/app/api/deps.py` (new)

```python
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Conversation, Message, User
from ..security import get_current_user


def month_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def month_usage(db: Session, user_id: str) -> int:
    start, _end = month_bounds(datetime.now(timezone.utc))
    return (
        db.scalar(
            select(func.count(Message.id))
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Conversation.user_id == user_id, Message.created_at >= start)
        )
        or 0
    )


def quota_status(db: Session, user: User, settings) -> dict:
    if user.is_admin:
        limit = None
    elif user.plan in ("pro", "team"):
        limit = settings.pro_monthly_quota
    else:
        limit = settings.free_monthly_quota
    used = month_usage(db, user.id)
    _start, reset_at = month_bounds(datetime.now(timezone.utc))
    return {
        "plan": user.plan,
        "limit": limit,
        "used": used,
        "reset_at": reset_at.isoformat(),
        "exempt": user.is_admin,
    }


def check_quota(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    quota = quota_status(db, user, request.app.state.settings)
    limit = quota["limit"]
    if limit is not None and quota["used"] >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "quota_exceeded": True,
                "used": quota["used"],
                "limit": limit,
                "reset_at": quota["reset_at"],
            },
        )
    return quota
```

Note: `Message.created_at` is stored with the model's `utcnow()` default. Keep the aware-UTC comparison here; the quota test in 2.5 will confirm it filters the current month correctly on SQLite.

**Commit:** `feat(quota): monthly usage query and 429 guard`

---

### Task 2.2: chat.py — enforce quota on chat endpoints

**Goal:** `/api/chat` and `/api/chat/stream` refuse to run when the monthly limit is reached.

**Files:** `backend/app/api/chat.py`

- Import: `from .deps import check_quota`.
- In both `chat` and `chat_stream`, add a parameter `quota: dict = Depends(check_quota)` after `user`. `Depends(check_quota)` runs before the body and raises 429. The returned dict is unused inside the endpoints for now (it exists so the check runs eagerly and is available later).
- No change to message insertion — the count naturally grows after each turn.

**Commit:** `feat(quota): enforce limit on /api/chat and /api/chat/stream`

---

### Task 2.3: agent.py — enforce quota on /api/agent

**Goal:** The bare agent endpoint is quota-guarded too.

**Files:** `backend/app/api/agent.py`

- At `POST /api/agent` (line 48), add `quota: dict = Depends(check_quota)` after the `user` parameter and import `from .deps import check_quota`.

**Commit:** `feat(quota): enforce limit on /api/agent`

---

### Task 2.4: billing.py — usage endpoint + monthly status

**Goal:** `GET /api/billing/usage` returns quota shape; `/api/billing/status` uses the shared monthly count.

**Files:** `backend/app/api/billing.py`

- Import: `from .deps import quota_status`.
- Add:

```python
@router.get("/usage")
def usage(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return quota_status(db, user, request.app.state.settings)
```

- Replace the body of `billing_status` (lines 352–364) so `usage`, `limit`, `plan` come from `quota_status(db, user, settings)`, and add `"reset_at"` to the returned dict. Keep `payment_methods`.

**Commit:** `feat(billing): expose monthly usage and reset date`

---

### Task 2.5: Tests — quota

**Goal:** Lock down the 429 behavior, limits, admin exemption, and monthly rollover.

**Files:** `backend/tests/test_quota.py` (new)

Seed helper:

```python
def seed_message(db, user_id, created_at):
    conv = Conversation(user_id=user_id, title="q")
    db.add(conv)
    db.flush()
    db.add(Message(conversation_id=conv.id, role="user", content="x", created_at=created_at))
    db.flush()
    return conv
```

Tests:

1. `test_free_user_under_limit_can_chat` — fresh free user → POST `/api/chat` (with a conversation) returns 200.
2. `test_free_user_at_limit_gets_429` — set `free_monthly_quota=2` in the test `Settings`, seed 2 messages this month → POST `/api/chat` → 429; response JSON `detail` has `quota_exceeded == True`, `limit == 2`, and a `reset_at` ISO string.
3. `test_pro_user_limit_from_config` — set `pro_monthly_quota=5000`; upsert user plan to `pro`; seed 4999 → 200; seed 1 more → 429.
4. `test_admin_exempt_from_quota` — admin user at/over limit → 200.
5. `test_usage_only_counts_current_month` — seed messages `datetime.now(utc) - timedelta(days=40)` → `used == 0` for a user with one stale message.
6. `test_billing_usage_endpoint` — GET `/api/billing/usage` → `{"plan", "limit", "used", "reset_at", "exempt"}` present.

Wire the same 429 test shape for `/api/agent` (assert 429 when over limit).

**Commit:** `test(quota): limits, rollover, admin exemption`

---

## Phase 3 — Per-User Isolation

### Task 3.1: File storage per user

**Goal:** Every user's files live under `storage_dir/users/{user_id}`; traversal guard stays.

**Files:** `backend/app/services/file_manager.py`, `backend/app/api/files.py`, `backend/app/services/agent.py`

- `file_manager.py`: add a module-level `DEFAULT_ROOT: Optional[Path] = None`. In `FileManager.__init__`, resolve `root = root or DEFAULT_ROOT or Path.home()`; keep `_resolve` as the only path-jail. Ensure the resolved root exists (mkdir) before first read/write.
- `files.py`: replace the global `_get_fm()` with:

```python
def _get_fm(request: Request, user: User) -> FileManager:
    root = request.app.state.settings.storage_dir / "users" / user.id
    return FileManager(root=root)
```

and change every route to call `_get_fm(request, user)` (all routes already receive `request` or can be given `request: Request`).
- `agent.py`: change `_get_file_manager()` (line 1511) to `_get_file_manager(user_id)` returning `FileManager(root=DEFAULT_ROOT / user_id)`. Set `DEFAULT_ROOT` in `main.py` lifespan from `active_settings.storage_dir / "users"` before yield, so API routes and agent tools agree. Update callers `_file_list/_file_read/_file_write/_file_search/_file_info` (1516–1562).

**Tests:** in `test_isolation.py` (3.5).

**Commit:** `feat(files): namespace storage per user`

---

### Task 3.2: Code sandbox per user

**Goal:** Each user's Python execution runs in its own sandbox dir; output/time limits unchanged.

**Files:** `backend/app/services/code_interpreter.py`, `backend/app/api/code_interpreter.py`, `backend/app/services/agent.py`

- `services/code_interpreter.py`: add a `workdir` param to `CodeInterpreter.__init__`; when set, `execute_python` runs the tempfile script inside `workdir` (or passes `cwd=workdir`), keeping `MAX_OUTPUT=50000`, `TIMEOUT=30`.
- `code_interpreter.py` API: change `_get_interp()` to `_get_interp(user)` returning `CodeInterpreter(workdir=settings.storage_dir / "users" / user.id / "sandbox")` (mkdir recursive). Thread `user` from each route's existing `Depends(get_current_user)`.
- `agent.py` `_code_run` (line 1573): build the interpreter from `DEFAULT_ROOT / user_id / "sandbox"`.

**Commit:** `feat(code): isolate interpreter sandbox per user`

---

### Task 3.3: WhatsApp per-user bridge sessions

**Goal:** Each user owns a separate WhatsApp session and can only read/send their own.

**Files:** `backend/whatsapp/bridge.js`, `backend/app/services/whatsapp.py`, `backend/app/api/whatsapp.py`

**bridge.js** — rewrite the singleton into a per-user session manager. Minimal diff approach:

- `AUTH_DIR` becomes a base dir (env `WA_AUTH_DIR`, default `/app/data/wa-auth` on Render, else `path.join(__dirname, 'auth')`).
- Replace `let sock/connectionStatus/qrCode/lastDisconnectReason/recentChats/messageStore` globals with a `Map<userId, session>` where each session object holds `{ sock, status, qr, reason, chats, store, timer }`.
- Factor the existing `startWhatsApp()` body into `startSession(userId)` using `AUTH_DIR/userId` for auth state; keep reconnect-on-close and clear-and-repair-on-loggedOut per session (clearing only that user's dir).
- Routes become per-user. Read `userId` from a header `x-user-id` (sent by the backend) and 400 if missing/unknown:

```js
app.get('/status', (req, res) => { const s = getSession(req); if (!s) return res.json({ status: 'missing' }); ... });
app.get('/qr', (req, res) => ...same with s.qr...);
app.post('/send', async (req, res) => { const s = getSession(req); if (!s?.sock || s.status !== 'connected') return res.status(503).json({ error: 'WhatsApp not connected' }); ...existing body using s.sock / s.store... });
app.get('/chats', ...s.chats...);
app.get('/messages/:jid', ...s.store...);
app.get('/contacts', ...s.sock.store...);
app.post('/logout', async (req, res) => { await s.sock.logout(); s.status = 'logged_out'; ... });
```

  Lazy-start sessions: `/start` (or first `/status`/`/qr` for an unknown user) calls `startSession(userId)`.
- `forwardToBackend` gains a `userId` arg and includes `user_id: userId` in the webhook payload.

**services/whatsapp.py** — `WhatsAppClient` methods (`get_status`, `get_qr`, `send_message`, `close`, and the chat/contacts readers if present) accept `user_id: str` and send it as `X-User-Id` on every request. Default user_id handling: keep `close()` idempotent.

**api/whatsapp.py** — every route takes `user: User = Depends(get_current_user)` and passes `user.id` to the client. The webhook route must read `user_id` from the body and, for replies/auto-reply, scope coordinator calls to that user. `GET /pass-messages` and `POST /pass-messages/{event_id}/acknowledge` filter by `user.id`.

**Tests:** in 3.5.

**Commit:** `feat(whatsapp): per-user bridge sessions and webhook routing`

---

### Task 3.4: Monitor + alerts admin-only

**Goal:** System telemetry and alert management are restricted to admins; agent tools respect it too.

**Files:** `backend/app/api/monitor.py`, `backend/app/api/alerts.py`, `backend/app/services/agent.py`

- `monitor.py`: change every route's `user: User = Depends(get_current_user)` to `user: User = Depends(require_admin)`. Import `require_admin` from `..security`.
- `alerts.py`: same for `list_rules`, `create_rule`, `delete_rule`, `toggle_rule`, `list_triggered`, `acknowledge_alert`.
- `agent.py`: for `_get_monitor_stats` (1822), `_list_processes_agent` (1827), `_create_alert_rule` (1832), `_list_alert_rules` (1843), `_list_triggered_alerts` (1851): load the user via the passed `db_session`; if `not user.is_admin` return `{"error": "Admin access required"}` as the tool result instead of executing.

**Commit:** `feat(rbac): monitor and alerts admin-only`

---

### Task 3.5: Tests — isolation

**Goal:** Verify tenant boundaries end-to-end.

**Files:** `backend/tests/test_isolation.py` (new)

1. `test_file_roots_are_per_user` — user A writes `notes.txt` via `/api/files/write`; user B's `/api/files/list` is empty; A still sees it. Also assert files for A live under `storage_dir/users/{A.id}`.
2. `test_file_traversal_blocked` — writing `../x` returns 400/422 (guard holds under the new root).
3. `test_code_sandbox_per_user` — `/api/code/execute` succeeds for both users; assert no cross-user file access (write in A's sandbox, B's `list` empty via files API).
4. `test_monitor_requires_admin` — free user → GET `/api/monitor/...` → 403; admin → 200.
5. `test_alerts_require_admin` — free user → GET `/api/alerts/rules` → 403; admin → 200.
6. `test_whatsapp_route_threads_user` — with a stubbed `WhatsAppClient` on `app.state.whatsapp`, GET `/api/whatsapp/status` returns the user-scoped call (assert client received `user_id == user.id`).

**Commit:** `test(isolation): per-user files, sandbox, whatsapp, admin rbac`

---

## Phase 4 — Chat-Only Dashboard (Frontend)

### Task 4.1: api.ts — Supabase login + usage, drop legacy auth

**Goal:** The API client talks only to the new auth surface.

**Files:** `frontend/src/api.ts`

- Remove `login(email, password)`, `provisionDesktop(key)`, `createPairingCode()`, `redeemPairingCode(...)`.
- Add:

```typescript
async supabaseLogin(token: string) {
  const data = await this.request('/api/auth/supabase', { method: 'POST', body: JSON.stringify({ token }) })
  return data as { access_token: string; token_type: string }
}

async usage() {
  return this.request('/api/billing/usage') as Promise<{ plan: string; limit: number | null; used: number; reset_at: string; exempt: boolean }>
}
```

- Keep `billingStatus()` (the frontend pricing page still uses it). Keep stream + timeouts unchanged.

**Commit:** `feat(api): supabase exchange + usage; drop legacy auth methods`

---

### Task 4.2: access.ts — three-state machine

**Goal:** Remove `pairing` and `desktop-disconnected`; sessions are app JWTs from Supabase exchange.

**Files:** `frontend/src/access.ts`

- Collapse `AccessState` to `'checking' | 'connected' | 'signed-out'`.
- `resolveAccessState`: if a stored session exists → `connected`, else → `signed-out` (no pairing branch). `saveSession`/`clearSession` stay; `invoke` stays for actions.

**Tests:** rewrite `frontend/src/tests/access.test.ts` for the three states (stored session → connected; none → signed-out; clearing → signed-out).

**Commit:** `refactor(access): collapse to checking|connected|signed-out`

---

### Task 4.3: main.tsx — chat-only shell

**Goal:** Single-screen app: chat is the main pane; a right rail shows status cards; live overlay stays; all view switching, pairing, and connection settings go away.

**Files:** `frontend/src/main.tsx`

- Remove: `View` union (line 28), `PairingPortal` (39–83), the sidebar/nav view-state in `App` (85–166), the `?preview=dashboard` special-casing for a full dashboard, and `SettingsPage`'s `connection` tab + `provision()` + `createCode()` + pairing UI (1256–1261). Alerts stay inside Settings but only render for admin users (from `/api/auth/me` `is_admin`).
- `App` becomes: top bar (brand, plan/usage chip via `api.usage()`, Live toggle, sign-out) + two-column layout:
  - Main: the existing `Chat` component (conversation list, messages, composer).
  - Rail: compact cards reusing existing components' data: WhatsApp status/QR (from `WhatsApp` component data hooks), today's calendar (`CalendarView`), memories (`Memories`), documents (`Documents`), devices (`Devices`), and a usage meter (from `usage()`).
  - `Live` remains the full-screen overlay launched from the top bar.
- `Root` (1407–1412): replace the `?app` gate. If `previewShell` or an existing Supabase session → run exchange → `App`; otherwise `SalaarLanding` as the sign-in gate.
- Move `PricingPage` + `PLANS` to `frontend/src/components/PricingPage.tsx` (export them) and import from `main.tsx`; the pricing screen is reachable from the plan/usage chip.

**Commit:** `feat(ui): chat-only dashboard with status rail`

---

### Task 4.4: SalaarLanding — Supabase sign-in gate

**Goal:** Landing page becomes the login page. Email-OTP via Supabase; on authenticated session, exchange and enter.

**Files:** `frontend/src/components/SalaarLanding.tsx`, `frontend/src/lib/supabase.ts`

- `lib/supabase.ts`: keep `createClient`/`isSupabaseConfigured`/`supabase`; add `getSession()` helper returning `supabase.auth.getSession()`.
- `SalaarLanding`: add an email input; on submit `supabase.auth.signInWithOtp({ email })` → show "Check your email". Subscribe to `supabase.auth.onAuthStateChange`; on `SIGNED_IN`, call `api.supabaseLogin(session.access_token)`, `saveSession(access_token)`, set access `connected`, and enter `App`. If Supabase is not configured (`isSupabaseConfigured()` false), keep the current preview/copy-only landing (no `Enter app` button path to a broken app).
- Replace the old `onEnterApp` prop with the session-gated `onAuthenticated` flow.

**Commit:** `feat(ui): supabase sign-in gate on landing page`

---

## Phase 5 — Configuration, Docs, Verification

### Task 5.1: Environment + docs

**Goal:** Render and local env carry the new settings; repo docs note the removal.

**Files:** `backend/.env.example` (or `frontend/.env.example` for `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY`), `docs/superpowers/specs/2026-08-06-salar-multi-tenant-redesign-design.md` (append "Deployment notes")

- Backend env: add `SALAR_SUPABASE_URL`, `SALAR_SUPABASE_JWT_SECRET`, `SALAR_SUPABASE_AUDIENCE=authenticated`, `SALAR_ADMIN_EMAILS=["you@domain.com"]`; remove `SALAR_PROVISIONING_KEY`, `SALAR_PAIRING_CODE_MINUTES`. Note `SALAR_ENVIRONMENT=production` on Render disables the bootstrap seed.
- Frontend env: document `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` as required in production.

**Commit:** `docs(config): deployment env for supabase auth and quotas`

### Task 5.2: Full verification

- `cd backend && python -m pytest tests -q` — all green (test_pairing.py deleted).
- `cd frontend && npm test` — all green.
- `cd frontend && npm run build` — no TS errors.
- Manual smoke on `http://127.0.0.1:8000/docs`: exchange endpoint present; `/login` gone.

**Commit:** none (verification task).

---

## Final Review

After all tasks: re-read the design doc, confirm each section (A/B/C/D) is implemented, run the full verification in 5.2, and update the design doc's status to "implemented" with the deployment notes. Flag remaining open items (Azure secret, PayPal rotation, WhatsApp re-pairing) in the doc.
