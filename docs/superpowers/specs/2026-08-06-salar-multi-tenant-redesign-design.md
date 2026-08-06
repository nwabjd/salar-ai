# SALAR commercial multi-tenant redesign

## Objective

Turn SALAR from a single-owner, pairing-code app into a commercial multi-tenant product. Anyone signs up through the landing page (Supabase), logs into a chat-only dashboard, and gets per-user data isolation with server-enforced monthly quotas. The personal computer / desktop device-control remains, tied to each account.

Approved by the user on 2026-08-06. This document is the source of truth for the implementation plan.

## Confirmed product direction

- Supabase is the only login. The backend trusts a Supabase-verified session and auto-creates the user on first sign-in.
- Pairing codes, backend password login, provisioning keys, and the bootstrap user are removed from the product path.
- The app is a chat-only dashboard: one conversation screen. All features are reachable through the agent's tools, with a few dedicated screens for billing, WhatsApp QR pairing, and plan/usage.
- Everything is per-user: files, WhatsApp accounts, code interpreter sandboxes. Monitor and alerts are admin-only.
- Quota = messages per calendar month, enforced server-side (Free 500, Pro 5,000).
- The liquid aurora background approved in the preview stays.

## Approaches considered

### Chat-only single surface — selected

One chat screen is the entire product surface. The agent's ~80 tools already cover files, WhatsApp, email, calendar, tasks, reminders, memory, knowledge, browser, system control, code execution, and workflows. Dedicated UI is kept only where a chat card cannot do the job well (billing/pricing, WhatsApp QR, plan/usage meter). This matches the approved preview and removes ~15 redundant views.

### Retain the 16-view dashboard

Keeping the full dashboard costs significant per-view isolation work and contradicts the approved conversational direction. Rejected.

### Hybrid (chat + drawer)

A chat surface plus a collapsible drawer for tools. Nice-to-have, but scope creep for v1 of the commercial launch. Deferred.

## A. Auth — Supabase is the only gate

### Landing sign-in

`SalaarLanding.tsx` already renders Supabase providers (Google, GitHub, Azure, wallet, email OTP) behind an env-gated `lib/supabase.ts` client. Flow:

1. User signs in on the landing page → Supabase session (access token).
2. Frontend POSTs the Supabase access token to backend `POST /api/auth/supabase`.
3. Backend verifies the token signature against the Supabase project's public JWKS, checks `aud` and `exp`.
4. On success, backend upserts the user by email (`plan` defaults to `free`, `is_admin` stays `false`), then issues its own short-lived JWT (`sub=user.id`) and returns it plus user metadata.
5. Frontend stores the backend JWT in the existing session mechanism and enters the app.

All existing `get_current_user` and `Depends(get_current_user)` code keeps working because the backend JWT shape is unchanged.

### Removed paths

- 6-digit pairing codes: `redeemPairingCode`, `createPairingCode`, and their API routes.
- Backend `/api/auth/login` with email/password and password hashing for product users.
- `provisioning_key` provisioning flow and config value.
- Bootstrap admin auto-creation on startup stays only in development environments (guarded by `settings.environment != "production"`), used as a local admin fallback. In production the first admin is assigned via the DB or a `SALAR_ADMIN_EMAILS` env list.

### Desktop

- The Tauri desktop window loads the same web app and signs in via Supabase inside the window. Same account → same `user.id` → existing device polling works.
- Existing long-lived `sds_` device sessions remain supported so a connected desktop does not re-prompt after sign-in.
- `access.ts` state machine collapses to `checking → connected | logged-out`; the `pairing` state and `PairingPortal` go away.

### Config additions

- `supabase_url`, `supabase_jwt_secret` (or JWKS URL), `supabase_audience`.
- `admin_emails: List[str]`.

## B. Chat-only dashboard

### Layout

Single conversation screen per the approved preview:

- Top bar: SALAR wordmark, account menu (email, plan, sign out), usage meter chip.
- Center: message stream with the liquid aurora background behind it.
- Bottom: persistent composer with attachment and voice affordances.
- Contextual chat cards injected into the stream: WhatsApp QR pairing, usage/plan meter, device list/status.

### Engine

- `POST /api/agent` remains the primary engine. It is already per-user scoped (conversations, memories, documents filter by `user.id`).
- `POST /api/chat` remains for no-tool conversational fallback. Both routes are quota-counted.
- New minimal endpoints:
  - `GET /api/billing/usage` → `{month, used, limit, plan}` for the usage chip and enforcement messaging.
  - WhatsApp QR: reuse `GET /api/whatsapp/qr` (per-user after Section C) surfaced as a chat card.
  - `GET /api/devices` already exists for device list.

### Removed UI

