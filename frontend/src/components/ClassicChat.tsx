import React, { useEffect, useRef, useState } from 'react'
import { Copy, RefreshCcw, Share, ThumbsUp, ThumbsDown, Check, Mic2 } from 'lucide-react'
import { OrbInput } from './ui/animated-input'
import { Conversation, Message, SalarApi } from '../api'

function TypingDots() {
  return (
    <span className="typing-dots">
      {[1, 2, 3].map((d) => (
        <span key={d} className="typing-dot" style={{ animationDelay: `${d * 0.15}s` }} />
      ))}
    </span>
  )
}

function MessageActions({ content }: { content: string }) {
  const [copied, setCopied] = useState(false)
  function handleCopy() {
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="ai-msg-actions">
      <button className="ai-msg-action" onClick={handleCopy} title="Copy">
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
      <button className="ai-msg-action" title="Retry"><RefreshCcw size={14} /></button>
      <button className="ai-msg-action" title="Like"><ThumbsUp size={14} /></button>
      <button className="ai-msg-action" title="Dislike"><ThumbsDown size={14} /></button>
      <button className="ai-msg-action" title="Share"><Share size={14} /></button>
    </div>
  )
}

export function ClassicChat({ api, onLive }: { api: SalarApi; onLive: () => void }) {
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)
  const [streaming, setStreaming] = useState('')
  const [toolActivity, setToolActivity] = useState('')
  const streamBuf = useRef('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.conversations().then(async (list) => {
      const item = list[0] || (await api.createConversation())
      setConversation(item)
      if (list[0]) {
        const conv = await api.conversation(item.id)
        setMessages(conv.messages || [])
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming, toolActivity])

  function handleSend(content: string) {
    if (!content.trim() || !conversation || busy) return
    setBusy(true); setStreaming(''); setToolActivity(''); streamBuf.current = ''
    const userMsg: Message = { id: 'tmp-' + Date.now(), role: 'user', content, created_at: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    let done = false
    const finish = () => { if (done) return; done = true; setStreaming(''); streamBuf.current = ''; setToolActivity(''); setBusy(false) }
    api.chatStream(
      conversation.id,
      content,
      (token) => { streamBuf.current += token; setStreaming(streamBuf.current); setToolActivity('') },
      (messageId, createdAt) => {
        const reply = streamBuf.current
        setMessages((prev) => [...prev.slice(0, -1), userMsg, { id: messageId, role: 'assistant', content: reply, created_at: createdAt }])
        finish()
      },
      (err) => {
        console.error('Stream failed:', err)
        if (streamBuf.current) {
          const reply = streamBuf.current
          setMessages((prev) => [...prev.slice(0, -1), userMsg, { id: 'err-' + Date.now(), role: 'assistant', content: reply + '\n\n[Stream interrupted]', created_at: new Date().toISOString() }])
        }
        finish()
      },
      (toolName) => { setToolActivity(`Using ${toolName}…`) },
      () => { setToolActivity('') },
    )
  }

  const hasMessages = messages.length > 0 || busy

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        {!hasMessages ? (
          /* EMPTY STATE: heading + composer centered in viewport */
          <div className="flex h-full flex-col items-center justify-center px-4" style={{ gap: 40 }}>
            <h1 style={{ fontSize: 'clamp(24px, 4vw, 36px)', fontWeight: 300, color: 'rgba(255,255,255,.65)', letterSpacing: '-.02em', margin: 0 }}>
              How can I help you today?
            </h1>
            <div style={{ width: 'min(1000px, calc(100vw - 48px))' }}>
              <OrbInput onSubmit={handleSend} />
            </div>
          </div>
        ) : (
          /* ACTIVE STATE: messages + sticky composer at bottom */
          <>
            <div style={{ maxWidth: 1000, margin: '0 auto', padding: '24px 24px 0' }}>
              {messages.map((msg) => (
                <div key={msg.id} style={{ marginBottom: 24, display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  {msg.role === 'assistant' ? (
                    <div style={{ color: 'rgba(255,255,255,.85)', fontSize: 15, lineHeight: 1.7, maxWidth: '85%' }}>
                      <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{msg.content}</p>
                      <MessageActions content={msg.content} />
                    </div>
                  ) : (
                    <div style={{
                      maxWidth: '80%',
                      background: 'rgba(255,255,255,.08)',
                      border: '1px solid rgba(255,255,255,.08)',
                      borderRadius: '20px 20px 4px 20px',
                      padding: '10px 16px',
                    }}>
                      <p style={{ margin: 0, color: 'rgba(255,255,255,.85)', fontSize: 15, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{msg.content}</p>
                    </div>
                  )}
                </div>
              ))}
              {streaming && (
                <div style={{ marginBottom: 24 }}>
                  <div style={{ color: 'rgba(255,255,255,.85)', fontSize: 15, lineHeight: 1.7 }}>
                    <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{streaming}<span style={{ opacity: .5, animation: 'aiBlink 1s step-end infinite' }}>|</span></p>
                  </div>
                </div>
              )}
              {toolActivity && !streaming && (
                <div style={{ marginBottom: 24 }}>
                  <p style={{ color: 'rgba(201,165,110,.8)', fontSize: 13, fontStyle: 'italic', margin: 0 }}>{toolActivity}</p>
                </div>
              )}
              {busy && !streaming && !toolActivity && (
                <div style={{ marginBottom: 24 }}>
                  <p style={{ color: 'rgba(255,255,255,.5)', fontSize: 15, margin: 0 }}>
                    Reasoning across your private context…<TypingDots />
                  </p>
                </div>
              )}
              <div ref={endRef} />
            </div>
          </>
        )}
      </div>

      {/* COMPOSER: sticky at bottom when messages exist, hidden in empty state (it's inside the centered flex above) */}
      {hasMessages && (
        <div className="orb-composer-sticky">
          <div className="orb-composer-inner">
            <OrbInput
              onSubmit={handleSend}
              placeholder={busy ? "Salaar is thinking..." : undefined}
              disabled={busy}
              loading={busy}
            />
            <button
              onClick={onLive}
              title="Live voice"
              aria-label="Open live voice"
              className="orb-mic-btn"
            >
              <Mic2 size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
