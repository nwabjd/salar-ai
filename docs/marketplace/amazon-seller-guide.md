# SALAR ↔ Amazon Seller Central (SP-API) — Setup Guide & Platform Reference

SALAR reads and manages your Amazon seller account through Amazon's official
**Selling Partner API (SP-API)** using a **private (self-authorized)**
application. Everything runs through SALAR's backend — no Amazon code is
bundled into SALAR.

> **Time needed: ~45–90 minutes, one-time.** You only need a **Professional**
> seller account (the ~AED 33/month / SAR 15/month plan) — a personal/Basic
> account cannot use the API.

---

## What SALAR can do for you

| SALAR tool (ask in chat) | What it does |
| --- | --- |
| `amazon_seller_info` | Your seller id + which marketplaces (AE/SA/…) you participate in |
| `amazon_sales` | Daily orders / units / revenue (last 1–90 days) |
| `amazon_recent_orders` | Latest orders: id, status, FBA/FBM, unshipped items, total |
| `amazon_inventory` | FBA stock per SKU + out-of-stock flags |
| `amazon_listing` | One listing: live price, quantity, availability status |
| `amazon_update_price` | Change a listing's selling price (needs your approval) |
| `amazon_update_quantity` | Change an FBM listing's sellable quantity (needs your approval) |
| `marketplace_status` / `marketplace_daily_summary` | Overall connectivity + combined daily briefing |

## What this covers (and what it doesn't)

- Covers: your **orders, sales metrics, FBA inventory, prices, quantities**.
  No buyer personal data is pulled (no restricted-data token needed).
- Doesn't cover (yet): creating brand-new listings end-to-end, A+ content,
  advertising console, returns/reimbursements.

---

## Step 1 — Register an SP-API application (Developer Central)

1. Log in to **Seller Central** → *Partner Network* → *Develop Apps*
   (menu may be at the bottom of *Settings* → *User Permissions* → *Your Info*,
   under *Partner Network*).
2. Agree to the **Selling Partner API developer agreement**.
3. **Register Your Application** → choose **`Selling Partner API`** and role
   **`Seller`** (you are the merchant, not a vendor).
4. Fill in the form (App name: `SALAR Seller`, contact email: yours).
   For the "Privacy Policy URL" and "Terms & Conditions" you can put your own
   site or `https://salaar.cloud`. You only need a **UX placeholder** for the
   Appstore listing — private apps work without publishing
   (*Actions* → *Edit App* → security profile section).

> Keep this tab open — you'll come back for the **IBM role ARN** and the
> **authorization URL**.

## Step 2 — Create the Login with Amazon (LWA) security profile

The SP-API uses *Login with Amazon* credentials to exchange a refresh token.

