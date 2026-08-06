import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from '../api'

interface Reminder {
  id: string
  title: string
  message?: string
  remind_at: string
  recurrence?: string
  is_done?: boolean
  notified?: boolean
  workspace_id?: string
}

interface Props {
  workspaceId: string | null
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  const now = Date.now()
  const diff = d.getTime() - now
  const absDiff = Math.abs(diff)
  const past = diff < 0
  if (absDiff < 3600000) { const m = Math.round(absDiff / 60000); return past ? `${m}m ago` : `in ${m}m` }
  if (absDiff < 86400000) { const h = Math.round(absDiff / 3600000); return past ? `${h}h ago` : `in ${h}h` }
  const days = Math.round(absDiff / 86400000)
  return past ? `${days}d ago` : `in ${days}d`
}

const recurrenceLabels: Record<string, string> = { daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly' }

const s = {
  panel: { display: 'flex', flexDirection: 'column' as const, gap: 12, height: '100%' },
  form: { display: 'flex', flexDirection: 'column' as const, gap: 8, padding: 12, border: '1px solid var(--line, #2a2a2a)', borderRadius: 10, background: 'rgba(0,0,0,.12)' },
  row: { display: 'flex', gap: 8, alignItems: 'center' },
  input: { flex: 1, padding: '6px 10px', border: '1px solid var(--line, #2a2a2a)', borderRadius: 8, background: 'rgba(0,0,0,.18)', color: 'var(--ink, #e0e0e0)', fontSize: 10 },
  select: { padding: '6px 8px', border: '1px solid var(--line, #2a2a2a)', borderRadius: 8, background: 'rgba(0,0,0,.18)', color: 'var(--ink, #e0e0e0)', fontSize: 10 },
  btn: { padding: '6px 14px', border: 0, borderRadius: 8, background: '#5227FF', color: '#fff', fontSize: 9, cursor: 'pointer' as const },
  btnDone: { padding: '4px 10px', border: '1px solid rgba(112,229,170,.3)', borderRadius: 6, background: 'rgba(112,229,170,.1)', color: '#70e5aa', fontSize: 9, cursor: 'pointer' as const },
  btnDel: { padding: '4px 10px', border: '1px solid rgba(239,68,68,.3)', borderRadius: 6, background: 'rgba(239,68,68,.1)', color: '#ef4444', fontSize: 9, cursor: 'pointer' as const },
  card: { padding: 10, borderRadius: 8, border: '1px solid var(--line, #2a2a2a)', background: 'rgba(255,255,255,.02)' },
  cardOverdue: { padding: 10, borderRadius: 8, border: '1px solid rgba(255,68,68,.4)', borderLeftWidth: 3, background: 'rgba(255,68,68,.06)' },
  title: { fontSize: 12, fontWeight: 600, color: '#e0e0e0' },
  titleDone: { fontSize: 12, fontWeight: 600, color: '#666', textDecoration: 'line-through' as const },
  msg: { fontSize: 10, color: '#999', marginTop: 4 },
  meta: { display: 'flex', alignItems: 'center', gap: 6, marginTop: 6, flexWrap: 'wrap' as const },
  badge: { fontSize: 8, padding: '2px 6px', borderRadius: 4, background: 'rgba(82,39,255,.15)', color: '#7c5cff', fontWeight: 600 },
  badgeOverdue: { fontSize: 8, padding: '2px 6px', borderRadius: 4, background: 'rgba(255,68,68,.15)', color: '#ff6666', fontWeight: 600 },
  time: { fontSize: 10, color: '#777' },
  section: { fontSize: 9, color: 'var(--muted, #888)', letterSpacing: '.1em', textTransform: 'uppercase' as const, marginTop: 8 },
  empty: { textAlign: 'center' as const, color: '#555', fontSize: 12, padding: 24 },
  toggle: { background: 'none', border: 'none', color: '#666', fontSize: 11, cursor: 'pointer', padding: '4px 0' },
}

export function ReminderPanel({ workspaceId }: Props) {
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [overdue, setOverdue] = useState<Reminder[]>([])
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [message, setMessage] = useState('')
  const [remindAt, setRemindAt] = useState('')
  const [recurrence, setRecurrence] = useState('none')
  const [busy, setBusy] = useState(false)
  const [showDone, setShowDone] = useState(false)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const [all, od] = await Promise.all([api.reminders({ upcoming_only: false, limit: 200 }), api.overdueReminders()])
      setReminders(Array.isArray(all) ? all : [])
      setOverdue(Array.isArray(od) ? od : [])
    } catch { setReminders([]); setOverdue([]) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const overdueIds = useMemo(() => new Set(overdue.map(r => r.id)), [overdue])
  const { active, completed } = useMemo(() => {
    const a: Reminder[] = [], c: Reminder[] = []
    for (const r of reminders) { if (r.is_done) c.push(r); else a.push(r) }
    a.sort((x, y) => new Date(x.remind_at).getTime() - new Date(y.remind_at).getTime())
    return { active: a, completed: c }
  }, [reminders])

  async function create(e: React.FormEvent) {
    e.preventDefault()
    if (!title.trim() || !remindAt) return
    setBusy(true)
    try {
      await api.createReminder({ title: title.trim(), message: message.trim() || undefined, remind_at: new Date(remindAt).toISOString(), recurrence: recurrence === 'none' ? undefined : recurrence })
      setTitle(''); setMessage(''); setRemindAt(''); setRecurrence('none')
      await load()
    } finally { setBusy(false) }
  }

  async function done(id: string) { await api.markReminderDone(id); await load() }
  async function del(id: string) { await api.deleteReminder(id); await load() }

  function Card({ r }: { r: Reminder }) {
    const od = overdueIds.has(r.id) && !r.is_done
    return (
      <div style={od ? s.cardOverdue : s.card}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={r.is_done ? s.titleDone : s.title}>{r.title}</div>
            {r.message && <div style={s.msg}>{r.message}</div>}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {!r.is_done && <button style={s.btnDone} onClick={() => done(r.id)}>Done</button>}
            <button style={s.btnDel} onClick={() => del(r.id)}>Del</button>
          </div>
        </div>
        <div style={s.meta}>
          <span style={{ ...s.time, color: od ? '#ff6666' : '#777' }}>{formatTime(r.remind_at)}</span>
          {r.recurrence && r.recurrence !== 'none' && <span style={s.badge}>{recurrenceLabels[r.recurrence] || r.recurrence}</span>}
          {od && <span style={s.badgeOverdue}>Overdue</span>}
        </div>
      </div>
    )
  }

  return (
    <div style={s.panel}>
      <form onSubmit={create} style={s.form}>
        <div style={s.row}>
          <input style={{ ...s.input, flex: 2 }} placeholder="Reminder title" value={title} onChange={e => setTitle(e.target.value)} required/>
          <input style={{ ...s.input, flex: 1 }} type="datetime-local" value={remindAt} onChange={e => setRemindAt(e.target.value)} required/>
        </div>
        <div style={s.row}>
          <input style={{ ...s.input, flex: 1 }} placeholder="Message (optional)" value={message} onChange={e => setMessage(e.target.value)}/>
          <select style={s.select} value={recurrence} onChange={e => setRecurrence(e.target.value)}>
            <option value="none">No repeat</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option>
          </select>
          <button style={s.btn} type="submit" disabled={busy || !title.trim() || !remindAt}>{busy ? '...' : 'Add'}</button>
        </div>
      </form>
      {loading ? <div style={s.empty}>Loading…</div> : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto', flex: 1 }}>
          {!active.length && !completed.length && <div style={s.empty}>No reminders yet</div>}
          {active.length > 0 && <><div style={s.section}>Active ({active.length})</div>{active.map(r => <Card key={r.id} r={r}/>)}</>}
          {completed.length > 0 && (
            <div style={{ borderTop: '1px solid var(--line, #2a2a2a)', paddingTop: 8 }}>
              <button style={s.toggle} onClick={() => setShowDone(!showDone)}><span style={{ fontSize: 9 }}>{showDone ? '▾' : '▸'}</span> Completed ({completed.length})</button>
              {showDone && <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>{completed.map(r => <Card key={r.id} r={r}/>)}</div>}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
