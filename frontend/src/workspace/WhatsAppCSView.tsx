import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Bot, CheckCircle, Headset, Loader2, Plus, RefreshCw, Send, Trash2, UserCheck } from 'lucide-react'
import { SalarApi } from '../api'
import type {
  WhatsAppCsAiSettings,
  WhatsAppCsConnection,
  WhatsAppCsConversation,
  WhatsAppCsKnowledgeEntry,
  WhatsAppCsMessage,
  WhatsAppCsOverview,
} from '../api'

type Tab = 'overview' | 'inbox' | 'knowledge' | 'connection'

const CATEGORIES = [
  'company', 'product', 'faq', 'pricing', 'shipping', 'returns',
  'booking', 'troubleshooting', 'sales', 'policy', 'other',
]

const CARD: React.CSSProperties = {
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: 12,
  padding: 14,
  background: 'rgba(255,255,255,0.02)',
}

const INPUT: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  borderRadius: 8,
  border: '1px solid rgba(255,255,255,0.12)',
  background: 'rgba(0,0,0,0.25)',
  color: 'inherit',
  fontSize: 13,
}

const BUTTON: React.CSSProperties = {
  padding: '7px 12px',
  borderRadius: 8,
  border: '1px solid rgba(255,255,255,0.14)',
  background: 'rgba(123,124,246,0.16)',
  color: 'inherit',
  fontSize: 12,
  cursor: 'pointer',
}

const MUTED: React.CSSProperties = { opacity: 0.65, fontSize: 12 }

function formatTime(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString()
}

function statusColor(status: string): string {
  if (status === 'verified') return '#4ade80'
  if (status === 'failed') return '#f87171'
  if (status === 'incomplete') return '#fbbf24'
  return 'rgba(255,255,255,0.5)'
}

function StatusPill({ label, tone }: { label: string; tone: string }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 8px',
      borderRadius: 999, fontSize: 11, border: `1px solid ${tone}`, color: tone,
    }}>
      {label}
    </span>
  )
}

