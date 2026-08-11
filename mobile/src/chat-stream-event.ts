export type ChatStreamHandlers = {
  onToken: (token: string) => void
  onDone: (messageId: string, createdAt: string) => void
  onError?: (error: string) => void
  close: () => void
}

export function handleChatStreamEvent(data: unknown, handlers: ChatStreamHandlers): boolean {
  if (!data || typeof data !== 'object' || !("type" in data)) return false
  const event = data as Record<string, unknown>

  if (event.type === 'token') {
    handlers.onToken(String(event.content || ''))
    return false
  }
  if (event.type === 'done') {
    handlers.onDone(String(event.message_id || ''), String(event.created_at || ''))
    handlers.close()
    return true
  }
  if (event.type === 'error') {
    handlers.close()
    handlers.onError?.(String(event.detail || event.error || 'Stream failed'))
    return true
  }
  return false
}
