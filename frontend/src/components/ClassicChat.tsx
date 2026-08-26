import React, { useEffect, useRef, useState } from 'react'
import { Copy, RefreshCcw, Share, ThumbsUp, ThumbsDown, Check, Cpu } from 'lucide-react'
import { OrbInput } from './ui/animated-input'
import { Conversation, Message, SalarApi } from '../api'
import { useMode, MODE_INFO } from '../contexts/ModeContext'
import { useSettings } from '../contexts/SettingsContext'

function LocalToggle({ localMode, onToggle }: { localMode: boolean; onToggle: () => void }) {
  return (
    <button
      className={`local-toggle${localMode ? ' active' : ''}`}
      onClick={onToggle}
      title={localMode ? 'Switch to cloud model' : 'Switch to your local fine-tuned model (runs on your PC)'}
    >
      <Cpu size={14} />
      <span>{localMode ? 'Local' : 'Cloud'}</span>
    </button>
  )
}

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
  const [localMode, setLocalMode] = useState(false)
  const streamBuf = useRef('')
  const endRef = useRef<HTMLDivElement>(null)
  const { mode } = useMode()
  const { settings } = useSettings()

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
    const modePrompt = MODE_INFO[mode].prompt
    const fullContent = modePrompt ? `${modePrompt}\n\n${content}` : content
    setBusy(true); setStreaming(''); setToolActivity(''); streamBuf.current = ''
    const userMsg: Message = { id: 'tmp-' + Date.now(), role: 'user', content, created_at: new Date().toISOString() }
    setMessages((prev) => [...prev, userMsg])
    let done = false
    const finish = () => { if (done) return; done = true; setStreaming(''); streamBuf.current = ''; setToolActivity(''); setBusy(false) }

    if (localMode) {
      setToolActivity('Running on your PC (local model)…')
      const history = messages.filter(m => !m.id.startsWith('tmp-') && !m.id.startsWith('err-')).slice(-10).map(m => ({ role: m.role, content: m.content }))
      api.ollamaChat([...history, { role: 'user', content: fullContent }])
        .then((result) => {
          const toolsNote = result.executed?.length ? `\n\n[${result.executed.map(e => e.tool).join(', ')} executed on your PC]` : ''
          setMessages((prev) => [...prev.slice(0, -1), userMsg, { id: 'local-' + Date.now(), role: 'assistant', content: (result.content || '(empty response)') + toolsNote, created_at: new Date().toISOString() }])
          finish()
        })
        .catch((err) => {
          console.error('Local model failed:', err)
          const msg = String(err?.message || err)
          setMessages((prev) => [...prev.slice(0, -1), userMsg, { id: 'err-' + Date.now(), role: 'assistant', content: msg.includes('No connected device') ? 'Local model needs the SALAR desktop app running (with Ollama).' : `Local model error: ${msg}`, created_at: new Date().toISOString() }])
          finish()
        })
      return
    }

    if (!settings.streaming) {
      api.chat(conversation.id, fullContent, mode)
        .then((res) => {
          setMessages((prev) => [...prev.slice(0, -1), userMsg, res.assistant_message])
          finish()
        })
        .catch((err) => {
          console.error('Chat failed:', err)
          setMessages((prev) => [...prev.slice(0, -1), userMsg, { id: 'err-' + Date.now(), role: 'assistant', content: 'Failed to get response.', created_at: new Date().toISOString() }])
          finish()
        })
      return
    }

    api.chatStream(
      conversation.id,
      fullContent,
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
      false,
      mode,
    )
  }

  const hasMessages = messages.length > 0 || busy

  return (
    <div className="cc-wrap">
      <div className="cc-scroll">
        {!hasMessages ? (
          <div className="cc-empty">
            <h1 className="cc-empty-heading">How can I help you today?</h1>
            <div className="cc-composer-wrap">
              <div className="composer-row">
                <LocalToggle localMode={localMode} onToggle={() => setLocalMode(v => !v)} />
                <OrbInput onSubmit={handleSend} onOrbClick={onLive} />
              </div>
            </div>
          </div>
        ) : (
          <div className="cc-messages">
            {messages.map((msg) => (
              <div key={msg.id} className={msg.role === 'user' ? 'cc-msg cc-msg-user' : 'cc-msg cc-msg-assistant'}>
                {msg.role === 'assistant' ? (
                  <div className="cc-msg-body">
                    <p className="cc-msg-text">{msg.content}</p>
                    <MessageActions content={msg.content} />
                  </div>
                ) : (
                  <div className="cc-msg-bubble-user">
                    <p className="cc-msg-text">{msg.content}</p>
                  </div>
                )}
              </div>
            ))}
            {streaming && (
              <div className="cc-msg cc-msg-assistant">
                <div className="cc-msg-body">
                  <p className="cc-msg-text">{streaming}<span className="cc-cursor">|</span></p>
                </div>
              </div>
            )}
            {toolActivity && !streaming && (
              <div className="cc-msg cc-msg-assistant">
                <p className="cc-tool-activity">{toolActivity}</p>
              </div>
            )}
            {busy && !streaming && !toolActivity && (
              <div className="cc-msg cc-msg-assistant">
                <p className="cc-msg-text cc-msg-idle">
                  Reasoning across your private context…<TypingDots />
                </p>
              </div>
            )}
            <div ref={endRef} />
          </div>
        )}
      </div>

      {hasMessages && (
        <div className="orb-composer-sticky">
          <div className="orb-composer-inner">
            <div className="composer-row">
              <LocalToggle localMode={localMode} onToggle={() => setLocalMode(v => !v)} />
              <OrbInput
                onSubmit={handleSend}
                onOrbClick={onLive}
                placeholder={busy ? "Salaar is thinking..." : (localMode ? "Ask your local SALAR model…" : undefined)}
                disabled={busy}
                loading={busy}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
