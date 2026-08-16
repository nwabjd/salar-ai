export type Message = { id: string; role: 'user' | 'assistant'; content: string; created_at: string }
export type Conversation = { id: string; title: string; messages?: Message[] }
export type Memory = { id: string; title: string; content: string; layer: string; created_at: string }
export type DocumentItem = { id: string; filename: string; media_type: string; created_at: string }
export type Device = { id: string; name: string; platform: string; last_seen_at: string | null }
export type WhatsAppChat = { jid: string; name: string; lastMessage: string | null }
export type WhatsAppMessage = { id: string; fromMe: boolean; text: string; senderName: string; pushName: string; timestamp: number }
export type EmailAccount = { address: string; password: string; imap_host?: string; smtp_host?: string }
export type EmailMessage = { id: string; from: string; to: string; subject: string; date: string }
export type EmailFolder = { folder: string; total: number; unread: number }
export type WorldSituation = {
  kind: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  title: string
  summary?: string
  entity_ids?: string[]
  props?: Record<string, unknown>
}

export type WorldAction = {
  id: string
  situation_kind: string
  title: string
  description: string
  tool_calls: Array<{ name: string; args: Record<string, unknown> }>
  risk: string
  severity: string
  score: number
}

export type WorldSimulation = {
  situations_before: WorldSituation[]
  situations_after: WorldSituation[]
  consequences: Array<{ kind: string; delta: string; detail: string; severity: string }>
  narrative: string
}

export type WorldPolicy = {
  situation_kind: string
  action_title: string
  attempts: number
  successes: number
  resolved_count: number
  score: number
}

export type MissionStep = {
  id: string
  sequence: number
  tool: string
  args_json: string
  danger_level: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'waiting_approval' | 'approved' | 'denied'
  error?: string | null
  approval_note?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_at?: string | null
}

export type MissionEvent = {
  id: string
  sequence: number
  kind: string
  detail_json: string
  created_at: string
}

export type Mission = {
  id: string
  goal: string
  mode: string
  status: 'queued' | 'planning' | 'running' | 'waiting_approval' | 'completed' | 'failed' | 'cancelled' | 'interrupted'
  step_count: number
  completed_count: number
  total_attempts: number
  replan_count: number
  result_summary?: string | null
  error?: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  updated_at?: string | null
  steps?: MissionStep[]
  events?: MissionEvent[]
}

localStorage.removeItem('salar.apiUrl')
export const DEFAULT_API = (import.meta.env.VITE_API_URL || 'https://salar-backend.onrender.com').replace(/\/$/, '')

const DEFAULT_TIMEOUT = 30000
const STREAM_TIMEOUT = 120000

function timeoutSignal(ms: number): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  return { signal: controller.signal, cleanup: () => clearTimeout(timer) }
}

export interface Notification {
  id: string
  kind: string
  title: string
  body?: string
  link?: string
  severity?: string
  is_read: boolean
  created_at?: string
}

export class SalarApi {
  constructor(public baseUrl = DEFAULT_API, public token = localStorage.getItem('salar.deviceSession') || localStorage.getItem('salar.token') || '') {}

