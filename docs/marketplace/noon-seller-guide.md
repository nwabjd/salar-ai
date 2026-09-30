# SALAR ↔ noon Seller (Partner API) — Setup Guide & Platform Reference

SALAR reads and manages your **noon** seller account (UAE, KSA, Egypt) through
noon's official **Partner API** (`noon-api-gateway.noon.partners`) using your
noon **service-account key**. Nothing from noon's SDK is bundled into SALAR —
it talks to noon's public API only.

> **Time needed:** the API key is granted by noon's team, so the wait is
> usually the slowest part (days). You must be an **approved noon seller**.

---

## What SALAR can do for you

| SALAR tool (ask in chat) | What it does |
| --- | --- |
| `noon_pricing` | Current price + MSRP + active flag per SKU and country (ae/sa/eg) |
| `noon_stock` | Available quantity per (warehouse, SKU) pair |
| `noon_update_price` | Set price (and optional MSRP / active flag) for a SKU in a country |
| `noon_update_stock` | **Set** the available quantity for a SKU in a warehouse |
| `marketplace_status` / `marketplace_daily_summary` | Connectivity + daily briefing across platforms |

> ⚠️ `noon_update_stock` sends an **absolute** quantity: whatever SALAR sends
> **becomes** noon's available quantity — it is not added to the current value.

## What this covers (and what it doesn't)

- Covers: **stock, pricing, offer status** per country.
- Doesn't cover (yet): creating products (Content API), orders/shipments
  (FBPI), catalog sync, or reports exports. SALAR's architecture lets us add
  them next — the auth + Stock/Pricing/Offer plumbing is already in place.

---

## Step 1 — Be an approved noon seller

You need active accounts on the noon marketplaces you sell in. Sabbatical /
dormant stores must be reactivated before API access can be granted.

## Step 2 — Partner onboarding & API access

noon controls API access through **partner onboarding**:

1. Go to **Seller Lab** (sell.noon.com) → your seller dashboard.
2. Request/confirm **API access** — on fresh accounts this lives under
   *Settings → API / Integration*, or you ask your **noon account manager /
   onboarding team** for the *Partner API onboarding* form.
3. noon's team validates your store and grants partner access (this is the
   step that can take days). You'll receive:
   - a **partner/project code**, and
   - access to noon's **Developer Portal**.

## Step 3 — Get your service-account key from the Developer Portal

1. Open the noon **Developer Portal**: https://developer.noon.partners
   (log in with the approved account).
2. Follow the onboarding there → **create your project**.
3. Generate the **service-account key file**. It's a JSON document like:

```json
{
  "key_id": "…",
  "private_key": "-----BEGIN PRIVATE KEY-----\n…\n-----END PRIVATE KEY-----\n",
  "project_code": "…"
}
```

4. Keep the file safe — it's the password to your noon data. (If you see a
   different name like `client_id` instead of `key_id`, tell SALAR and it can
   map the field.)

## Step 4 — Find your warehouse code

Stock operations are per **warehouse**. Ask SALAR for a stock read on a known
SKU and it will tell you if a warehouse code is missing; you can also find the
list via noon's *Warehouse Platform* API, or simply use the warehouse code
noon shows in Seller Lab (`WH-…`).

## Step 5 — Tell SALAR

Add these lines to `backend/.env` (repo root). **Either** point at the JSON
file (easiest) **or** paste the three fields:

```env
SALAR_NOON_ENABLED=true
# Option A: the service-account JSON file
SALAR_NOON_KEY_FILE=C:/Users/You/noon_credentials.json
# Option B: fields directly (skip if using the file)
#SALAR_NOON_KEY_ID=
#SALAR_NOON_PRIVATE_KEY=
#SALAR_NOON_PROJECT_CODE=
# Countries you sell in (default: ae,sa,eg)
SALAR_NOON_COUNTRY_CODES=ae,sa,eg
# Warehouse for stock ops when not given per-call
SALAR_NOON_WAREHOUSE_CODE=WH-…
```

**(Optional)** per-user connect over the API instead:
`POST /api/marketplace/noon/connect` with `{key_id, private_key, project_code,
base_url?, country_codes?, warehouse_code?}` — validated live with a `whoami`
call before it's stored.

Restart the backend and ask: *"are my Amazon and noon accounts connected?"* →
`marketplace_status`. Then try *"what's the price of SKU X on noon UAE?"* →
`noon_pricing`.

---

## Platform reference (the details SALAR knows)

### Countries & domains

| Country | Code | API domain (SALAR uses) | Currency |
| --- | --- | --- | --- |
| UAE | `ae` | pricing / stock / offer / content / fbpi | AED |
| KSA | `sa` | pricing / stock / offer / content / fbpi | SAR |
| Egypt | `eg` | pricing / stock / offer / content / fbpi | EGP |

One service account + project covers all of them; every SKU/country pair has
its own price and active flag (a product can be live in the UAE but not in
KSA).

### Auth (SALAR does this for you)

1. SALAR signs a short-lived **RS256 JWT** with your private key (`sub` =
   `key_id`).
2. `POST /identity/public/v1/api/login` with the JWT + project code →
   session cookie.
3. Every later API call carries that cookie + a SALAR User-Agent.

### Endpoints SALAR calls

| Purpose | Endpoint |
| --- | --- |
| Login | `POST /identity/public/v1/api/login` |
| Identity check | `GET /identity/v1/whoami` |
| Read pricing | `POST /pricing/v1/pricing/get` |
| Write pricing | `POST /pricing/v1/pricing/upsert` |
| Read stock | `POST /stock/v1/stock-list` |
| Write stock | `POST /stock/v1/stock-update` |

### Fulfillment model quick notes

- **FBPI** (Fulfilled By Partner Integration): you fulfil orders from your own
  warehouse — the responsibilities map to the `stock` numbers SALAR manages.
- **FBPO** (Fulfilled By Purchase Order): noon buys/buy stock — different
  flows (POs), not covered by the stock update tool.
- noon's **Pricing** updates are usually reflected on the live stores within
  minutes; heavy repricing can occasionally be throttled.

### Troubleshooting

| Symptom | Fix |
| --- | --- |
| `noon rejected the service-account key` | key_id / private_key mismatch. If you use `SALAR_NOON_KEY_FILE`, double-check the JSON field names. |
| `noon returned HTTP 403` on pricing/stock | project_code doesn't match the store, or API access not yet granted to that country. |
| Stock read says a warehouse code is missing | pass `warehouse_code` per call or set `SALAR_NOON_WAREHOUSE_CODE`. |
| Pricing write returns `NOT_FOUND` for a SKU | the SKU has no offer in that country yet — create it via Seller Lab (Content/Offer) first. |