export type PreviewMode = "fixture" | "live";

export interface PreviewConfig {
  apiUrl: string;
  mode: PreviewMode;
}

const API_URL_KEY = "salar-preview.apiUrl";
const MODE_KEY = "salar-preview.mode";
const SESSION_KEY = "salar-preview.session";
const DEFAULT_API_URL = "http://127.0.0.1:8000";

export function normalizePreviewApiUrl(value: string): string {
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error("Enter a valid HTTP or HTTPS backend URL.");
  }
  if (
    (url.protocol !== "http:" && url.protocol !== "https:") ||
    !url.hostname
  ) {
    throw new Error("Enter a valid HTTP or HTTPS backend URL.");
  }
  url.hash = "";
  url.search = "";
  return url.toString().replace(/\/+$/, "");
}

export function loadPreviewConfig(): PreviewConfig {
  const mode = sessionStorage.getItem(MODE_KEY);
  const storedApiUrl = sessionStorage.getItem(API_URL_KEY);
  let apiUrl = DEFAULT_API_URL;
  if (storedApiUrl) {
    try {
      apiUrl = normalizePreviewApiUrl(storedApiUrl);
    } catch {
      apiUrl = DEFAULT_API_URL;
    }
  }
  return {
    apiUrl,
    mode: mode === "live" ? "live" : "fixture",
  };
}

export function savePreviewConfig(config: PreviewConfig): void {
  sessionStorage.setItem(API_URL_KEY, normalizePreviewApiUrl(config.apiUrl));
  sessionStorage.setItem(MODE_KEY, config.mode);
}

export function clearPreviewSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}
