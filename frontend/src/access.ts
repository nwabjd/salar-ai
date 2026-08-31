export type AccessState = 'checking' | 'connected' | 'signed-out'

export function isDesktop(): boolean {
  if (typeof window === 'undefined') return false
  if (Boolean((window as any).__TAURI_INTERNALS__)) return true
  if (Boolean((window as any).__TAURI__)) return true
  return navigator.userAgent.includes('Tauri') || window.location.protocol === 'tauri:'
}

export function resolveAccessState(input: { token: string }): AccessState {
  if (input.token) return 'connected'
  return 'signed-out'
}

function invoke(cmd: string, args?: Record<string, unknown>): Promise<unknown> {
  const invoker = (window as any).__TAURI_INTERNALS__?.invoke || (window as any).__TAURI__?.core?.invoke || (window as any).__TAURI__?.invoke
  if (!invoker) return Promise.reject(new Error('Not in Tauri context'))
  return invoker(cmd, args || {})
}

export async function storedSession(): Promise<string> {
  if (isDesktop()) {
    try {
      const token = await invoke('load_token') as string
      if (token) return token
    } catch { /* fall through */ }
  }
  return localStorage.getItem('salar.deviceSession') || localStorage.getItem('salar.token') || ''
}

export async function saveSession(token: string): Promise<void> {
  localStorage.setItem('salar.token', token)
  if (isDesktop()) {
    try { await invoke('save_token', { token }) } catch { /* file fallback ok */ }
  }
}

export async function clearSession(): Promise<void> {
  localStorage.removeItem('salar.deviceSession')
  localStorage.removeItem('salar.token')
  if (isDesktop()) {
    try { await invoke('clear_token') } catch { /* file fallback ok */ }
  }
}

export type LiveMetrics = {
  cpu_percent: number;
  cpu_count: number;
  cpu_brand: string;
  memory_total: number;
  memory_used: number;
  memory_percent: number;
  disk_percent: number;
  uptime_seconds: number;
  os: string;
}

export async function getLiveMetrics(): Promise<LiveMetrics | null> {
  if (!isDesktop()) return null
  try {
    return await invoke('live_metrics') as LiveMetrics
  } catch { return null }
}
