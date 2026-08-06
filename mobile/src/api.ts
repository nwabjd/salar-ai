import AsyncStorage from '@react-native-async-storage/async-storage';
import EventSource from 'react-native-sse';

export type Message = { id: string; role: 'user' | 'assistant'; content: string; created_at: string }
export type Conversation = { id: string; title: string; messages?: Message[] }

const TOKEN_KEY = 'salar.token';

export const DEFAULT_API = 'https://salar-backend.onrender.com';

async function getToken(): Promise<string> {
  return (await AsyncStorage.getItem(TOKEN_KEY)) || '';
}

async function setToken(token: string) {
  await AsyncStorage.setItem(TOKEN_KEY, token);
}

async function clearToken() {
  await AsyncStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers = new Headers(init.headers as any);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${DEFAULT_API}${path}`, { ...init, headers });
  if (!response.ok) {
    if (response.status === 401) throw new Error('Session expired — please sign in again');
    throw new Error((await response.json().catch(() => null))?.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export async function getBaseUrl() {
  return DEFAULT_API;
}

export async function supabaseLogin(supabaseToken: string) {
  const data = await request<{ access_token: string }>('/api/auth/supabase', { method: 'POST', body: JSON.stringify({ token: supabaseToken }) });
  await setToken(data.access_token);
  return data;
}

export async function validateSession() {
  return request<{ id: string; email: string }>('/api/auth/session');
}

export async function conversations() {
  return request<Conversation[]>('/api/conversations');
}

export async function createConversation(title = 'New conversation') {
  return request<Conversation>('/api/conversations', { method: 'POST', body: JSON.stringify({ title }) });
}

export async function getConversation(id: string) {
  return request<Conversation>(`/api/conversations/${id}`);
}

export function chatStream(
  conversationId: string,
  content: string,
  baseUrl: string,
  token: string,
  onToken: (token: string) => void,
  onDone: (messageId: string, createdAt: string) => void,
  onError?: (err: string) => void
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const es = new EventSource(`${baseUrl}/api/chat/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ conversation_id: conversationId, content }),
    polling: false,
  } as any);

  es.addEventListener('message', (event: any) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'token') onToken(data.content);
      if (data.type === 'done') { onDone(data.message_id, data.created_at); es.close(); }
    } catch {}
  });

  es.addEventListener('error', () => {
    onError?.('Stream connection lost');
    es.close();
  });

  return () => es.close();
}

export async function tts(text: string): Promise<ArrayBuffer> {
  const token = await getToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(`${DEFAULT_API}/api/tts`, { method: 'POST', headers, body: JSON.stringify({ conversation_id: 'tts', content: text }) });
  if (!response.ok) throw new Error('TTS failed');
  return response.arrayBuffer();
}

export { getToken, setToken, clearToken };
