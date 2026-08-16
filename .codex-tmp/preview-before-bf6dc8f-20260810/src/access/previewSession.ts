const MODE_KEY = 'salar-preview.mode';
const API_URL_KEY = 'salar-preview.apiUrl';

export type PreviewDataMode = 'fixture' | 'live';

export interface PreviewConfig {
  mode: PreviewDataMode;
  apiUrl: string;
}

export function loadPreviewConfig(): PreviewConfig {
  const envMode = import.meta.env.VITE_PREVIEW_DATA_MODE as string | undefined;
  const envApiUrl = import.meta.env.VITE_PREVIEW_API_URL as string | undefined;

  const sessionMode = sessionStorage.getItem(MODE_KEY) as PreviewDataMode | null;
  const sessionApiUrl = sessionStorage.getItem(API_URL_KEY);

  const mode =
    sessionMode === 'fixture' || sessionMode === 'live'
      ? sessionMode
      : envMode === 'live'
        ? 'live'
        : 'fixture';

  const apiUrl = sessionApiUrl || envApiUrl || '';

  return { mode, apiUrl };
}

export function setPreviewMode(mode: PreviewDataMode): void {
  sessionStorage.setItem(MODE_KEY, mode);
}

export function setPreviewApiUrl(url: string): void {
  sessionStorage.setItem(API_URL_KEY, url);
}

export function clearPreviewSession(): void {
  sessionStorage.removeItem(MODE_KEY);
  sessionStorage.removeItem(API_URL_KEY);
}
