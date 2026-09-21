# WhatsApp Customer Service (official Meta Cloud API)

A production-oriented customer-service capability for SALAAR, built on the **official
Meta WhatsApp Business Platform (Cloud API)**. It handles inbound customer messages,
answers them with the existing AI orchestration layer, escalates to a human when
appropriate, and gives admins a dashboard for conversations, knowledge, and settings.

> **Scope note.** This is a **new, modular capability**. It does **not** modify or
> replace the existing per-user personal WhatsApp bridge (unofficial Web automation)
> served under `/api/whatsapp/*`. The two integrations coexist independently.
> Nothing here claims live message delivery: the Cloud API adapter is only exercised
> against mocks until real Meta credentials are configured (see
> [Live verification](#live-verification-and-rollout)).

---

## 1. Architecture

```
Meta WhatsApp Cloud API
        │  webhook (HTTPS, X-Hub-Signature-256)
        ▼
POST /api/whatsapp-cs/webhook        (backend/app/api/whatsapp_cs.py)
        │  verify signature · parse · idempotently persist
        ▼
process_webhook_payload              (backend/app/services/whatsapp_cs_engine.py)
        │  writes customer / conversation / message / webhook-event ledger
        │  creates one background task per new inbound message
        ▼
reply_worker                         (async, in-process)
        │
        ├─ loop guard + human-takeover check
        ├─ deterministic escalation (human requested / sensitive topic)
        ├─ knowledge retrieval (keyword scoring)      (whatsapp_cs_store.py)
        ├─ Gemini generation via existing coordinator  (whatsapp_cs_agent.py)
        ├─ normalization + escalation decision
        └─ outbox row → Meta send_text                 (whatsapp_cs_cloud.py)
                │
                ▼
        delivery/read statuses come back on the same webhook and reconcile the outbox.
```

Admin surface: `GET /api/whatsapp-cs/overview` … (see [API reference](#5-api-reference)),
rendered in the workspace **WhatsApp CS** view (`frontend/src/workspace/WhatsAppCSView.tsx`).

The AI call reuses the existing provider abstraction
(`app.state.coordinator.gemini.chat_with_tools`), so model/provider behavior and
credentials are unchanged from the rest of SALAAR.

---

## 2. Configuration

All configuration is server-side. **Secrets live only in environment variables** and
are never stored in the database or returned by any API (every response is
credential-free; `secrets_in_db` is always `false`).

| Variable | Default | Purpose |
| --- | --- | --- |
| `SALAR_WHATSAPP_CS_ENABLED` | `false` | Feature flag for the capability. |
| `SALAR_WHATSAPP_CS_ACCESS_TOKEN` | — | Meta system-user / permanent access token. **Secret.** |
| `SALAR_WHATSAPP_CS_PHONE_NUMBER_ID` | — | Cloud API phone-number ID that sends messages. |
| `SALAR_WHATSAPP_CS_BUSINESS_ACCOUNT_ID` | — | WhatsApp Business Account (WABA) ID. |
| `SALAR_WHATSAPP_CS_VERIFY_TOKEN` | — | Arbitrary token you also paste into Meta's webhook config. **Secret.** |
| `SALAR_WHATSAPP_CS_APP_SECRET` | — | Meta app secret, used to validate `X-Hub-Signature-256`. **Secret.** |
| `SALAR_WHATSAPP_CS_API_VERSION` | `v23.0` | Graph API version. |
| `SALAR_WHATSAPP_CS_AI_ENABLED` | `true` | Server-side master switch for automatic replies. |
| `SALAR_WHATSAPP_CS_AI_MODEL` | *(falls back to `SALAR_GEMINI_MODEL`)* | Model for the CS agent. |
| `SALAR_WHATSAPP_CS_DEFAULT_FALLBACK` | *(short hold message)* | Sent when the model returns nothing usable. |

Non-secret metadata (phone-number ID, WABA ID, display name, AI settings) is editable
from the dashboard and stored per account in `whatsapp_cs_settings` /
`whatsapp_cs_accounts`. Environment values act as fallbacks.

Placeholders for local development are in [`backend/.env.example`](../backend/.env.example).
Never commit real values; never log them (the code only logs boolean presence/IDs).

---

## 3. Meta setup

1. Create a Meta app of type **Business** and add the **WhatsApp** product.
2. Add a phone number, then copy the **Phone number ID** and **WhatsApp Business
   Account ID** into `SALAR_WHATSAPP_CS_PHONE_NUMBER_ID` / `..._BUSINESS_ACCOUNT_ID`.
3. Create a **permanent token** for a system user with `whatsapp_business_messaging`
   and `whatsapp_business_management`; set it as `SALAR_WHATSAPP_CS_ACCESS_TOKEN`.
4. Copy the app's **App secret** into `SALAR_WHATSAPP_CS_APP_SECRET`.
5. Pick any random string for `SALAR_WHATSAPP_CS_VERIFY_TOKEN` (e.g. `openssl rand -hex 24`).
6. Set the webhook:
   - **Callback URL:** `https://<your-backend-host>/api/whatsapp-cs/webhook`
   - **Verify token:** the same value as `SALAR_WHATSAPP_CS_VERIFY_TOKEN`
   - **Subscribe to fields:** `messages` (covers inbound messages **and** status updates).
7. Set `SALAR_WHATSAPP_CS_ENABLED=true` and restart the backend.

Meta will call `GET /api/whatsapp-cs/webhook?hub.mode=subscribe&hub.verify_token=…&hub.challenge=…`;
the server echoes the challenge only when the token matches.

---

## 4. Behavior

### Inbound pipeline
- **Verification:** `GET` echoes `hub.challenge` only for `hub.mode=subscribe` and a
  correct `hub.verify_token`.
- **Signature:** every `POST` must carry a valid `X-Hub-Signature-256`
  (HMAC-SHA256 of the raw body). Invalid or missing signatures return `403`;
  an unconfigured app secret returns `503`.
- **Idempotency:** each event is recorded in `whatsapp_cs_webhook_events`; a redelivered
  message id is a no-op. New inbound messages are keyed by the unique Meta
  `external_message_id`.
- **Async:** the webhook returns immediately after persisting; replies run in a
  background task so Meta always gets a fast `200`.
- **Own-number guard:** messages whose sender equals the business phone number are ignored.
- **Loop guard:** an inbound message identical to a reply we sent in the last 2 minutes is
  treated as an echo and never re-answered (prevents automated response loops).
- **Media:** image/audio/video/document/sticker/location/contacts messages are stored with
  their metadata and a readable placeholder body (e.g. `[image] please advise`).

### AI agent
- Answers **only** from the configured knowledge base and cannot invent facts on
  regulated topics (prices, policies, legal, medical). If it does not know, it says so
  and escalates.
- Treats all customer text as untrusted data and ignores embedded instructions
  (prompt-injection resistant).
- Replies in the customer's language when known, and stays within a configurable length.
- A hidden marker lets the model request human help; a deterministic escalation layer also
  triggers on explicit human requests and, optionally, sensitive topics (refunds, legal,
  complaints).

### Human handover
- Escalation sets `handling_mode = human` and `status = human`; the AI stops replying
  until an admin clicks **Resume AI**.
- Admins can assign a representative by email, reply manually, add internal notes,
  resolve, or reopen. A manual reply always switches the conversation to human-driven.

---

## 5. API reference

Public (signature-protected):

| Method | Path | Notes |
| --- | --- | --- |
| `GET` | `/api/whatsapp-cs/webhook` | Meta verification challenge. |
| `POST` | `/api/whatsapp-cs/webhook` | Meta events; rate-limited `600/minute`. |

Authenticated (any logged-in user):

| Method | Path |
| --- | --- |
| `GET` | `/api/whatsapp-cs/status` |

Admin-only (`require_admin`, 403 otherwise):

| Method | Path |
| --- | --- |
| `GET` | `/api/whatsapp-cs/overview` |
| `GET` | `/api/whatsapp-cs/conversations?status=&search=&limit=&offset=` |
| `GET` | `/api/whatsapp-cs/conversations/{id}` |
| `POST` | `/api/whatsapp-cs/conversations/{id}/assign` |
| `POST` | `/api/whatsapp-cs/conversations/{id}/unassign` |
| `POST` | `/api/whatsapp-cs/conversations/{id}/reply` |
| `POST` | `/api/whatsapp-cs/conversations/{id}/resume-ai` |
| `POST` | `/api/whatsapp-cs/conversations/{id}/resolve` |
| `POST` | `/api/whatsapp-cs/conversations/{id}/reopen` |
| `POST` | `/api/whatsapp-cs/conversations/{id}/notes` |
| `GET/POST` | `/api/whatsapp-cs/knowledge` |
| `PUT` | `/api/whatsapp-cs/knowledge/{id}` |
| `POST` | `/api/whatsapp-cs/knowledge/{id}/toggle` |
| `DELETE` | `/api/whatsapp-cs/knowledge/{id}` |
| `GET/PUT` | `/api/whatsapp-cs/ai-settings` |
| `GET/PUT` | `/api/whatsapp-cs/connection` |

Admin actions are written to the existing `audit_events` table
(`whatsapp_cs.admin.*`). Responses never include credentials.

---

## 6. Data model

Created automatically on startup (`Base.metadata.create_all`); no migration step is
required. All tables are scoped by `account_id` so multi-business support can be added
without a rewrite.

| Table | Contents |
| --- | --- |
| `whatsapp_cs_accounts` | Single business account row + non-secret connection metadata. |
| `whatsapp_cs_customers` | One row per WhatsApp number (`wa_id`, profile name, language). |
| `whatsapp_cs_conversations` | Status, handling mode, assignment, escalation reason, notes. |
| `whatsapp_cs_messages` | Full thread (inbound + outbound), delivery status, media metadata. |
| `whatsapp_cs_knowledge` | Knowledge-base entries (category, title, body, tags, active). |
| `whatsapp_cs_outbound` | Send outbox with idempotency key + delivery/error state. |
| `whatsapp_cs_webhook_events` | Webhook dedupe ledger. |
| `whatsapp_cs_settings` | Per-account non-secret settings (AI, connection). |

The outbox row is committed **before** the external send, and carries a unique
idempotency key, so a crash can never produce a double-send.

---

## 7. Security model

- **Authorization is enforced server-side.** Every admin route depends on
  `require_admin`; non-admins receive `403` and anonymous callers `401`. This is the
  authoritative gate (the dashboard merely reflects it).
- **Secrets** are read from the environment only. They are never persisted, never
  serialized, and never logged.
- **Webhook authenticity** is enforced with HMAC-SHA256 signature validation; the raw
  body is used, so the signature cannot be bypassed by JSON reshaping.
- **Rate limiting** on the webhook (600/min) plus the global slowapi limiter.
- **RLS note.** Production data currently lives in SQLite on the mounted disk
  (Supabase is used for auth only), so Postgres row-level security does not apply today.
  Authorization is therefore application-side. When the data layer moves to Postgres,
  add RLS policies on the `whatsapp_cs_*` tables keyed to the authenticated user/admin
  role; the schema is already `account_id`-scoped to make that mapping straightforward.

---

## 8. Admin dashboard

Workspace → **WhatsApp CS** (`#/whatsapp-cs`), with four tabs:

- **Overview** — active / AI / human / unresolved / resolved counts, 7-day new leads,
  delivery breakdown, and recent activity (click through to a thread).
- **Inbox** — filter/search conversations, read the thread, reply manually, assign a
  rep, resume AI, resolve/reopen, and add internal notes.
- **Knowledge** — create, edit, activate/deactivate, and delete entries. The AI answers
  from these entries only.
- **Connection** — connection status and which credentials are present (booleans only),
  editable non-secret metadata, and AI settings (enabled, model, length, fallback,
  sensitive-topic escalation).

---

## 9. Testing

Backend (`backend/`):

```bash
.venv/Scripts/python.exe -m pytest tests/test_whatsapp_cs.py -q
```

42 tests cover verification, signatures, idempotency/redelivery, media, own-number and
loop guards, status reconciliation, the AI pipeline (success, fallback, escalation,
human takeover, disabled AI, LLM failure, transient vs permanent send failure), KB
retrieval, outbox idempotency, and the full admin API including secret-non-exposure.
Live sends are always mocked (`FakeCloud`) — no external network calls.

Frontend (`frontend/`):

```bash
node ./node_modules/vitest/vitest.mjs run
node ./node_modules/typescript/bin/tsc -b
```

`src/whatsapp-cs-contract.test.ts` asserts the API surface, endpoint separation from the
personal bridge, navigation/shell wiring, the four tabs, and that no credentials ship to
the browser.

---

## 10. Deployment

The capability ships as part of the normal backend image; no extra service is needed.

1. Add the `SALAR_WHATSAPP_CS_*` environment variables to the Render service
   (Dashboard → Environment, or the Render API). Keep the three secrets out of logs.
2. Deploy. On boot, `create_all` creates the new tables and the app logs
   `WhatsApp Customer Service Cloud API client initialized`.
3. Point Meta's webhook at `https://<backend-host>/api/whatsapp-cs/webhook` and verify.
4. Open the **WhatsApp CS → Connection** tab; the status should read `verified`.
5. Add knowledge entries before enabling automatic replies.

The in-process background tasks are suitable for the current single-instance Render
deployment. On a multi-instance/horizontally-scaled setup, move `reply_worker` onto the
existing background-worker/queue mechanism to avoid duplicate processing.

---

## 11. Acceptance criteria

- [x] Webhook verification echoes the challenge only for the right token/mode.
- [x] Invalid/missing signature is rejected; unconfigured webhook returns 503.
- [x] Redelivered events are idempotent (no duplicate messages/replies).
- [x] Inbound messages persist customer, conversation, and message.
- [x] Delivery/read statuses reconcile the outbox and the message.
- [x] AI replies are generated, normalized, and dispatched through an idempotent outbox.
- [x] AI answers only from the knowledge base and never invents facts.
- [x] Explicit human requests and (optionally) sensitive topics escalate without the LLM.
- [x] Human takeover pauses AI; Resume AI restores it.
- [x] Admins can list/detail/reply/assign/resolve/reopen and add notes.
- [x] Knowledge CRUD + active toggle works and drives retrieval.
- [x] Admin routes are enforced server-side; secrets never leave the server.
- [x] Mocked tests pass; docs and env placeholders are in place.
- [ ] **Live** send/receive verified with real Meta credentials (see below).

---

## 12. Live verification and rollout

This is the one criterion that **cannot** be marked done in code alone. It requires real
Meta Business credentials, which were not available during implementation. To finish it:

1. Complete [Meta setup](#3-meta-setup) and set the env vars on Render.
2. In Meta's **Configuration → Webhooks**, click **Test** — expect a `200` and a green check.
3. Send a WhatsApp message from a real handset to the business number; confirm it appears
   in **WhatsApp CS → Inbox** and that the status transitions
   `sent → delivered → read` on the Overview tab.
4. Reply from the dashboard; confirm it arrives on the handset.
5. Trigger an escalation ("I want to talk to a human"); confirm the AI stops and the
   conversation moves to human.
6. Only then flip automatic replies to on for production traffic.

Until step 4 succeeds end-to-end, treat delivery as **unverified**. The code makes no
claim of live messaging.

---

## 13. Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Webhook returns `503` | `SALAR_WHATSAPP_CS_APP_SECRET` not set. |
| Webhook returns `403` | Signature mismatch — wrong app secret or a proxy mutating the body. |
| Meta webhook verification fails | `SALAR_WHATSAPP_CS_VERIFY_TOKEN` differs from the value in Meta. |
| `status = incomplete` on Connection | Missing access token, phone-number ID, or WABA ID. |
| No AI reply | AI disabled (`SALAR_WHATSAPP_CS_AI_ENABLED` or the dashboard toggle), conversation in human mode, empty knowledge base, or the loop guard suppressed an echo. |
| Manual reply `502` | Meta rejected the send (expired token, 24-hour window, invalid recipient); check the outbox `error_json`. |
| Duplicate concern | Outbox and webhook-event unique keys make duplicates a no-op by design. |
