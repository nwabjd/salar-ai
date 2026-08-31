import { useEffect, useRef, useState } from 'react'
import {
  Check, Copy, Pencil, RefreshCw, ThumbsDown, ThumbsUp, Wand2,
} from 'lucide-react'
import type { Conversation, Message } from '../api'
import { RichBlock, inlineTextForTitle } from './rich'
import Composer from './Composer'

interface ToolActivity {
  tool: string
  args?: Record<string, unknown>
  result?: Record<string, unknown>
}

interface ChatViewProps {
  apiConversation: Conversation | null
  messages: Message[]
  busy: boolean
  streamingPartial: string
  toolActivity: ToolActivity | null
  error: string
  onSend: (text: string, files: File[]) => void
  onStop: () => void
  onRetry: () => void
  onNewChat: () => void
  onAttachFiles: (files: File[]) => void
}

function fmtTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

function MessageActions({ copied, onCopy, onRegenerate, onEdit, onLike, onDislike }: {
  copied: boolean
  onCopy: () => void
  onRegenerate?: () => void
  onEdit?: () => void
  onLike?: () => void
  onDislike?: () => void
}) {
  return (
    <div className="ws-msg__actions">
      <button className="ws-msg__action" onClick={onCopy} title="Copy">
        {copied ? <Check size={13} /> : <Copy size={13} />}
      </button>
      {onRegenerate && <button className="ws-msg__action" onClick={onRegenerate} title="Regenerate"><RefreshCw size={13} /></button>}
      {onEdit && <button className="ws-msg__action" onClick={onEdit} title="Edit message"><Pencil size={13} /></button>}
      {onLike && <button className="ws-msg__action" onClick={onLike} title="Helpful"><ThumbsUp size={13} /></button>}
      {onDislike && <button className="ws-msg__action" onClick={onDislike} title="Not helpful"><ThumbsDown size={13} /></button>}
    </div>
  )
}

export default function ChatView({
  apiConversation, messages, busy, streamingPartial, toolActivity, error,
  onSend, onStop, onRetry, onNewChat, onAttachFiles,
}: ChatViewProps) {
  const endRef = useRef<HTMLDivElement>(null)
  const [edited, setEdited] = useState<{ id: string; text: string } | null>(null)

  useEffect(() => {
    if (!busy) endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    else endRef.current?.scrollIntoView({ behavior: 'auto', block: 'end' })
  }, [messages.length, streamingPartial, busy, error])

  const copy = async (text: string) => {
    try { await navigator.clipboard.writeText(text) } catch { /* ignore */ }
  }

  const isEmpty = messages.length === 0 && !busy && !error

  return (
    <div className="ws-chat">
      <div className="ws-chat__scroll">
        {isEmpty ? (
          <div className="ws-chat__empty">
            <div className="ws-home__eyebrow">NEW CONVERSATION</div>
            <h1 className="ws-home__title" style={{ fontSize: 'clamp(24px, 3vw, 34px)', marginTop: 10 }}>What shall we accomplish?</h1>
            <p className="ws-home__sub">Salaar adapts its intelligence mode to what you ask. Type below to begin.</p>
            <div className="ws-home__quick" style={{ marginTop: 24 }}>
              {['Plan my day', 'Research a topic', 'Write code', 'Draft an email'].map((s) => (
                <button key={s} className="ws-quick" onClick={() => onSend(s, [])}>{s}</button>
              ))}
            </div>
          </div>
        ) : (
          <div className="ws-thread">
            {apiConversation && (
              <div className="ws-thread__head">
                <span className="ws-thread__convo">{inlineTextForTitle(apiConversation.title)}</span>
              </div>
            )}
            {messages.map((m, idx) => {
              const isUser = m.role === 'user'
              const prev = messages[idx - 1]
              const streaming = m.role === 'assistant' && idx === messages.length - 1 && busy && !streamingPartial && !m.content
              return (
                <div key={m.id} className={`ws-msg${isUser ? ' ws-msg--user' : ' ws-msg--assistant'}`}>
                  <div className="ws-msg__row">
                    <span className="ws-msg__avatar">{isUser ? 'U' : 'S'}</span>
                    <div className="ws-msg__body">
                      {isUser ? (
                        <>
                          {m.content}
                          <div className="ws-msg__meta">{fmtTime(m.created_at)}</div>
                        </>
                      ) : (
                        <>
                          {streaming ? (
                            <div className="ws-msg__typing"><i /><i /><i /></div>
                          ) : (
                            <>
                              <RichBlock base={m.id} text={m.content} />
                              {idx === messages.length - 1 && prev?.role === 'user' && toolActivity && (
                                <span className="ws-msg__tool">
                                  <Wand2 size={11} />
                                  {toolActivity.tool}
                                </span>
                              )}
                            </>
                          )}
                        </>
                      )}
                      {isUser && (
                        <MessageActions copied={false} onCopy={() => copy(m.content)} onEdit={() => setEdited({ id: m.id, text: m.content })} />
                      )}
                    </div>
                  </div>
                </div>
              )
            })}

            {streamingPartial && (
              <div className="ws-msg ws-msg--assistant">
                <div className="ws-msg__row">
                  <span className="ws-msg__avatar">S</span>
                  <div className="ws-msg__body">
                    <RichBlock base="stream" text={streamingPartial} />
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="ws-msg ws-msg--assistant">
                <div className="ws-msg__row">
                  <span className="ws-msg__avatar">!</span>
                  <div className="ws-msg__body">
                    <div className="ws-msg__error">
                      <b>Something went wrong.</b> Salaar couldn’t complete that request.
                      <div className="ws-msg__error-actions">
                        <button onClick={onRetry}><RefreshCw size={11} /> Retry</button>
                        <button onClick={onNewChat}>New conversation</button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={endRef} />
          </div>
        )}
      </div>
      <div className="ws-chat__composer">
        <Composer
          compact
          onSend={onSend}
          busy={busy}
          onStop={onStop}
          placeholder={busy ? 'Salaar is responding…' : 'Ask Salaar anything…'}
        />
      </div>
    </div>
  )
}