import { SalarApi } from './api'
import { isDesktop } from './access'

const DEVICE_TOKEN_KEY = 'salar.deviceToken'

let stopped = false
let timer: number | null = null
const listeners = new Set<() => void>()

function tauriInvoke(cmd: string, args?: Record<string, unknown>): Promise<unknown> {
  const invoker = (window as any).__TAURI_INTERNALS__?.invoke || (window as any).__TAURI__?.core?.invoke || (window as any).__TAURI__?.invoke
  if (!invoker) return Promise.reject(new Error('Not in Tauri context'))
  return invoker(cmd, args || {})
}

async function ensureDeviceToken(api: SalarApi): Promise<string | null> {
  const existing = localStorage.getItem(DEVICE_TOKEN_KEY)
  if (existing) return existing
  try {
    const platform = (navigator as any).userAgentData?.platform || navigator.platform || 'desktop'
    const device = await api.registerDevice('SALAR Desktop', platform)
    localStorage.setItem(DEVICE_TOKEN_KEY, device.token)
    return device.token
  } catch {
    return null
  }
}

async function executeCommand(kind: string, payload: Record<string, unknown>, api: SalarApi): Promise<{ ok: boolean; detail: string; data: Record<string, unknown> }> {
  const resolved: Record<string, unknown> = { ...payload }
  if (kind === 'open_url' && typeof resolved.url === 'string' && resolved.url.startsWith('/')) {
    resolved.url = api.baseUrl + resolved.url
  }
  try {
    const data = await tauriInvoke('execute_device_command', { kind, payload: resolved })
    return { ok: true, detail: 'executed', data: (data as Record<string, unknown>) || {} }
  } catch (reason) {
    return { ok: false, detail: String(reason), data: {} }
  }
}

export function onDeviceCommand(cb: () => void): () => void {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

function notify() {
  listeners.forEach((cb) => cb())
}

export function startDevicePolling(api: SalarApi): () => void {
  if (!isDesktop()) return () => {}
  stopped = false

  async function poll() {
    if (stopped) return
    let token = await ensureDeviceToken(api)
    if (!token) {
      timer = window.setTimeout(poll, 5000)
      return
    }
    try {
      const command = await api.nextDeviceCommand(token)
      if (command && !stopped) {
        notify()
        const result = await executeCommand(command.kind, command.payload || {}, api)
        try {
          await api.completeDeviceCommand(command.id, token, result)
          notify()
        } catch { /* ignore reporting errors */ }
      }
    } catch (reason) {
      const msg = String(reason)
      if (msg.includes('rejected') || msg.includes('401')) {
        localStorage.removeItem(DEVICE_TOKEN_KEY)
        token = null
      }
    }
    if (!stopped) timer = window.setTimeout(poll, 3000)
  }

  poll()
  return () => {
    stopped = true
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }
}