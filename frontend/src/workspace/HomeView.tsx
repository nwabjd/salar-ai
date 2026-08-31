import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Activity, ScanLine, Timer, TrendingUp } from 'lucide-react'
import { SalarApi } from '../api'
import Composer from './Composer'

const SUGGESTIONS = [
  'Summarize my week',
  'Plan my day',
  'Research a topic',
  'Write a report',
  'Debug this code',
  'Draft an email',
]

function greeting(): string {
  const h = new Date().getHours()
  if (h < 5) return 'Still up?'
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

function IntelCards({ api }: { api: SalarApi }) {
  const [data, setData] = useState<Record<string, ReactNode>>({})

  useEffect(() => {
    let stopped = false
    const load = async () => {
      try {
        const [usage, core, notif] = await Promise.all([
          api.usage().catch(() => null),
          api.coreStatus().catch(() => null),
          api.intelUnreadCount().catch(() => null),
        ])
        if (stopped) return
        setData({
          usage: usage
            ? <span>{usage.used.toLocaleString()} <small>/ {usage.limit === null ? '∞' : usage.limit.toLocaleString()}</small></span>
            : undefined,
          core: core
            ? <span>{core.live_agents?.length ?? 0} <small>live agents</small></span>
            : undefined,
          intel: notif && notif.unread_count > 0
            ? <span>{notif.unread_count} <small>new intel</small></span>
            : <span>0 <small>new intel</small></span>,
        })
      } catch { /* keep previous */ }
    }
    load()
    const timer = setInterval(load, 30000)
    return () => { stopped = true; clearInterval(timer) }
  }, [api])

  const cards = useMemo(() => [
    { label: 'Usage', value: data.usage, icon: <Activity size={14} /> },
    { label: 'Active cores', value: data.core, icon: <Timer size={14} /> },
    { label: 'Intel backlog', value: data.intel, icon: <TrendingUp size={14} /> },
  ], [data])

  return (
    <div className="ws-home__intel">
      {cards.map((c) => (
        <div key={c.label} className="ws-intel-card">
          <span className="ws-intel-card__icon">{c.icon}</span>
          <div>
            <b>{c.value ?? <span className="ws-intel-card__muted">—</span>}</b>
            <small>{c.label}</small>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function HomeView({ api, onSend, onStartChat }: { api: SalarApi; onSend: (text: string, files: File[]) => void; onStartChat: () => void }) {
  return (
    <div className="ws-scroll ws-home-center">
      <div className="ws-home">
        <span className="ws-home__eyebrow">SALAAR INTELLIGENCE</span>
        <h1 className="ws-home__title">{greeting()}. Your intelligent <em>workspace</em> is ready.</h1>
        <p className="ws-home__sub">Private, adaptive and always on. Ask Salaar anything — or hand it a project.</p>
        <IntelCards api={api} />
        <div className="ws-home__quick">
          {SUGGESTIONS.map((s) => (
            <button key={s} className="ws-quick" onClick={() => { onSend(s, []); onStartChat() }}>
              <ScanLine size={13} />
              {s}
            </button>
          ))}
        </div>
        <Composer onSend={(t, f) => { onSend(t, f); onStartChat() }} placeholder="Ask Salaar anything…" />
      </div>
    </div>
  )
}