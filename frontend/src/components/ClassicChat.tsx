import React, { useEffect, useRef, useState } from 'react'
import { Copy, RefreshCcw, Share, ThumbsUp, ThumbsDown, Check, Mic2 } from 'lucide-react'
import { ChatInput, ChatInputTextArea, ChatInputSubmit } from './ui/chat-input'
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
  const [input, setInput] = useState('')
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

  function handleSend() {
    const content = input.trim()
    if (!content || !conversation || busy) return
    setInput('')
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
    <div className="ai-chat-wrap">
      <div className="ai-chat-orbs">
        <div className="ai-orb ai-orb-violet" />
        <div className="ai-orb ai-orb-indigo" />
        <div className="ai-orb ai-orb-fuchsia" />
      </div>

      <div className="ai-chat-inner">
        {!hasMessages && (
          <div className="ai-chat-title">
            <h1>How can I help today?</h1>
            <div className="ai-chat-title-line" />
            <p>Type a command or ask a question</p>
          </div>
        )}

        {hasMessages && (
          <div className="ai-conversation">
            <div className="ai-conv-scroll">
              {messages.map((msg) => (
                <div key={msg.id} className={`ai-msg ${msg.role === 'assistant' ? 'ai-msg-assistant' : 'ai-msg-user'}`}>
                  {msg.role === 'assistant' && (
                    <img src="https://ui-avatars.com/api/?name=SALAR&background=8b5cf6&color=fff&bold=true&size=32" alt="SALAR" className="ai-msg-avatar" width={32} height={32} />
                  )}
                  <div className="ai-msg-col">
                    <div className="ai-msg-content"><p>{msg.content}</p></div>
                    {msg.role === 'assistant' && <MessageActions content={msg.content} />}
                  </div>
                </div>
              ))}
              {streaming && (
                <div className="ai-msg ai-msg-assistant">
                  <img src="https://ui-avatars.com/api/?name=SALAR&background=8b5cf6&color=fff&bold=true&size=32" alt="SALAR" className="ai-msg-avatar" width={32} height={32} />
                  <div className="ai-msg-col">
                    <div className="ai-msg-content"><p>{streaming}<span className="ai-cursor-blink">|</span></p></div>
                  </div>
                </div>
              )}
              {toolActivity && !streaming && (
                <div className="ai-msg ai-msg-assistant">
                  <img src="https://ui-avatars.com/api/?name=SALAR&background=8b5cf6&color=fff&bold=true&size=32" alt="SALAR" className="ai-msg-avatar" width={32} height={32} />
                  <div className="ai-msg-col">
                    <div className="ai-msg-content"><p className="ai-tool-hint">{toolActivity}</p></div>
                  </div>
                </div>
              )}
              {busy && !streaming && !toolActivity && (
                <div className="ai-msg ai-msg-assistant">
                  <img src="https://ui-avatars.com/api/?name=SALAR&background=8b5cf6&color=fff&bold=true&size=32" alt="SALAR" className="ai-msg-avatar" width={32} height={32} />
                  <div className="ai-msg-col">
                    <div className="ai-msg-content"><p>Reasoning across your private context…<TypingDots /></p></div>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          </div>
        )}

        <div className="ai-composer">
          <ChatInput
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onSubmit={handleSend}
            loading={busy}
          >
            <ChatInputTextArea placeholder="Ask Salaar a question…" />
            <div className="flex items-center gap-2">
              <button
                className="pi-icon-btn pi-live"
                onClick={onLive}
                title="Live voice"
              >
                <Mic2 size={16} />
              </button>
              <ChatInputSubmit />
            </div>
          </ChatInput>
        </div>
      </div>
    </div>
  )
}