- The 16-item sidebar and `View` union switch in `main.tsx`.
- `PairingPortal` and its two-tab (code / email+password) flow.
- Dedicated view pages for memory, documents, files, tasks, reminders, email, calendar, knowledge, workflows, workspaces, monitor, alerts — the agent tools cover them.

## C. Per-user isolation

### Already per-user (verified in `services/agent.py`)

Conversations, messages, memories, documents, tasks, reminders, workspaces, workflows, projects all filter by `user_id == user.id`.

### Files

`files.py` / `file_manager.py` currently write to a server-global uploads dir.

- Storage root becomes `storage_dir / users / {user_id}`.
- Every list/read/write/delete/search op scopes to the owner's root.
- The `file_*` agent tools already receive `user_id` from `execute_tool` — they inherit the fix.

### WhatsApp (largest change)

Today: one global Node bridge session (`backend/whatsapp/`), admin auto-reply, single `WA_AUTH_DIR`.

Target:

- One connection per user. The bridge keys sessions by user id; auth data stored under `WA_AUTH_DIR/{user_id}`.
- `services/whatsapp.py` `WhatsAppClient` becomes a manager: `get_client(user_id)` lazily spawns/starts a session, `get_qr(user_id)`, `send_message(user_id, ...)`, etc.
- API routes take the authenticated `user` and pass `user.id` down.
- Webhook payloads include the owning account/connection id; inbound messages route to the owning user; auto-reply is configured per user (`User.whatsapp_auto_reply` already exists per user).
- The WhatsApp tools (`whatsapp_send`, `whatsapp_read`, `whatsapp_list_chats`, `whatsapp_search`) scope to the current user's connection.

### Code interpreter

`code_interpreter.py` executes in a server-global workspace.

- Each execution runs in `storage_dir / sandboxes / {user_id} / {execution_id}`.
- Enforce per-user resource/time limits and cleanup on completion.

### Monitor and alerts

Admin-only. `monitor.py`, `alerts.py`, and the `get_monitor_stats` / alert tools return 403 (or empty) for non-admins. The alert and reminder background engines keep running but all rows remain user-scoped (already the case).

### Storage

Render already mounts a persistent disk at `/app/data`. Per-user dirs live under it (`/app/data/uploads/users/{id}`, `/app/data/sandboxes/{id}`, `/app/data/wa-auth/{id}`).

## D. Enforced monthly quota

### Counting

- A message round-trip = one user message through `/api/agent` or `/api/chat` that is persisted as a `Message` row.
- Counting window = current calendar month (UTC).
- Implement as a FastAPI dependency `check_quota` applied to the chat and agent routes: count `Message` rows for `(user.id, month_start <= created_at)`.

### Enforcement

- `used >= limit` → `HTTPException 429`, detail `{"detail": "Monthly message limit reached", "quota_exceeded": true, "reset_at": "<first day of next month>"}`.
- Plan lookup from `User.plan` (`free` 500, `pro` 5000). Billing already sets `plan` on payment.
- Admin users are exempt.

### Frontend

- `GET /api/billing/usage` powers a header chip: "247 / 500 messages this month".
- On 429 the composer shows the upsell state (link to `/pricing`, banner), and the message is not sent.
- Exempt flag surfaced for admin users.

## Open questions

- Azure provider secret + tenant URL still missing from the user (blocks that one sign-in method, not the rest).
- Rotate the PayPal secret (it appeared in chat history and previously in `.env.example`).

## What this touches

- `backend/app/config.py` — new settings, remove provisioning.
- `backend/app/security.py` — Supabase JWT verification helper; keep backend JWT issuance.
- `backend/app/api/auth.py` — add `/auth/supabase`, remove pairing/login paths.
- `backend/app/main.py` — bootstrap gated to dev; router wiring.
- `backend/app/api/files.py`, `app/services/file_manager.py` — per-user roots.
- `backend/app/api/whatsapp.py`, `app/services/whatsapp.py`, `backend/whatsapp/` — per-user sessions.
- `backend/app/api/code_interpreter.py`, `app/services/code_interpreter.py` — per-user sandboxes.
- `backend/app/api/monitor.py`, `app/api/alerts.py` — admin-only.
- `backend/app/api/agent.py`, `app/api/chat.py` — quota dependency.
- `backend/app/api/billing.py` — usage endpoint.
- `backend/app/models.py` — add `Usage` (or rely on Message counts) and any session/connection model.
- `frontend/src/main.tsx`, `frontend/src/access.ts`, `frontend/src/api.ts` — chat-only shell, remove pairing.
- `frontend/src/components/SalaarLanding.tsx`, `frontend/src/lib/supabase.ts` — become the real gate.
- Tests: `backend/tests/` and frontend tests must stay green; add auth-isolation and quota tests.