  private async request<T>(path: string, init: RequestInit = {}, timeout = DEFAULT_TIMEOUT): Promise<T> {
    const headers = new Headers(init.headers)
    if (this.token) headers.set('Authorization', `Bearer ${this.token}`)
    if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const { signal, cleanup } = timeoutSignal(timeout)
    try {
      const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers, signal })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        if (response.status === 401) throw new Error('Authentication expired — please log in again')
        throw new Error(body?.detail || `Request failed (${response.status})`)
      }
      return response.json()
    } finally {
      cleanup()
    }
  }

  async supabaseLogin(token: string) {
    const data = await this.request<{access_token:string;token_type:string}>('/api/auth/supabase', { method: 'POST', body: JSON.stringify({ token }) })
    this.token = data.access_token
    return data
  }
  validateSession() { return this.request<{id:string;email:string;is_admin:boolean}>('/api/auth/session') }
  async usage() {
    return this.request<{ plan: string; limit: number | null; used: number; reset_at: string; exempt: boolean }>('/api/billing/usage')
  }
  conversations() { return this.request<Conversation[]>('/api/conversations') }
  conversation(id: string) { return this.request<Conversation>(`/api/conversations/${id}`) }
  createConversation(title='New conversation') { return this.request<Conversation>('/api/conversations', {method:'POST', body:JSON.stringify({title})}) }
  chat(conversation_id:string, content:string) { return this.request<{user_message:Message;assistant_message:Message}>('/api/chat', {method:'POST',body:JSON.stringify({conversation_id,content})}) }

  chatStream(
    conversation_id: string,
    content: string,
    onToken: (token: string) => void,
    onDone: (messageId: string, createdAt: string) => void,
    onError?: (error: Error) => void,
    onTool?: (toolName: string, args: Record<string, unknown>) => void,
    onToolResult?: (toolName: string, result: Record<string, unknown>) => void,
    fast = false,
  ) {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), STREAM_TIMEOUT)

    fetch(`${this.baseUrl}/api/chat/stream`, { method: 'POST', headers, body: JSON.stringify({ conversation_id, content, fast }), signal: controller.signal })
      .then(async response => {
        clearTimeout(timer)
        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: 'Stream failed' }))
          throw new Error(err.detail || `Stream failed (${response.status})`)
        }
        const reader = response.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let gotDone = false
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'token') onToken(data.content)
              if (data.type === 'tool_call') onTool?.(data.tool, data.args)
              if (data.type === 'tool_result') onToolResult?.(data.tool, data.result)
              if (data.type === 'done') { gotDone = true; onDone(data.message_id, data.created_at) }
              if (data.type === 'error') throw new Error(data.detail)
            } catch (e) {
              if (e instanceof SyntaxError) continue
              throw e
            }
          }
        }
        if (!gotDone) throw new Error('Stream ended unexpectedly')
      })
      .catch((err) => {
        clearTimeout(timer)
        console.error('Stream error:', err)
        onError?.(err instanceof Error ? err : new Error(String(err)))
      })
  }

  notifications(limit = 50): Promise<Notification[]> { return this.request(`/api/notifications?limit=${limit}`) }
  notificationUnreadCount(): Promise<{ unread_count: number }> { return this.request('/api/notifications/unread-count') }
  markNotificationRead(id: string): Promise<Notification> { return this.request(`/api/notifications/${id}/read`, { method: 'POST' }) }
  markAllNotificationsRead(): Promise<{ ok: boolean }> { return this.request('/api/notifications/read-all', { method: 'POST' }) }

  coreRun(request: string, goal = ''): Promise<any> { return this.request('/api/core/run', { method: 'POST', body: JSON.stringify({ request, goal }) }) }
  coreApprove(taskId: string, approve: boolean): Promise<any> { return this.request(`/api/core/run/${taskId}/approve`, { method: 'POST', body: JSON.stringify({ approve }) }) }
  coreStatus(): Promise<{ live_agents: any[]; alerts: any[]; bus_events_count: number }> { return this.request('/api/core/status') }
  coreTraces(): Promise<any[]> { return this.request('/api/core/traces') }
  coreTrace(traceId: string): Promise<any> { return this.request(`/api/core/traces/${traceId}`) }

  memories() { return this.request<Memory[]>('/api/memories') }
  saveMemory(title:string, content:string) { return this.request<Memory>('/api/memories',{method:'POST',body:JSON.stringify({title,content,layer:'long_term'})}) }
  documents() { return this.request<DocumentItem[]>('/api/documents') }
  async upload(file:File) { const body=new FormData(); body.append('file',file); return this.request<DocumentItem>('/api/documents',{method:'POST',body}) }
  devices() { return this.request<Device[]>('/api/devices') }
  registerDevice(name:string, platform='windows') { return this.request<Device & {token:string}>('/api/devices',{method:'POST',body:JSON.stringify({name,platform})}) }
  command(device_id:string, kind:string, payload:Record<string,unknown>) { return this.request('/api/commands',{method:'POST',body:JSON.stringify({device_id,kind,payload})}) }

  async nextDeviceCommand(deviceToken: string) {
    const { signal, cleanup } = timeoutSignal(60000)
    try {
      const response = await fetch(`${this.baseUrl}/api/device/commands/next`, { headers: { 'X-Device-Token': deviceToken }, signal })
      if (!response.ok) throw new Error('Device link rejected')
      return response.json() as Promise<null | { id: string; kind: string; payload: Record<string, unknown> }>
    } finally {
      cleanup()
    }
  }

  async completeDeviceCommand(id: string, deviceToken: string, result: { ok: boolean; detail: string; data?: Record<string, unknown> }) {
    const { signal, cleanup } = timeoutSignal(10000)
    try {
      const response = await fetch(`${this.baseUrl}/api/device/commands/${id}/result`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Device-Token': deviceToken },
        body: JSON.stringify({ ...result, data: result.data || {} }),
        signal,
      })
      if (!response.ok) throw new Error(`Command result failed (${response.status})`)
      return response
    } finally {
      cleanup()
    }
  }

  tts(text: string, fast = false): Promise<Blob> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`
    const { signal, cleanup } = timeoutSignal(60000)
    const fastParam = fast ? '?fast=true' : ''
    return fetch(`${this.baseUrl}/api/tts${fastParam}`, { method: 'POST', headers, body: JSON.stringify({ conversation_id: 'tts', content: text }), signal })
      .then(r => { if (!r.ok) throw new Error('TTS failed'); return r.blob() })
      .finally(cleanup)
  }

  stt(audioBlob: Blob, fast = false): Promise<string> {
    const headers: Record<string, string> = {}
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`
    const form = new FormData()
    form.append('file', audioBlob, 'audio.webm')
    const { signal, cleanup } = timeoutSignal(30000)
    const fastParam = fast ? '?fast=true' : ''
    return fetch(`${this.baseUrl}/api/stt${fastParam}`, { method: 'POST', headers, body: form, signal })
      .then(async r => { const d = await r.json(); if (!r.ok) throw new Error(d.detail || 'STT failed'); return d.text || '' })
      .finally(cleanup)
  }

  whatsappStatus(): Promise<{ status: string; phone_number: string | null; name: string | null; has_qr: boolean }> {
    return this.request('/api/whatsapp/status')
  }

  whatsappQR(): Promise<{ qr: string | null; image: string | null; status: string }> {
    return this.request('/api/whatsapp/qr')
  }

  whatsappChats(): Promise<WhatsAppChat[]> {
    return this.request('/api/whatsapp/chats')
  }

  whatsappMessages(jid: string): Promise<WhatsAppMessage[]> {
    return this.request(`/api/whatsapp/messages/${encodeURIComponent(jid)}`)
  }

  whatsappSend(to: string, text: string): Promise<{ status: string }> {
    return this.request('/api/whatsapp/send', { method: 'POST', body: JSON.stringify({ to, text }) })
  }

  whatsappAutoReplyGet(): Promise<{ enabled: boolean }> {
    return this.request('/api/whatsapp/auto-reply')
  }

  whatsappAutoReplySet(enabled: boolean): Promise<{ enabled: boolean }> {
    return this.request('/api/whatsapp/auto-reply', { method: 'PUT', body: JSON.stringify({ enabled }) })
  }

  whatsappPassMessages(): Promise<{ messages: Array<{ id: number; detail: any; time: string }> }> {
    return this.request('/api/whatsapp/pass-messages')
  }

  whatsappPassMessageAck(eventId: string): Promise<{ ok: boolean }> {
    return this.request(`/api/whatsapp/pass-messages/${eventId}/acknowledge`, { method: 'POST' })
  }

  whatsappLogout(): Promise<{ ok: boolean }> {
    return this.request('/api/whatsapp/logout', { method: 'POST' })
  }

  emailConnect(config: EmailAccount): Promise<{ status: string; folders: EmailFolder[] }> {
    return this.request('/api/email/connect', { method: 'POST', body: JSON.stringify(config) })
  }

  emailStatus(): Promise<{ connected: boolean; address?: string }> {
    return this.request('/api/email/status')
  }

  emailFolders(): Promise<{ folders: EmailFolder[] }> {
    return this.request('/api/email/folders')
  }

  emailSearch(folder = 'INBOX', query = 'ALL', limit = 20): Promise<{ emails: EmailMessage[] }> {
    return this.request('/api/email/search', { method: 'POST', body: JSON.stringify({ folder, query, limit }) })
  }

  emailRead(msgId: string, folder = 'INBOX'): Promise<{ id: string; from: string; to: string; subject: string; body: string; date: string }> {
    return this.request('/api/email/read', { method: 'POST', body: JSON.stringify({ msg_id: msgId, folder }) })
  }

  emailSend(to: string, subject: string, body: string, cc?: string): Promise<{ status: string }> {
    return this.request('/api/email/send', { method: 'POST', body: JSON.stringify({ to, subject, body, cc }) })
  }

  monitorSnapshot(): Promise<any> {
    return this.request('/api/monitor/snapshot')
  }

  worldSituations(limit = 12): Promise<WorldSituation[]> {
    return this.request(`/api/world/situations?limit=${limit}`)
  }

  worldActions(): Promise<WorldAction[]> {
    return this.request('/api/world/actions')
  }

  worldExecuteAction(action: { situation_kind: string; action_title: string; tool_calls: Array<{ name: string; args: Record<string, unknown> }>; risk: string; confirmed?: boolean }): Promise<{ ok: boolean; results: Array<{ tool: string; result: Record<string, unknown> }>; outcome: string }> {
    return this.request('/api/world/actions/execute', { method: 'POST', body: JSON.stringify({ ...action, confirmed: action.confirmed ?? false }) })
  }

  worldEvolve(): Promise<{ ok: boolean; policies: WorldPolicy[] }> {
    return this.request('/api/world/evolve', { method: 'POST' })
  }

  worldPolicies(): Promise<WorldPolicy[]> {
    return this.request('/api/world/policies')
  }

  worldSimulate(changes: Array<{ action: string; params: Record<string, unknown> }>): Promise<WorldSimulation> {
    return this.request('/api/world/simulate', { method: 'POST', body: JSON.stringify({ changes }) })
  }

  worldObserve(source: string, event_type: string, payload: Record<string, unknown>): Promise<any> {
    return this.request('/api/world/observe', { method: 'POST', body: JSON.stringify({ source, event_type, payload }) })
  }

  missions(): Promise<Mission[]> {
    return this.request('/api/missions')
  }

  mission(id: string): Promise<Mission> {
    return this.request(`/api/missions/${id}`)
  }

  missionEvents(id: string): Promise<MissionEvent[]> {
    return this.request(`/api/missions/${id}/events`)
  }

  launchMission(goal: string, mode = 'autonomous'): Promise<Mission> {
    return this.request('/api/missions', { method: 'POST', body: JSON.stringify({ goal, mode }) })
  }

  cancelMission(id: string): Promise<any> {
    return this.request(`/api/missions/${id}/cancel`, { method: 'POST' })
  }

  approveMissionStep(missionId: string, stepId: string): Promise<any> {
    return this.request(`/api/missions/${missionId}/steps/${stepId}/approve`, { method: 'POST' })
  }

  denyMissionStep(missionId: string, stepId: string): Promise<any> {
    return this.request(`/api/missions/${missionId}/steps/${stepId}/deny`, { method: 'POST' })
  }

  monitorStream(onData: (data: any) => void, onError?: (err: Error) => void): () => void {
    const headers: Record<string, string> = {}
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`
    const controller = new AbortController()

    fetch(`${this.baseUrl}/api/monitor/stream`, { headers, signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(`Monitor stream failed (${response.status})`)
        const reader = response.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try { onData(JSON.parse(line.slice(6))) } catch {}
          }
        }
      })
      .catch(err => { if (onError && !controller.signal.aborted) onError(err) })

    return () => controller.abort()
  }

  monitorProcesses(): Promise<{ processes: { pid: number; name: string; cpu_percent: number; memory_percent: number; status: string }[]; total: number }> {
    return this.request('/api/monitor/processes')
  }

  calendarFeeds(): Promise<{ feeds: { name: string; url: string; color: string }[] }> {
    return this.request('/api/calendar/feeds')
  }

  calendarAddFeed(name: string, url: string, color?: string): Promise<any> {
    return this.request('/api/calendar/feeds', { method: 'POST', body: JSON.stringify({ name, url, color: color || '#5227FF' }) })
  }

  calendarRemoveFeed(name: string): Promise<any> {
    return this.request(`/api/calendar/feeds/${encodeURIComponent(name)}`, { method: 'DELETE' })
  }

  calendarEvents(daysBefore = 7, daysAfter = 30): Promise<{ events: any[] }> {
    return this.request(`/api/calendar/events?days_before=${daysBefore}&days_after=${daysAfter}`)
  }

  calendarToday(): Promise<{ events: any[] }> {
    return this.request('/api/calendar/today')
  }

  calendarUpcoming(limit = 10): Promise<{ events: any[] }> {
    return this.request(`/api/calendar/upcoming?limit=${limit}`)
  }

  alertRules(): Promise<{ rules: any[] }> {
    return this.request('/api/alerts/rules')
  }

  alertCreate(name: string, type: string, config: any = {}, severity = 'warning'): Promise<any> {
    return this.request('/api/alerts/rules', { method: 'POST', body: JSON.stringify({ name, type, config, severity }) })
  }

  alertDelete(ruleId: string): Promise<any> {
    return this.request(`/api/alerts/rules/${ruleId}`, { method: 'DELETE' })
  }

  alertToggle(ruleId: string, enabled: boolean): Promise<any> {
    return this.request(`/api/alerts/rules/${ruleId}/toggle`, { method: 'PUT', body: JSON.stringify({ enabled }) })
  }

  alertTriggered(limit = 50, unackedOnly = false): Promise<{ alerts: any[] }> {
    return this.request(`/api/alerts/triggered?limit=${limit}&unacked_only=${unackedOnly}`)
  }

  alertAcknowledge(alertId: string): Promise<any> {
    return this.request(`/api/alerts/triggered/${alertId}/acknowledge`, { method: 'POST' })
  }

  fileList(path = '', sort = 'name', desc = false): Promise<{ items: any[]; path: string; count: number }> {
    return this.request(`/api/files/list?path=${encodeURIComponent(path)}&sort=${sort}&desc=${desc}`)
  }

  fileTree(path = '', depth = 2): Promise<any> {
    return this.request(`/api/files/tree?path=${encodeURIComponent(path)}&depth=${depth}`)
  }

  fileInfo(path: string): Promise<any> {
    return this.request(`/api/files/info?path=${encodeURIComponent(path)}`)
  }

  fileRead(path: string): Promise<{ content: string }> {
    return this.request(`/api/files/read?path=${encodeURIComponent(path)}`)
  }

  fileWrite(path: string, content: string): Promise<any> {
    return this.request('/api/files/write', { method: 'POST', body: JSON.stringify({ path, content }) })
  }

  fileSearch(query: string, path = ''): Promise<{ results: any[] }> {
    return this.request(`/api/files/search?q=${encodeURIComponent(query)}&path=${encodeURIComponent(path)}`)
  }

  fileRename(path: string, newName: string): Promise<any> {
    return this.request('/api/files/rename', { method: 'POST', body: JSON.stringify({ path, new_name: newName }) })
  }

  fileMove(src: string, dest: string): Promise<any> {
    return this.request('/api/files/move', { method: 'POST', body: JSON.stringify({ src, dest }) })
  }

  fileDelete(path: string): Promise<any> {
    return this.request(`/api/files/delete?path=${encodeURIComponent(path)}`, { method: 'DELETE' })
  }

  fileMkdir(path: string): Promise<any> {
    return this.request(`/api/files/mkdir?path=${encodeURIComponent(path)}`, { method: 'POST' })
  }

  fileUpload(path: string, file: File): Promise<any> {
    const form = new FormData()
    form.append('file', file)
    return this.request(`/api/files/upload?path=${encodeURIComponent(path)}`, { method: 'POST', body: form } as any)
  }

  fileDownload(path: string): string {
    const headers: Record<string, string> = {}
    if (this.token) headers['Authorization'] = `Bearer ${this.token}`
    return `${this.baseUrl}/api/files/download?path=${encodeURIComponent(path)}`
  }

  codeExecute(code: string, language = 'python', timeout = 30): Promise<{ stdout: string; stderr: string; status: string; exit_code: number }> {
    return this.request('/api/code/execute', { method: 'POST', body: JSON.stringify({ code, language, timeout }) })
  }

  workspaces(): Promise<any[]> { return this.request('/api/workspaces') }
  createWorkspace(data: { name: string; icon?: string; color?: string }): Promise<any> { return this.request('/api/workspaces', { method: 'POST', body: JSON.stringify(data) }) }
  updateWorkspace(id: string, data: any): Promise<any> { return this.request(`/api/workspaces/${id}`, { method: 'PUT', body: JSON.stringify(data) }) }
  deleteWorkspace(id: string): Promise<any> { return this.request(`/api/workspaces/${id}`, { method: 'DELETE' }) }
  setDefaultWorkspace(id: string): Promise<any> { return this.request(`/api/workspaces/${id}/default`, { method: 'POST' }) }

  tasks(params?: { status?: string; priority?: string; workspace_id?: string }): Promise<any[]> {
    const q = new URLSearchParams()
    if (params?.status) q.set('status', params.status)
    if (params?.priority) q.set('priority', params.priority)
    if (params?.workspace_id) q.set('workspace_id', params.workspace_id)
    return this.request(`/api/tasks?${q}`)
  }
  createTask(data: any): Promise<any> { return this.request('/api/tasks', { method: 'POST', body: JSON.stringify(data) }) }
  updateTask(id: string, data: any): Promise<any> { return this.request(`/api/tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }) }
  deleteTask(id: string): Promise<any> { return this.request(`/api/tasks/${id}`, { method: 'DELETE' }) }
  setTaskStatus(id: string, status: string): Promise<any> { return this.request(`/api/tasks/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }) }
  taskStats(): Promise<any> { return this.request('/api/tasks/stats') }

  reminders(params?: { upcoming_only?: boolean; limit?: number }): Promise<any[]> {
    const q = new URLSearchParams()
    if (params?.upcoming_only) q.set('upcoming_only', 'true')
    if (params?.limit) q.set('limit', String(params.limit))
    return this.request(`/api/reminders?${q}`)
  }
  createReminder(data: any): Promise<any> { return this.request('/api/reminders', { method: 'POST', body: JSON.stringify(data) }) }
  updateReminder(id: string, data: any): Promise<any> { return this.request(`/api/reminders/${id}`, { method: 'PUT', body: JSON.stringify(data) }) }
  deleteReminder(id: string): Promise<any> { return this.request(`/api/reminders/${id}`, { method: 'DELETE' }) }
  markReminderDone(id: string): Promise<any> { return this.request(`/api/reminders/${id}/done`, { method: 'PATCH' }) }
  overdueReminders(): Promise<any[]> { return this.request('/api/reminders/overdue') }

  knowledgeDocs(): Promise<any[]> { return this.request('/api/knowledge') }
  uploadKnowledge(file: File): Promise<any> {
    const form = new FormData()
    form.append('file', file)
    return this.request('/api/knowledge/upload', { method: 'POST', body: form } as any)
  }
  deleteKnowledge(id: string): Promise<any> { return this.request(`/api/knowledge/${id}`, { method: 'DELETE' }) }
  searchKnowledge(query: string, limit = 5): Promise<any> { return this.request('/api/knowledge/search', { method: 'POST', body: JSON.stringify({ query, limit }) }) }
  knowledgeChunks(id: string): Promise<any> { return this.request(`/api/knowledge/${id}/chunks`) }

  systemPerf(): Promise<any> { return this.request('/api/system/perf') }
  systemNetwork(): Promise<any> { return this.request('/api/system/network') }
  swarmAgents(): Promise<{ agents: any[] }> { return this.request('/api/swarm/agents') }
  guardianActivity(limit = 10): Promise<any[]> { return this.request(`/api/guardian/activity?limit=${limit}`) }
  thoughtStream(limit = 10): Promise<{ items: any[] }> { return this.request(`/api/thought-stream?limit=${limit}`) }
  intelUnreadCount(): Promise<{ unread_count: number }> { return this.request('/api/intel/unread-count') }
  knowledgeTopics(): Promise<any> { return this.request('/api/knowledge/topics') }
  predictiveNow(): Promise<any> { return this.request('/api/predictive/now') }
  privacyScan(): Promise<any> { return this.request('/api/privacy/scan', { method: 'POST' }) }

  workflows(): Promise<any[]> { return this.request('/api/workflows') }
  createWorkflow(data: any): Promise<any> { return this.request('/api/workflows', { method: 'POST', body: JSON.stringify(data) }) }
  billingCheckout(priceId: string, chainId?: number, paypal?: boolean): Promise<any> {
    return this.request(
      '/api/billing/checkout',
      { method: 'POST', body: JSON.stringify({ price_id: priceId, chain_id: chainId ?? 1, paypal: paypal ?? false }) },
    )
  }
  billingVerify(intentId: string, address: string, signature: string): Promise<any> {
    return this.request(
      '/api/billing/verify',
      { method: 'POST', body: JSON.stringify({ intent_id: intentId, address, signature }) },
    )
  }
  billingStatus(): Promise<any> { return this.request('/api/billing/status') }
  billingSetPlan(plan: string): Promise<any> { return this.request('/api/billing/plan', { method: 'POST', body: JSON.stringify({ plan }) }) }
  billingPrices(): Promise<any> { return this.request('/api/billing/prices') }
  updateWorkflow(id: string, data: any): Promise<any> { return this.request(`/api/workflows/${id}`, { method: 'PUT', body: JSON.stringify(data) }) }
  deleteWorkflow(id: string): Promise<any> { return this.request(`/api/workflows/${id}`, { method: 'DELETE' }) }
  toggleWorkflow(id: string): Promise<any> { return this.request(`/api/workflows/${id}/toggle`, { method: 'PATCH' }) }
  workflowRuns(id: string): Promise<any> { return this.request(`/api/workflows/${id}/runs`) }
  testWorkflow(id: string): Promise<any> { return this.request(`/api/workflows/${id}/test`, { method: 'POST' }) }
}

const api = new SalarApi()
export { api }