function Metric({ label, value, hint }: { label: string; value: number | string; hint?: string }) {
  return (
    <div style={{ ...CARD, minWidth: 140, flex: '1 1 140px' }}>
      <div style={{ fontSize: 24, fontWeight: 650 }}>{value}</div>
      <div style={{ fontSize: 12, opacity: 0.8 }}>{label}</div>
      {hint ? <div style={MUTED}>{hint}</div> : null}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

function OverviewTab({ api, onOpenConversation }: { api: SalarApi; onOpenConversation: (id: string) => void }) {
  const [data, setData] = useState<WhatsAppCsOverview | null>(null)
  const [connection, setConnection] = useState<WhatsAppCsConnection | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [overview, conn] = await Promise.all([
        api.whatsappCsOverview(),
        api.whatsappCsConnectionGet().catch(() => null),
      ])
      setData(overview)
      setConnection(conn)
    } catch (e) {
      setError((e as Error).message || 'Could not load WhatsApp overview')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { void load() }, [load])

  if (loading) return <div style={MUTED}><Loader2 size={14} /> Loading overview…</div>
  if (error) return <div style={{ color: '#f87171' }}>{error}</div>
  if (!data) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {connection && connection.status !== 'verified' ? (
        <div style={{ ...CARD, borderColor: 'rgba(251,191,36,0.4)', color: '#fbbf24' }}>
          <AlertTriangle size={14} /> Configuration incomplete — set the WhatsApp Cloud API credentials in the
          server environment (see the Connection tab). No live messaging will occur until verified.
        </div>
      ) : null}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        <Metric label="Active conversations" value={data.active_conversations} />
        <Metric label="AI-handled" value={data.ai_handled} />
        <Metric label="Human-handled" value={data.human_handled} />
        <Metric label="Unresolved" value={data.unresolved} />
        <Metric label="Resolved" value={data.resolved} />
        <Metric label="New leads (7d)" value={data.new_leads_7d} />
      </div>

      <div style={CARD}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <strong style={{ fontSize: 13 }}>Delivery status</strong>
          <button style={BUTTON} onClick={() => { void load() }}><RefreshCw size={12} /> Refresh</button>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
          {Object.entries(data.delivery).map(([key, value]) => (
            <div key={key} style={{ fontSize: 12 }}>
              <div style={{ fontSize: 18, fontWeight: 600 }}>{value}</div>
              <div style={{ opacity: 0.7 }}>{key.replace('_', ' ')}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={CARD}>
        <strong style={{ fontSize: 13 }}>Recent activity</strong>
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.recent_activity.length === 0 ? <div style={MUTED}>No messages yet.</div> : null}
          {data.recent_activity.map((item) => (
            <button
              key={item.message.id}
              onClick={() => onOpenConversation(item.conversation_id)}
              style={{
                display: 'flex', gap: 8, alignItems: 'baseline', textAlign: 'left',
                background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', padding: '4px 0',
              }}
            >
              <StatusPill
                label={item.message.direction === 'incoming' ? 'in' : 'out'}
                tone={item.message.direction === 'incoming' ? '#60a5fa' : '#4ade80'}
              />
              <span style={{ fontWeight: 600 }}>{item.customer_name || 'Unknown'}</span>
              <span style={{ ...MUTED, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {item.message.body}
              </span>
              <span style={MUTED}>{formatTime(item.message.created_at)}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inbox
// ---------------------------------------------------------------------------

function MessageBubble({ message }: { message: WhatsAppCsMessage }) {
  const incoming = message.direction === 'incoming'
  return (
    <div style={{ display: 'flex', justifyContent: incoming ? 'flex-start' : 'flex-end' }}>
      <div style={{
        maxWidth: '78%', padding: '8px 10px', borderRadius: 10, fontSize: 13,
        background: incoming ? 'rgba(96,165,250,0.14)' : 'rgba(74,222,128,0.14)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div>{message.body || `[${message.type}]`}</div>
        <div style={{ ...MUTED, marginTop: 4, fontSize: 10 }}>
          {message.delivery_status}{message.delivery_status ? ' · ' : ''}{formatTime(message.created_at)}
        </div>
      </div>
    </div>
  )
}

function InboxTab({ api, selectedId, onSelect }: { api: SalarApi; selectedId: string | null; onSelect: (id: string | null) => void }) {
  const [items, setItems] = useState<WhatsAppCsConversation[]>([])
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState('')
  const [search, setSearch] = useState('')
  const [detail, setDetail] = useState<{ conversation: WhatsAppCsConversation; messages: WhatsAppCsMessage[] } | null>(null)
  const [reply, setReply] = useState('')
  const [repEmail, setRepEmail] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const loadList = useCallback(async () => {
    try {
      const data = await api.whatsappCsConversations({ status: statusFilter || undefined, search: search || undefined, limit: 50 })
      setItems(data.items)
      setTotal(data.total)
    } catch (e) {
      setError((e as Error).message || 'Could not load conversations')
    }
  }, [api, statusFilter, search])

  const loadDetail = useCallback(async (id: string) => {
    try {
      setDetail(await api.whatsappCsConversation(id))
      setError('')
    } catch (e) {
      setError((e as Error).message || 'Could not load conversation')
    }
  }, [api])

  useEffect(() => { void loadList() }, [loadList])
  useEffect(() => {
    if (selectedId) void loadDetail(selectedId)
    else setDetail(null)
  }, [selectedId, loadDetail])

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true)
    setError('')
    try {
      await action()
      if (selectedId) await loadDetail(selectedId)
      await loadList()
    } catch (e) {
      setError((e as Error).message || 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  const sendReply = async () => {
    if (!selectedId || !reply.trim()) return
    const text = reply.trim()
    setReply('')
    await run(() => api.whatsappCsReply(selectedId, text))
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(220px, 320px) 1fr', gap: 14, alignItems: 'start' }}>
      <div style={CARD}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
          <input
            style={INPUT}
            placeholder="Search name or number"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') void loadList() }}
          />
          <select style={{ ...INPUT, width: 'auto' }} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All</option>
            <option value="open">Open</option>
            <option value="human">Human</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>
        <div style={{ ...MUTED, marginBottom: 6 }}>{total} conversation{total === 1 ? '' : 's'}</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 460, overflowY: 'auto' }}>
          {items.map((c) => (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              style={{
                textAlign: 'left', padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
                border: `1px solid ${c.id === selectedId ? 'rgba(123,124,246,0.6)' : 'transparent'}`,
                background: c.id === selectedId ? 'rgba(123,124,246,0.12)' : 'transparent', color: 'inherit',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6 }}>
                <strong style={{ fontSize: 13 }}>{c.customer.profile_name || c.customer.wa_id}</strong>
                <StatusPill label={c.handling_mode === 'human' ? 'human' : 'ai'} tone={c.handling_mode === 'human' ? '#fbbf24' : '#4ade80'} />
              </div>
              <div style={MUTED}>{c.status} · {formatTime(c.last_message_at)}</div>
            </button>
          ))}
          {items.length === 0 ? <div style={MUTED}>No conversations.</div> : null}
        </div>
      </div>

      <div style={CARD}>
        {error ? <div style={{ color: '#f87171', marginBottom: 8 }}>{error}</div> : null}
        {!detail ? (
          <div style={MUTED}>Select a conversation to view the thread.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
              <div>
                <strong>{detail.conversation.customer.profile_name || detail.conversation.customer.wa_id}</strong>
                <div style={MUTED}>
                  {detail.conversation.customer.wa_id} · {detail.conversation.status}
                  {detail.conversation.assigned_rep_name ? ` · ${detail.conversation.assigned_rep_name}` : ''}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button style={BUTTON} disabled={busy} onClick={() => void run(() => api.whatsappCsResumeAi(detail.conversation.id))}>
                  <Bot size={12} /> Resume AI
                </button>
                <button style={BUTTON} disabled={busy} onClick={() => void run(() => api.whatsappCsResolve(detail.conversation.id))}>
                  <CheckCircle size={12} /> Resolve
                </button>
                <button style={BUTTON} disabled={busy} onClick={() => void run(() => api.whatsappCsReopen(detail.conversation.id))}>
                  Reopen
                </button>
              </div>
            </div>

            {detail.conversation.escalation_reason ? (
              <div style={{ ...MUTED, color: '#fbbf24' }}>Escalated: {detail.conversation.escalation_reason}</div>
            ) : null}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 360, overflowY: 'auto', padding: '4px 0' }}>
              {detail.messages.map((m) => <MessageBubble key={m.id} message={m} />)}
              {detail.messages.length === 0 ? <div style={MUTED}>No messages.</div> : null}
            </div>

            <div style={{ display: 'flex', gap: 6 }}>
              <input
                style={INPUT}
                placeholder="Reply as a human representative…"
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') void sendReply() }}
              />
              <button style={BUTTON} disabled={busy || !reply.trim()} onClick={() => void sendReply()}>
                <Send size={12} /> Send
              </button>
            </div>

            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input style={INPUT} placeholder="Assign to rep email" value={repEmail} onChange={(e) => setRepEmail(e.target.value)} />
              <button
                style={BUTTON}
                disabled={busy || !repEmail.trim()}
                onClick={() => void run(() => api.whatsappCsAssign(detail.conversation.id, repEmail.trim()))}
              >
                <UserCheck size={12} /> Assign
              </button>
              <button style={BUTTON} disabled={busy} onClick={() => void run(() => api.whatsappCsUnassign(detail.conversation.id))}>
                Unassign
              </button>
            </div>

            <div style={{ display: 'flex', gap: 6 }}>
              <input style={INPUT} placeholder="Internal note (not sent to customer)" value={note} onChange={(e) => setNote(e.target.value)} />
              <button
                style={BUTTON}
                disabled={busy || !note.trim()}
                onClick={() => {
                  const text = note.trim()
                  setNote('')
                  void run(() => api.whatsappCsNotes(detail.conversation.id, text))
                }}
              >
                <Plus size={12} /> Note
              </button>
            </div>
            {detail.conversation.notes ? (
              <pre style={{ ...MUTED, whiteSpace: 'pre-wrap', margin: 0, maxHeight: 120, overflowY: 'auto' }}>
                {detail.conversation.notes}
              </pre>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Knowledge base
// ---------------------------------------------------------------------------

function KnowledgeTab({ api }: { api: SalarApi }) {
  const [items, setItems] = useState<WhatsAppCsKnowledgeEntry[]>([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState({ category: 'faq', title: '', body: '', tags: '' })

  const load = useCallback(async () => {
    try {
      const data = await api.whatsappCsKnowledge({ search: search || undefined })
      setItems(data.items)
      setError('')
    } catch (e) {
      setError((e as Error).message || 'Could not load knowledge base')
    }
  }, [api, search])

  useEffect(() => { void load() }, [load])

  const reset = () => {
    setEditingId(null)
    setForm({ category: 'faq', title: '', body: '', tags: '' })
  }

  const save = async () => {
    if (!form.title.trim() || !form.body.trim()) return
    setBusy(true)
    setError('')
    try {
      if (editingId) await api.whatsappCsKnowledgeUpdate(editingId, form)
      else await api.whatsappCsKnowledgeCreate(form)
      reset()
      await load()
    } catch (e) {
      setError((e as Error).message || 'Could not save entry')
    } finally {
      setBusy(false)
    }
  }

  const act = async (action: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await action()
      await load()
    } catch (e) {
      setError((e as Error).message || 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr minmax(260px, 360px)', gap: 14, alignItems: 'start' }}>
      <div style={CARD}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
          <input style={INPUT} placeholder="Search knowledge…" value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void load() }} />
          <button style={BUTTON} onClick={() => void load()}><RefreshCw size={12} /></button>
        </div>
        {error ? <div style={{ color: '#f87171', marginBottom: 8 }}>{error}</div> : null}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 520, overflowY: 'auto' }}>
          {items.map((entry) => (
            <div key={entry.id} style={{ border: '1px solid rgba(255,255,255,0.07)', borderRadius: 8, padding: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <strong style={{ fontSize: 13 }}>{entry.title}</strong>
                <StatusPill label={entry.is_active ? 'active' : 'inactive'} tone={entry.is_active ? '#4ade80' : 'rgba(255,255,255,0.5)'} />
              </div>
              <div style={MUTED}>{entry.category}{entry.tags ? ` · ${entry.tags}` : ''}</div>
              <div style={{ fontSize: 12, margin: '6px 0', whiteSpace: 'pre-wrap' }}>{entry.body}</div>
              <div style={{ display: 'flex', gap: 6 }}>
                <button style={BUTTON} disabled={busy} onClick={() => { setEditingId(entry.id); setForm({ category: entry.category, title: entry.title, body: entry.body, tags: entry.tags }) }}>
                  Edit
                </button>
                <button style={BUTTON} disabled={busy} onClick={() => void act(() => api.whatsappCsKnowledgeToggle(entry.id))}>
                  {entry.is_active ? 'Deactivate' : 'Activate'}
                </button>
                <button style={BUTTON} disabled={busy} onClick={() => void act(() => api.whatsappCsKnowledgeDelete(entry.id))}>
                  <Trash2 size={12} /> Delete
                </button>
              </div>
            </div>
          ))}
          {items.length === 0 ? <div style={MUTED}>No knowledge entries yet. Add company, product, FAQ, shipping, returns, booking, troubleshooting and sales information so the AI answers only from verified facts.</div> : null}
        </div>
      </div>

      <div style={CARD}>
        <strong style={{ fontSize: 13 }}>{editingId ? 'Edit entry' : 'Add entry'}</strong>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
          <select style={INPUT} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input style={INPUT} placeholder="Title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <textarea style={{ ...INPUT, minHeight: 120 }} placeholder="Verified answer / policy text" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
          <input style={INPUT} placeholder="Tags (comma separated)" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
          <div style={{ display: 'flex', gap: 6 }}>
            <button style={BUTTON} disabled={busy || !form.title.trim() || !form.body.trim()} onClick={() => void save()}>
              {editingId ? 'Save changes' : 'Add entry'}
            </button>
            {editingId ? <button style={BUTTON} onClick={reset}>Cancel</button> : null}
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Connection + AI settings
// ---------------------------------------------------------------------------

function ConnectionTab({ api }: { api: SalarApi }) {
  const [connection, setConnection] = useState<WhatsAppCsConnection | null>(null)
  const [ai, setAi] = useState<WhatsAppCsAiSettings | null>(null)
  const [form, setForm] = useState({ phone_number_id: '', business_account_id: '', display_name: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [conn, settings] = await Promise.all([api.whatsappCsConnectionGet(), api.whatsappCsAiSettingsGet()])
      setConnection(conn)
      setAi(settings)
      setForm({
        phone_number_id: conn.phone_number_id,
        business_account_id: conn.business_account_id,
        display_name: conn.display_name,
      })
      setError('')
    } catch (e) {
      setError((e as Error).message || 'Could not load connection settings')
    }
  }, [api])

  useEffect(() => { void load() }, [load])

  const saveConnection = async () => {
    setBusy(true)
    try {
      const conn = await api.whatsappCsConnectionUpdate(form)
      setConnection(conn)
      setError('')
    } catch (e) {
      setError((e as Error).message || 'Could not update connection')
    } finally {
      setBusy(false)
    }
  }

  const saveAi = async (patch: Partial<WhatsAppCsAiSettings>) => {
    setBusy(true)
    try {
      setAi(await api.whatsappCsAiSettingsSet(patch))
    } catch (e) {
      setError((e as Error).message || 'Could not update AI settings')
    } finally {
      setBusy(false)
    }
  }

  if (!connection || !ai) {
    return error ? <div style={{ color: '#f87171' }}>{error}</div> : <div style={MUTED}>Loading…</div>
  }

  const flag = (ok: boolean) => ok ? <StatusPill label="set" tone="#4ade80" /> : <StatusPill label="missing" tone="#f87171" />

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {error ? <div style={{ color: '#f87171' }}>{error}</div> : null}

      <div style={CARD}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong style={{ fontSize: 13 }}>Meta WhatsApp Cloud API connection</strong>
          <StatusPill label={connection.status.replace('_', ' ')} tone={statusColor(connection.status)} />
        </div>
        <div style={{ ...MUTED, marginTop: 6 }}>
          Webhook URL: <code>/api/whatsapp-cs/webhook</code> · Graph API {connection.api_version}
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', margin: '10px 0' }}>
          <div style={{ fontSize: 12 }}>Access token {flag(connection.has_access_token)}</div>
          <div style={{ fontSize: 12 }}>App secret {flag(connection.has_app_secret)}</div>
          <div style={{ fontSize: 12 }}>Verify token {flag(connection.has_verify_token)}</div>
          <div style={{ fontSize: 12 }}>Feature flag {flag(connection.enabled)}</div>
        </div>
        <div style={{ ...MUTED, marginBottom: 8 }}>
          Credentials are stored only in server environment variables (never in the database or the browser).
          {connection.last_error ? ` Last error: ${connection.last_error}` : ''}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
          <input style={INPUT} placeholder="Phone number ID" value={form.phone_number_id} onChange={(e) => setForm({ ...form, phone_number_id: e.target.value })} />
          <input style={INPUT} placeholder="Business account ID" value={form.business_account_id} onChange={(e) => setForm({ ...form, business_account_id: e.target.value })} />
          <input style={INPUT} placeholder="Display name" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
        </div>
        <button style={{ ...BUTTON, marginTop: 8 }} disabled={busy} onClick={() => void saveConnection()}>
          <Headset size={12} /> Save connection metadata
        </button>
      </div>

      <div style={CARD}>
        <strong style={{ fontSize: 13 }}>AI agent</strong>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
          <label style={{ fontSize: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="checkbox" checked={ai.enabled} disabled={busy} onChange={(e) => void saveAi({ enabled: e.target.checked })} />
            Automatic AI replies enabled
          </label>
          <label style={{ fontSize: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="checkbox" checked={ai.sensitive_escalation} disabled={busy} onChange={(e) => void saveAi({ sensitive_escalation: e.target.checked })} />
            Escalate refunds / legal / complaint topics to a human
          </label>
          <label style={{ fontSize: 12 }}>Model
            <input style={INPUT} value={ai.model} disabled={busy} onChange={(e) => setAi({ ...ai, model: e.target.value })} onBlur={() => void saveAi({ model: ai.model })} />
          </label>
          <label style={{ fontSize: 12 }}>Max reply length (characters)
            <input
              style={INPUT}
              type="number"
              min={60}
              max={2000}
              value={ai.max_response_length}
              disabled={busy}
              onChange={(e) => setAi({ ...ai, max_response_length: Number(e.target.value) })}
              onBlur={() => void saveAi({ max_response_length: ai.max_response_length })}
            />
          </label>
          <label style={{ fontSize: 12 }}>Fallback message
            <textarea
              style={{ ...INPUT, minHeight: 70 }}
              value={ai.fallback}
              disabled={busy}
              onChange={(e) => setAi({ ...ai, fallback: e.target.value })}
              onBlur={() => void saveAi({ fallback: ai.fallback })}
            />
          </label>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'inbox', label: 'Inbox' },
  { id: 'knowledge', label: 'Knowledge' },
  { id: 'connection', label: 'Connection' },
]

export default function WhatsAppCSView({ api }: { api: SalarApi }) {
  const [tab, setTab] = useState<Tab>('overview')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const openConversation = (id: string) => {
    setSelectedId(id)
    setTab('inbox')
  }

  return (
    <div className="ws-scroll" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 650, letterSpacing: '-0.01em' }}>WhatsApp Customer Service</h2>
          <div style={MUTED}>Official Meta WhatsApp Business Platform · AI agent with human handover</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              style={{
                ...BUTTON,
                background: tab === t.id ? 'rgba(123,124,246,0.28)' : 'transparent',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'overview' ? <OverviewTab api={api} onOpenConversation={openConversation} /> : null}
      {tab === 'inbox' ? <InboxTab api={api} selectedId={selectedId} onSelect={setSelectedId} /> : null}
      {tab === 'knowledge' ? <KnowledgeTab api={api} /> : null}
      {tab === 'connection' ? <ConnectionTab api={api} /> : null}
    </div>
  )
}