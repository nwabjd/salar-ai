export type AccessState = 'checking' | 'connected' | 'desktop-disconnected' | 'pairing'

export function isDesktop(): boolean {
  return typeof window !== 'undefined' && Boolean((window as any).__TAURI_INTERNALS__)
}

export function resolveAccessState(input: { desktop: boolean; token: string }): AccessState {
  if (input.token) return 'connected'
  return input.desktop ? 'desktop-disconnected' : 'pairing'
}

export function storedSession(): string {
  return localStorage.getItem('salar.deviceSession') || localStorage.getItem('salar.token') || ''
}

export function saveSession(token: string): void {
  localStorage.setItem('salar.deviceSession', token)
  localStorage.removeItem('salar.token')
}

export function clearSession(): void {
  localStorage.removeItem('salar.deviceSession')
  localStorage.removeItem('salar.token')
}
