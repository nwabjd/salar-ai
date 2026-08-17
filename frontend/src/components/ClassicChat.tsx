import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Mic2, Send, Command, Image, Layers, Monitor, Sparkles, Loader } from 'lucide-react'
import { Conversation, Message, SalarApi } from '../api'

interface CommandSuggestion {
  icon: React.ReactNode
  label: string
  prefix: string
}

const COMMANDS: CommandSuggestion[] = [
  { icon: <Image size={16} />, label: 'Clone UI', prefix: '/clone' },
  { icon: <Layers size={16} />, label: 'Import Figma', prefix: '/figma' },
  { icon: <Monitor size={16} />, label: 'Create Page', prefix: '/page' },
  { icon: <Sparkles size={16} />, label: 'Improve', prefix: '/improve' },
]

function TypingDots() {
  return (
    <span className="typing-dots">
      {[1, 2, 3].map((d) => (
        <span key={d} className="typing-dot" style={{ animationDelay: `${d * 0.15}s` }} />
      ))}
    </span>
  )
}

export function ClassicChat({ api, onLive }: { api: SalarApi; onLive: () => void }) {
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [streaming, setStreaming] = useState('')
  const [toolActivity, setToolActivity] = useState('')
  const [showCmd, setShowCmd] = useState(false)
  const [cmdIdx, setCmdIdx] = useState(0)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const [inputFocused, setInputFocused] = useState(false)
  const streamBuf = useRef('')
  const endRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const cmdRef = useRef<HTMLDivElement>(null)

  // Load conversation
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

  // Command palette logic
  useEffect(() => {
    if (input.startsWith('/') && !input.includes(' ')) {
      setShowCmd(true)
      const idx = COMMANDS.findIndex((c) => c.prefix.startsWith(input))
      setCmdIdx(idx >= 0 ? idx : 0)
    } else {
      setShowCmd(false)
    }
  }, [input])

  // Cursor glow
  useEffect(() => {
    const handler = (e: MouseEvent) => setMousePos({ x: e.clientX, y: e.clientY })
    window.addEventListener('mousemove', handler)
    return () => window.removeEventListener('mousemove', handler)
  }, [])

  // Close cmd palette on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (cmdRef.current && !cmdRef.current.contains(e.target as Node)) setShowCmd(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Auto-resize textarea
  const adjustHeight = useCallback((reset?: boolean) => {
    const ta = textareaRef.current
    if (!ta) return
    if (reset) { ta.style.height = '60px'; return }
    ta.style.height = '60px'
    const h = Math.max(60, Math.min(ta.scrollHeight, 200))
    ta.style.height = `${h}px`
  }, [])

  function selectCommand(cmd: CommandSuggestion) {
    setInput(cmd.prefix + ' ')
    setShowCmd(false)
    textareaRef.current?.focus()
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (showCmd) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setCmdIdx((i) => (i + 1) % COMMANDS.length) }
      else if (e.key === 'ArrowUp') { e.preventDefault(); setCmdIdx((i) => (i - 1 + COMMANDS.length) % COMMANDS.length) }
      else if (e.key === 'Tab' || e.key === 'Enter') { e.preventDefault(); selectCommand(COMMANDS[cmdIdx]) }
      else if (e.key === 'Escape') { e.preventDefault(); setShowCmd(false) }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  function send() {
    if (!input.trim() || !conversation || busy) return
    sendContent(input)
  }

  function sendContent(content: string) {
    if (!content.trim() || !conversation || busy) return
    setInput(''); setBusy(true); setStreaming(''); setToolActivity(''); streamBuf.current = ''
    adjustHeight(true)
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

  return (
    <div className="ai-chat-wrap">
      {/* Ambient blurs */}
      <div className="ai-chat-orbs">
        <div className="ai-orb ai-orb-violet" />
        <div className="ai-orb ai-orb-indigo" />
        <div className="ai-orb ai-orb-fuchsia" />
      </div>

      {/* Cursor glow */}
      {inputFocused && (
        <div
          className="ai-cursor-glow"
          style={{ left: mousePos.x - 400, top: mousePos.y - 400 }}
        />
      )}

      <div className="ai-chat-inner">
        {/* Title */}
        <div className="ai-chat-title">
          <h1>{messages.length ? 'Command stream' : 'How can I help today?'}</h1>
          <div className="ai-chat-title-line" />
          {!messages.length && <p>Type a command or ask a question</p>}
        </div>

        {/* Messages (shown after first message) */}
        {messages.length > 0 && (
          <div className="ai-chat-messages">
            {messages.map((msg) => (
              <div key={msg.id} className={`ai-msg ai-msg-${msg.role}`}>
                <span className="ai-msg-role">{msg.role === 'assistant' ? 'SALAR' : 'YOU'}</span>
                <p>{msg.content}</p>
              </div>
            ))}
            {streaming && (
              <div className="ai-msg ai-msg-assistant ai-thinking">
                <span className="ai-msg-role">SALAR</span>
                <p>{streaming}</p>
              </div>
            )}
            {toolActivity && !streaming && (
              <div className="ai-msg ai-msg-assistant ai-thinking">
                <span className="ai-msg-role">SALAR</span>
                <p className="ai-tool-hint">{toolActivity}</p>
              </div>
            )}
            {busy && !streaming && !toolActivity && (
              <div className="ai-msg ai-msg-assistant ai-thinking">
                <span className="ai-msg-role">SALAR</span>
                <p>Reasoning across your private context…<TypingDots /></p>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}

        {/* Chat box */}
        <div className="ai-chat-box">
          {/* Command palette */}
          {showCmd && (
            <div className="ai-cmd-palette" ref={cmdRef}>
              {COMMANDS.map((cmd, i) => (
                <div
                  key={cmd.prefix}
                  className={`ai-cmd-item${i === cmdIdx ? ' active' : ''}`}
                  onClick={() => selectCommand(cmd)}
                >
                  <span className="ai-cmd-icon">{cmd.icon}</span>
                  <span className="ai-cmd-label">{cmd.label}</span>
                  <span className="ai-cmd-prefix">{cmd.prefix}</span>
                </div>
              ))}
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => { setInput(e.target.value); adjustHeight() }}
            onKeyDown={handleKeyDown}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
            placeholder="Ask Salaar a question…"
            rows={1}
          />

          <div className="ai-chat-toolbar">
            <div className="ai-toolbar-left">
              <button
                className={`ai-icon-btn${showCmd ? ' active' : ''}`}
                onClick={() => { setShowCmd((v) => !v); textareaRef.current?.focus() }}
                title="Commands"
              >
                <Command size={16} />
              </button>
              <button className="ai-icon-btn" onClick={onLive} title="Enter Live mode">
                <Mic2 size={16} />
              </button>
            </div>
            <button
              className={`ai-send-btn${input.trim() ? ' ready' : ''}`}
              onClick={send}
              disabled={busy || !input.trim()}
            >
              {busy ? <Loader size={16} className="ai-spin" /> : <Send size={16} />}
              <span>Send</span>
            </button>
          </div>
        </div>

        {/* Suggestion chips (only when no messages) */}
        {!messages.length && (
          <div className="ai-chips">
            {COMMANDS.map((cmd, i) => (
              <button key={cmd.prefix} className="ai-chip" onClick={() => selectCommand(cmd)}>
                {cmd.icon}<span>{cmd.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
