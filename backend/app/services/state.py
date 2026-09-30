"""Shared in-memory stores for services that don't use the database."""

email_accounts: dict[str, dict] = {}

# Per-user n8n instance registrations: {user_id: {"base_url", "api_key"}}.
# Falls back to global SALAR_N8N_BASE_URL / SALAR_N8N_API_KEY when absent.
n8n_connections: dict[str, dict] = {}

# Per-user seller-platform registrations: {user_id: {"amazon": {...} | "noon": {...}}}.
# Falls back to global SALAR_AMAZON_* / SALAR_NOON_* env settings when absent.
marketplace_connections: dict[str, dict] = {}
