import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

export const isSupabaseConfigured = Boolean(url && anonKey);

export const supabase: SupabaseClient | null = isSupabaseConfigured
  ? createClient(url!, anonKey!, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;

export async function getSession() {
  if (!supabase) return { data: { session: null } };
  return supabase.auth.getSession();
}

const AUTH_URL_PARAMS = [
  "access_token",
  "refresh_token",
  "provider_token",
  "provider_refresh_token",
  "expires_in",
  "expires_at",
  "token_type",
  "type",
  "code",
  "flow_id",
  "error",
  "error_code",
  "error_description",
];

const AUTH_URL_TRIGGERS = [
  "access_token",
  "refresh_token",
  "provider_token",
  "provider_refresh_token",
  "code",
  "flow_id",
  "error",
  "error_code",
  "error_description",
];

function removeAuthParams(params: URLSearchParams): boolean {
  if (!AUTH_URL_TRIGGERS.some((key) => params.has(key))) return false;
  let changed = false;
  for (const key of AUTH_URL_PARAMS) {
    if (!params.has(key)) continue;
    params.delete(key);
    changed = true;
  }
  return changed;
}

export function cleanAuthFromUrl() {
  if (typeof window === "undefined") return;
  try {
    const url = new URL(window.location.href);
    let changed = removeAuthParams(url.searchParams);
    const hashParams = new URLSearchParams(url.hash.slice(1));
    if (removeAuthParams(hashParams)) {
      url.hash = hashParams.size ? hashParams.toString() : "";
      changed = true;
    }
    if (changed) {
      const cleaned = `${url.origin}${url.pathname}${url.search}${url.hash}`;
      window.history.replaceState(window.history.state, "", cleaned);
    }
  } catch {
    /* ignore */
  }
}
