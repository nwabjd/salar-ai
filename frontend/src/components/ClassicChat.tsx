import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Globe, Paperclip, Send, Command, Image, Layers, Monitor, Sparkles, Loader, Copy, RefreshCcw, Share, ThumbsUp, ThumbsDown, Check, Mic2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAutoResizeTextarea } from '../hooks/use-auto-resize-textarea'
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
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [streaming, setStreaming] = useState('')
  const [toolActivity, setToolActivity] = useState('')
  const [showCmd, setShowCmd] = useState(false)
  const [cmdIdx, setCmdIdx] = useState(0)
  const [isFocused, setIsFocused] = useState(false)
  const [showSearch, setShowSearch] = useState(true)
  const streamBuf = useRef('')
  const endRef = useRef<HTMLDivElement>(null)
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 52, maxHeight: 200 })
  const cmdRef = useRef<HTMLDivElement>(null)

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

  useEffect(() => {
    if (input.startsWith('/') && !input.includes(' ')) {
      setShowCmd(true)
      const idx = COMMANDS.findIndex((c) => c.prefix.startsWith(input))
      setCmdIdx(idx >= 0 ? idx : 0)
    } else {
      setShowCmd(false)
    }
  }, [input])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (cmdRef.current && !cmdRef.current.contains(e.target as Node)) setShowCmd(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
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

        {/* AI Input Search */}
        <div className="ai-composer">
          <div className="ai-search-wrap">
            {showCmd && (
              <div className="ai-cmd-palette" ref={cmdRef}>
                {COMMANDS.map((cmd, i) => (
                  <div key={cmd.prefix} className={`ai-cmd-item${i === cmdIdx ? ' active' : ''}`} onClick={() => selectCommand(cmd)}>
                    <span className="ai-cmd-icon">{cmd.icon}</span>
                    <span className="ai-cmd-label">{cmd.label}</span>
                    <span className="ai-cmd-prefix">{cmd.prefix}</span>
                  </div>
                ))}
              </div>
            )}

            <div className={`ai-search-box${isFocused ? ' focused' : ''}`} onClick={() => textareaRef.current?.focus()}>
              <div className="ai-search-textarea-wrap">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => { setInput(e.target.value); adjustHeight() }}
                  onKeyDown={handleKeyDown}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setIsFocused(false)}
                  placeholder="Ask Salaar a question…"
                  className="ai-search-textarea"
                />
              </div>

              <div className="ai-search-bottom">
                <div className="ai-search-left">
                  <label className="ai-search-attach" title="Attach file">
                    <input className="hidden" type="file" />
                    <Paperclip size={16} />
                  </label>
                  <button
                    className={`ai-search-globe${showSearch ? ' active' : ''}`}
                    onClick={() => setShowSearch((v) => !v)}
                    title="Toggle web search"
                  >
                    <motion.div animate={{ rotate: showSearch ? 180 : 0, scale: showSearch ? 1.1 : 1 }} transition={{ type: 'spring', stiffness: 260, damping: 25 }} whileHover={{ rotate: showSearch ? 180 : 15, scale: 1.1 }}>
                      <Globe size={16} />
                    </motion.div>
                    <AnimatePresence>
                      {showSearch && (
                        <motion.span initial={{ width: 0, opacity: 0 }} animate={{ width: 'auto', opacity: 1 }} exit={{ width: 0, opacity: 0 }} transition={{ duration: 0.2 }}>
                          Search
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </button>
                  <button className="ai-search-live" onClick={onLive} title="Enter Live mode">
                    <Mic2 size={16} />
                    <span>Live</span>
                  </button>
                </div>
                <button className={`ai-search-send${input.trim() ? ' ready' : ''}`} onClick={send} disabled={busy || !input.trim()}>
                  {busy ? <Loader size={16} className="ai-spin" /> : <Send size={16} />}
                </button>
              </div>
            </div>
          </div>
        </div>


      </div>
    </div>
  )
}
