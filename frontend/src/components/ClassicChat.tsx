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
      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto">
        {!hasMessages && (
          <div className="flex h-full flex-col items-center justify-center gap-6 px-4">
            <h1 className="text-3xl sm:text-4xl font-light text-white/80 text-center">How can I help you today?</h1>
          </div>
        )}

        {hasMessages && (
          <div className="mx-auto w-full max-w-3xl px-4 py-6">
            {messages.map((msg) => (
              <div key={msg.id} className={`mb-6 ${msg.role === 'user' ? 'flex justify-end' : ''}`}>
                {msg.role === 'assistant' ? (
                  <div className="text-white/85 text-[15px] leading-relaxed">
                    <p className="m-0 whitespace-pre-wrap">{msg.content}</p>
                    <MessageActions content={msg.content} />
                  </div>
                ) : (
                  <div className="max-w-[80%] bg-white/10 border border-white/10 rounded-2xl rounded-tr-sm px-4 py-3">
                    <p className="m-0 text-white/85 text-[15px] leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  </div>
                )}
              </div>
            ))}
            {streaming && (
              <div className="mb-6">
                <div className="text-white/85 text-[15px] leading-relaxed">
                  <p className="m-0 whitespace-pre-wrap">{streaming}<span className="opacity-50 animate-pulse">|</span></p>
                </div>
              </div>
            )}
            {toolActivity && !streaming && (
              <div className="mb-6">
                <p className="text-amber-300/70 text-[13px] italic m-0">{toolActivity}</p>
              </div>
            )}
            {busy && !streaming && !toolActivity && (
              <div className="mb-6">
                <p className="text-white/50 text-[15px] m-0">Reasoning across your private context…<TypingDots /></p>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* Animated Input */}
      <div className="mx-auto w-full max-w-3xl px-4 pb-6">
        <div className="relative">
          <OrbInput
            onSubmit={handleSend}
            placeholder={busy ? "Salaar is thinking..." : undefined}
          />
          <button
            className="absolute right-4 top-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white/10 border border-white/20 text-white/50 flex items-center justify-center hover:bg-white/15 hover:text-white/80 transition-all"
            onClick={onLive}
            title="Live voice"
          >
            <Mic2 size={18} />
          </button>
        </div>
      </div>
    </div>
  )
}
