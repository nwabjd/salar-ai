# n8n integration — AI-triggered workflows from SALAR

Date: 2026-09-26 · Status: implemented (unreleased)

## Motivation

SALAR's agent ("list my desktop", "research X", …) is great at *doing* — but its
built-in tools end at files, email, WhatsApp, calendar, devices. A user asked to
bring the **n8n workflow-automation engine** (github.com/n8n-io/n8n) into SALAR so
that anything automatable in n8n becomes something the AI companion can trigger:
"save this page to my tracker", "post a summary to Slack", "run the week-report".

### License reality check (why this architecture)

`n8n-io/n8n` is **not** MIT. It ships under the **Sustainable Use License v1.0**
(`LICENSE.md`) with `*.ee.*` files under the n8n Enterprise License.

| Use case | Allowed? |
|---|---|
| Personal / non-commercial, self-hosted usage | ✅ Free |
| SALAR's agent calling the **user's own** n8n instance over its REST API | ✅ Free |
| Running n8n as a sidecar service *beside* SALAR (not bundled into the binary) | ✅ for personal use |
| Vendoring the engine *into* SALAR and reselling | ❌ needs n8n commercial/Embed agreement |

**Decision: never vendor n8n.** SALAR's backend talks to a separate, self-hosted
n8n instance over the **public REST API v1** (`X-N8N-API-KEY` header). This lands
in the "self-hosted / personal use" bucket regardless of how SALAR itself is run.

## What was built

### New tool group in the agent (`backend/app/services/agent.py`)

Four Gemini function declarations + `execute_tool()` dispatch cases (auto-exposed
through `backend/app/mcp_server.py` `build_tool_specs()` — no extra MCP work):

| Tool | What it does |
|---|---|
| `n8n_instance_info` | Reachability + host + first-page workflow count (pre-flight check) |
| `n8n_list_workflows` | List workflows; filters: `active_only`, `name`, `limit`; each item includes id, name, active, tags, trigger count, and **webhook trigger path/method** when present |
| `n8n_execute_workflow` | Run a workflow. **Webhook-trigger first** (send payload to the webhook node's URL), legacy `POST /api/v1/executions` as fallback. Returns how it ran + execution id when available |
| `n8n_workflow_result` | Status/result of a run. Pass `execution_id`, or just `workflow_id` to inspect the latest run. Returns `success/error/running/waiting/canceled` + timing + a compact summary of the last node outputs |

Trigger semantics came from the current API spec (`docs.n8n.io/connect/n8n-api`):
the public API exposes **no create-execution endpoint** anymore, so the reliable
supported path is a **Webhook trigger** node; we still try the legacy executions
endpoint for older instances and return a *helpful* message when neither works.

### Client (`backend/app/services/n8n_client.py`)

- `N8nClient` — async httpx client, base URL normalization (accepts
  `http://host` or `http://host/api/v1`), `X-N8N-API-KEY` auth.
- `N8NError(kind=…)` normalized errors (`auth|not_found|timeout|upstream|invalid_config`)
  so tool responses stay clean.
- `resolve_n8n_config(user_id)` — **per-user registration first**, then global env.
- Execution output extraction: walks `data.result_data.runData`, keeps the last
  item each node emitted, truncates to a bounded summary (never dumps the whole
  execution blob into the model context).

### Config & connection surfaces

- `backend/app/config.py`: `n8n_base_url`, `n8n_api_key` (`SALAR_N8N_BASE_URL`, `SALAR_N8N_API_KEY`).
- `backend/app/api/n8n.py` (new router, mirrors `email.py`):
  - `POST /api/n8n/connect` — validate the key with a real `GET /workflows?limit=1`, store per-user.
  - `GET /api/n8n/status` — which instance is active (user-registered or env).
  - `POST /api/n8n/disconnect`.
  - `backend/app/services/state.py`: `n8n_connections` in-memory store.
- Root `.env.example` + `backend/render.yaml`: both variables documented; on Render
  they're `sync: false` (entered manually, same as `SALAR_GEMINI_API_KEY`).

### Local sidecar (`docker/docker-compose.n8n.yml`)

Privacy-first option matching SALAR's local-Gemma model. Official n8n Docker image
bound to **127.0.0.1:5678 only**, data on a named volume, public API enabled
(disabled only if you opt out). One-time setup: open `http://127.0.0.1:5678`,
create the owner account → **Settings → n8n API → Create an API key** → set the two
`SALAR_N8N_*` vars (or `POST /api/n8n/connect`).

### Tests (`backend/tests/test_n8n.py`, 13 cases)

Config resolution (env vs per-user), list mapping + filters, webhook trigger,
legacy-executions fallback, helpful failure when neither is available, execution
output extraction, auth error kinds, health, agent wiring, MCP exposure.

## Getting to first workflow end-to-end

```bash
cd salar-ai
docker compose -f docker/docker-compose.n8n.yml up -d
# http://127.0.0.1:5678 → create owner → Settings → n8n API → create key
# backend/.env or Render: SALAR_N8N_BASE_URL=http://127.0.0.1:5678  SALAR_N8N_API_KEY=<key>
```

1. Build a workflow in n8n with a **Webhook trigger** on top (test webhook is fine;
   for production use a static URL under `/webhook/`).
2. `n8n_list_workflows` in SALAR shows it with its webhook path.
3. Say e.g. *"run the Slack-post workflow with 'weekly digest ready'."* →
   `n8n_execute_workflow(workflow_id, payload)` → `n8n_workflow_result(...)`.
4. For workflows without a webhook: add one, or (older n8n only) the executions
   endpoint fallback kicks in.

## Notes / gotchas

- n8n webhooks are unauthenticated by default (auth lives on the node if you
  configure it); keep the sidecar bound to 127.0.0.1 and never expose port 5678.
- API keys are full-access on Community edition; on Enterprise use scopes and
  ideally an `n8n+salar` key with `workflow:list/read`, `execution:read/list` etc.
- `n8n_workflow_result` polls latest-run when given a `workflow_id`; prefer passing
  the `execution_id` from `n8n_execute_workflow` where available.
- Not in scope (future): SALAR UI settings page for `/api/n8n`, dynamic workflow
  composition from the n8n node catalog, Callable sub-workflow support.