1. In Seller Central → *Develop Apps* → on your app → **Security Profile**
   (or go to https://developer.amazon.com/lwa/sp/overview.html directly).
2. **Create a new security profile** → name it `SALAR Seller`.
3. Open the profile → copy:
   - **Client ID** (looks like `amzn1.application-oa2-client.…`)
   - **Client secret** (click "Show")

Keep both safe. You'll put them in `backend/.env` later.

## Step 3 — IAM role for request signing

Amazon requires every SP-API call to be cryptographically signed. You create
one **IAM role** in AWS (free) that SALAR assumes.

1. Open the **AWS console** (https://aws.amazon.com/console) → IAM → **Roles**
   → **Create role**.
2. Trust entity: **AWS account → This account**, then **Next**.
3. **Add permissions**: attach the managed policy
   `AmazonAPIGatewayInvokeFullAccess` (this is what Amazon's private-application
   flow documents; keep it minimal).
4. Role name: `SALAR-SPAPI-Role` → **Create role**.
5. Open the role → copy the **ARN**
   (`arn:aws:iam::123456789012:role/SALAR-SPAPI-Role`).

Then create **one IAM user** that is allowed to assume that role:

1. IAM → **Users** → **Create user** → name `salar-spapi-user` → no console
   access. (Do NOT attach any policy to the user — the role policy does the work.)
2. On the user → **Permissions** → **Add permission** → **Create inline policy** →

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::123456789012:role/SALAR-SPAPI-Role"
    }
  ]
}
```

3. **Security credentials** tab → **Create access key** → choose
   "Application running outside AWS" → copy the **Access key ID** and
   **Secret access key**.

## Step 4 — Self-authorize (get the refresh token)

1. Back in Developer Central (SP-API app) → open **Edit App** → copy the
   **Authorize** (or *REST API* → *Authorize your application*) URL. It looks
   like:
   ```
   https://sellercentral.amazon.eu/apps/authorize/consent?application_id=amzn1.sp.solution.…
   ```
2. Open that URL while logged in as the **primary account holder**.
3. Amazon shows a consent screen → **Allow** button (if missing, you're not the
   primary user or the app isn't self-authorized).
4. You land on a page with your **Refresh token** (a long `Atzr|…` string).
   **Copy it** — this never expires unless you revoke it.

## Step 5 — Tell SALAR

Add these lines to `backend/.env` (the repo root `.env`):

```env
SALAR_AMAZON_SPAPI_ENABLED=true
SALAR_AMAZON_SPAPI_REGION=EU
SALAR_AMAZON_LWA_CLIENT_ID=amzn1.application-oa2-client.…
SALAR_AMAZON_LWA_CLIENT_SECRET=…
SALAR_AMAZON_LWA_REFRESH_TOKEN=Atzr|…
SALAR_AMAZON_IAM_ACCESS_KEY=AKIA…
SALAR_AMAZON_IAM_SECRET_KEY=…
SALAR_AMAZON_SPAPI_ROLE_ARN=arn:aws:iam::123456789012:role/SALAR-SPAPI-Role
# Optional: which marketplaces, comma separated (AE + SA by default)
SALAR_AMAZON_MARKETPLACE_IDS=A2VIGQ35RCS4UG,A17E79C6D8DWNP
```

**(Optional)** connect per-user over the API instead:
`POST /api/marketplace/amazon/connect` with the same fields (validated live
before it's stored).

Then restart the backend and ask SALAR: *"are my Amazon and noon accounts
connected?"* → `marketplace_status`. Then try *"what did I sell yesterday on
Amazon?"* → `amazon_sales`.

---

## Platform reference (the details SALAR knows)

### Marketplaces & regions

| Marketplace | Marketplace ID | Region / endpoint | Currency |
| --- | --- | --- | --- |
| Amazon.ae (UAE) | `A2VIGQ35RCS4UG` | EU — `sellingpartnerapi-eu.amazon.com` (aws `eu-west-1`) | AED (د.إ) |
| Amazon.sa (KSA) | `A17E79C6D8DWNP` | EU — `sellingpartnerapi-eu.amazon.com` | SAR (ر.س) |
| Amazon.eg (Egypt, **arriving later**) | `ARBP9OOSHTCHU` | EU — `sellingpartnerapi-eu.amazon.com` | EGP |

Amazon Egypt isn't live for 3P sellers yet — SALAR is ready for it via
`SALAR_AMAZON_MARKETPLACE_IDS`.

### How auth works (SALAR does this for you)

1. **LWA**: refresh token → short-lived access token (valid ~1 h).
2. **STS**: assume the IAM role → temporary signing credentials.
3. **SigV4**: every request to the SP-API is signed (service `execute-api`).

### What each backend call maps to

- Sales: `GET /sales/v1/orderMetrics` (per-day orders/units/revenue)
- Orders: `GET /orders/v0/orders` (no buyer PII → no restricted data token)
- FBA stock: `GET /fba/inventory/v1/summaries`
- Listing read: `GET /listings/2021-08-01/items/{sellerId}/{sku}`
- Price/quantity update: `PUT /listings/2021-08-01/items/{sellerId}/{sku}`
  (patches `standard_price` / `fulfillment_availability`)

### Fees in brief (always changing — check Seller Central)

- Selling plan: **Professional** ≈ AED 33/month or SAR 15/month (required for API).
- **Referral fee**: category-dependent (~5–15% of the sale price).
- **FBA fulfillment** fees: per unit, weight/size-tier based.
- Prices on `amazon_update_price` are **gross of all fees** — Amazon takes its
  share automatically.

### Troubleshooting

| Symptom | Fix |
| --- | --- |
| `amazon LWA rejected the refresh token` | Re-run Step 4 (new refresh token), or your LWA secret was clipped. |
| `STS AssumeRole failed` | Role ARN typo, or the IAM user's inline policy resource doesn't match. |
| `SP-API returned HTTP 403` | You're not the primary account holder, or the app never got self-authorized (Step 4). |
| `could not determine the sellerId` | Check the role policy is attached (`AmazonAPIGatewayInvokeFullAccess`). |
| No data for AE/SA | Confirm `SALAR_AMAZON_MARKETPLACE_IDS` includes both ids and you have orders in the window. |