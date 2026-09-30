# Seller marketplace integration — Amazon SP-API + noon Partner API

Date: 2026-09-30 · Status: implemented (awaiting seller credentials for live validation)

## Motivation

SALAR's user sells on **Amazon** and **noon** across UAE + KSA (+ Egypt on
noon). They asked SALAR to *"manage the noon and Amazon seller accounts and
have all the information regarding these selling platforms"* — i.e.:

- **See everything**: orders, sales, inventory, pricing, product status on
  demand.
- **Take actions**: update prices / stock (with per-action approval).
- **Know the platforms**: built-in reference of how each platform works.
- **Daily briefing**: one combined report across both marketplaces.

## License / architecture reality check

- **Amazon SP-API**: official public REST API for sellers. Auth = self-authorized
  **private application** (LWA client + refresh token) + an IAM role assumed via
  STS, requests signed with **AWS SigV4**. All of this is implemented in
  `services/marketplace/amazon_client.py` with the standard library only.
- **noon Partner API**: official public API at `noon-api-gateway.noon.partners`.
  Auth = service-account RS256 JWT → login → cookie. Implemented in
  `services/marketplace/noon_client.py` using the existing `PyJWT` dependency.
- **No SDKs are vendored** into SALAR. Both platforms are driven strictly over
  their public HTTP APIs, exactly like the n8n integration. Real credentials are
  required **per seller** — SALAR is neutral infrastructure.

## What was built

### Connector package `backend/app/services/marketplace/`

- `amazon_client.py` — `AmazonClient` (async httpx): LWA token exchange, STS
  AssumeRole (XML parse), SigV4 signer (stdlib `hmac`/`hashlib`), token/session
  caching. Methods: seller info, order metrics, recent orders (no buyer PII),
  FBA inventory, listing read, price update, quantity update (Listings Items
  API `PATCH` via `PUT /listings/2021-08-01/items/{sellerId}/{sku}`).
  Region table `NA|EU|FE`; Middle-East marketplaces (AE/SA) live in the **EU**
  region (`sellingpartnerapi-eu.amazon.com`, aws `eu-west-1`).
- `noon_client.py` — `NoonClient`: RS256 JWT login (cookie kept by httpx),
  `whoami`, `pricing/get`, `pricing/upsert`, `stock-list`, `stock-update`
  (absolute quantities). Countries `ae|sa|eg`.
- `__init__.py` — config resolution (**per-user state first, env fallback** —
  same as n8n), client factories (test-injectable `transport`), normalized
  `MarketplaceError`.

### Agent tools (`backend/app/services/agent.py`)

13 tools auto-exposed also through `backend/app/mcp_server.py` `build_tool_specs()`:

Read: `marketplace_status`, `amazon_seller_info`, `amazon_sales`,
`amazon_recent_orders`, `amazon_inventory`, `amazon_listing`, `noon_pricing`,
`noon_stock`, `marketplace_daily_summary`.
Write: `amazon_update_price`, `amazon_update_quantity`, `noon_update_price`,
`noon_update_stock`.

Writes are registered in `services/permissions.py` (`_WRITE_TOOLS`, category
`marketplace` added to `CATEGORIES`) and classified **dangerous** in
`services/missions/safety.py` — they always require user approval (unless the
user's permission profile is set to autonomous), and reads are `safe`.

### API surface `backend/app/api/marketplace.py` (registered in `main.py`)

- `POST /api/marketplace/amazon/connect` — live health check (sellers API)
  before storing the per-user registration in-memory.
- `POST /api/marketplace/noon/connect` — live `whoami` check.
- `GET /api/marketplace/status` — configured? source (user/env)? non-secret
  identity (region, marketplaces/countries). **Never echoes credentials.**
- `POST /api/marketplace/{amazon,noon}/disconnect`.

### Config / deployment

- `backend/app/config.py` — `SALAR_AMAZON_*` + `SALAR_NOON_*` settings block.
- `backend/app/services/state.py` — `marketplace_connections` in-memory store.
- `.env.example` + `backend/render.yaml` (all `sync: false`, entered manually —
  never committed).

## Tests (`backend/tests/test_marketplace.py` — 34 tests)

Service tests run over `httpx.MockTransport` (no network): config resolution
(env / per-user / key-file), Amazon LWA+STS+SigV4 flow with header assertions,
all read/write method payloads and mappings, error kinds, Noon JWT login +
cookie + 401 re-login, pricing/stock read/write, agent wiring (tool surface,
unconfigured errors, arg validation), MCP exposure, permission/safety
classification, and the `/api/marketplace` routes (status, env status, 422s,
disconnect).

## Platform knowledge & onboarding

- `docs/marketplace/amazon-seller-guide.md` — click-by-click SP-API setup
  (Developer Central app → LWA security profile → IAM role → self-authorize →
  `.env`), platform reference (marketplaces/regions, fees, endpoint mapping,
  troubleshooting).
- `docs/marketplace/noon-seller-guide.md` — noon onboarding (seller approval →
  partner API access → Developer Portal service account → `.env`), platform
  reference (countries, FBPI/FBPO, endpoints, troubleshooting).

## Follow-ups (not in this change)

- Seed the two `docs/marketplace/*-seller-guide.md` references into the per-user
  **knowledge base** (`knowledge_documents` + `search_knowledge`) so SALAR can
  answer fee/policy/onboarding questions directly in chat.
- noon **Content** (product creation), **FBPI** orders/shipments, **Reports**
  exports; Amazon marketplace Egypt as soon as Amazon opens it; a morning-report
  schedule (natural fit: n8n webhook → `marketplace_daily_summary`).
- Live end-to-end validation once the seller pastes keys (docs above explain
  where each value comes from); expected flow: `marketplace_status` →
  `amazon_sales` / `noon_pricing` → a write tool → verify in Seller Central /
  Seller Lab.