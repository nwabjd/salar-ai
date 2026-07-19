export type Message = { id: string; role: 'user' | 'assistant'; content: string; created_at: string }
export type Conversation = { id: string; title: string; messages?: Message[] }
export type Memory = { id: string; title: string; content: string; layer: string; created_at: string }
export type DocumentItem = { id: string; filename: string; media_type: string; created_at: string }
export type Device = { id: string; name: string; platform: string; last_seen_at: string | null }

const saved = localStorage.getItem('salar.apiUrl')
export const DEFAULT_API = (import.meta.env.VITE_API_URL || saved || 'https://api.salar.example.com').replace(/\/$/, '')

export class SalarApi {
  constructor(public baseUrl = DEFAULT_API, public token = localStorage.getItem('salar.token') || '') {}
  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers)
    if (this.token) headers.set('Authorization', `Bearer ${this.token}`)
    if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
    const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers })
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || `Request failed (${response.status})`)
    return response.json()
  }
  async login(email: string, password: string) { const data = await this.request<{access_token:string}>('/api/auth/login', { method:'POST', body:JSON.stringify({email,password}) }); this.token=data.access_token; localStorage.setItem('salar.token', data.access_token); return data }
  conversations() { return this.request<Conversation[]>('/api/conversations') }
  conversation(id: string) { return this.request<Conversation>(`/api/conversations/${id}`) }
  createConversation(title='New conversation') { return this.request<Conversation>('/api/conversations', {method:'POST', body:JSON.stringify({title})}) }
  chat(conversation_id:string, content:string) { return this.request<{user_message:Message;assistant_message:Message}>('/api/chat', {method:'POST',body:JSON.stringify({conversation_id,content})}) }
  memories() { return this.request<Memory[]>('/api/memory') }
  saveMemory(title:string, content:string) { return this.request<Memory>('/api/memory',{method:'POST',body:JSON.stringify({title,content,layer:'long_term'})}) }
  documents() { return this.request<DocumentItem[]>('/api/documents') }
  async upload(file:File) { const body=new FormData(); body.append('file',file); return this.request<DocumentItem>('/api/documents',{method:'POST',body}) }
  devices() { return this.request<Device[]>('/api/devices') }
  registerDevice(name:string, platform='windows') { return this.request<Device & {token:string}>('/api/devices',{method:'POST',body:JSON.stringify({name,platform})}) }
  command(device_id:string, kind:string, payload:Record<string,unknown>) { return this.request('/api/commands',{method:'POST',body:JSON.stringify({device_id,kind,payload})}) }
  async nextDeviceCommand(deviceToken:string) {
    const response=await fetch(`${this.baseUrl}/api/device/commands/next`,{headers:{'X-Device-Token':deviceToken}})
    if(!response.ok) throw new Error('Device link rejected')
    return response.json() as Promise<null|{id:string;kind:string;payload:Record<string,unknown>}>
  }
  async completeDeviceCommand(id:string,deviceToken:string,result:{ok:boolean;detail:string;data?:Record<string,unknown>}) {
    return fetch(`${this.baseUrl}/api/device/commands/${id}/result`,{method:'POST',headers:{'Content-Type':'application/json','X-Device-Token':deviceToken},body:JSON.stringify({...result,data:result.data||{}})})
  }
}
