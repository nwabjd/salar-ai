import React, { useEffect, useRef, useState } from 'react'
import { Copy, RefreshCcw, Share, ThumbsUp, ThumbsDown, Check, Mic2, ArrowUp, Square, Plus } from 'lucide-react'
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
  const [showPlusMenu, setShowPlusMenu] = useState(false)

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

  function handleStop() {
    if (streamBuf.current) {
      const reply = streamBuf.current
      const userMsg = messages[messages.length - 1]
      setMessages((prev) => [...prev.slice(0, -1), userMsg, { id: 'stop-' + Date.now(), role: 'assistant', content: reply, created_at: new Date().toISOString() }])
    }
    setStreaming(''); streamBuf.current = ''; setToolActivity(''); setBusy(false)
  }

  const hasMessages = messages.length > 0 || busy
  const composerHasText = input.trim().length > 0

  return (
    <div className="g-chat-wrap">
      <div className="g-chat-glow" />

      <div className="g-chat-inner">
        {!hasMessages && (
          <div className="g-chat-empty">
            <div className="g-empty-orb" />
            <h1>How can I help you today?</h1>
          </div>
        )}

        {hasMessages && (
          <div className="g-conversation">
            <div className="g-conv-scroll">
              {messages.map((msg) => (
                <div key={msg.id} className={`g-msg ${msg.role === 'assistant' ? 'g-msg-assistant' : 'g-msg-user'}`}>
                  {msg.role === 'assistant' ? (
                    <div className="g-msg-content g-msg-content-assistant">
                      <p>{msg.content}</p>
                    </div>
                  ) : (
                    <div className="g-msg-content g-msg-content-user">
                      <p>{msg.content}</p>
                    </div>
                  )}
                </div>
              ))}
              {streaming && (
                <div className="g-msg g-msg-assistant">
                  <div className="g-msg-content g-msg-content-assistant">
                    <p>{streaming}<span className="g-cursor-blink">|</span></p>
                  </div>
                </div>
              )}
              {toolActivity && !streaming && (
                <div className="g-msg g-msg-assistant">
                  <div className="g-msg-content g-msg-content-assistant">
                    <p className="g-tool-hint">{toolActivity}</p>
                  </div>
                </div>
              )}
              {busy && !streaming && !toolActivity && (
                <div className="g-msg g-msg-assistant">
                  <div className="g-msg-content g-msg-content-assistant">
                    <p>Reasoning across your private context…<TypingDots /></p>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          </div>
        )}

        <div className="g-composer-wrap">
          <div className="g-composer">
            <div className="g-composer-plus">
              <button
                className="g-plus-btn"
                onClick={() => setShowPlusMenu(!showPlusMenu)}
                title="Menu"
              >
                <Plus size={18} />
              </button>
              {showPlusMenu && (
                <div className="g-plus-menu">
                  <button className="g-plus-item">Upload file</button>
                  <button className="g-plus-item">Drive</button>
                  <button className="g-plus-item">GitHub</button>
                </div>
              )}
            </div>

            <div className="g-composer-input">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey && composerHasText && !busy) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
                placeholder="Ask Salaar a question…"
                rows={1}
              />
            </div>

            <div className="g-composer-mic">
              <button
                className="g-mic-btn"
                onClick={onLive}
                title="Live voice"
              >
                <Mic2 size={18} />
              </button>
            </div>

            <div className="g-composer-send">
              {busy ? (
                <button className="g-send-btn g-send-stop" onClick={handleStop} title="Stop">
                  <Square size={16} />
                </button>
              ) : (
                <button
                  className={`g-send-btn ${composerHasText ? 'g-send-ready' : 'g-send-disabled'}`}
                  disabled={!composerHasText}
                  onClick={handleSend}
                  title="Send"
                >
                  <ArrowUp size={18} strokeWidth={2.5} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
