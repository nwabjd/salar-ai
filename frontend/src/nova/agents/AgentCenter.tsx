import React, { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Bot, Layers, Network, Activity, Send, Users, ShieldCheck } from 'lucide-react'

/* ============================================================
   MULTI-AGENT COORDINATION (Phase 7)
   AgentCenter: overview of the agent swarm.
   - Roster of specialist agents with capability + state
   - Live swarm (from /api/core/status)
   - Delegation console for dispatching tasks
   ============================================================ */

export interface AgentRole {
  id: string
  name: string
  specialty: string
  capability: string
  state: 'active' | 'waiting' | 'working'
  load: number
}

export const AGENT_ROSTER: AgentRole[] = [
  { id: 'architect', name: 'Architect', specialty: 'Planning', capability: 'Breaks goals into verifiable steps', state: 'active', load: 32 },
  { id: 'researcher', name: 'Researcher', specialty: 'Knowledge', capability: 'Gathers and synthesizes sources', state: 'active', load: 12 },
  { id: 'engineer', name: 'Engineer', specialty: 'Execution', capability: 'Runs tools and takes actions', state: 'working', load: 64 },
  { id: 'qa', name: 'QA', specialty: 'Verification', capability: 'Checks outcomes against claims', state: 'waiting', load: 0 },
  { id: 'automation', name: 'Automation', specialty: 'Devices', capability: 'Commands your connected devices', state: 'waiting', load: 0 },
]

interface AgentCenterProps {
  api: any
}

export default function AgentCenter({ api }: AgentCenterProps) {
  const [live, setLive] = useState<{ id: string; kind: string; status: string }[]>([])
  const [busEvents, setBusEvents] = useState(0)
  const [alerts, setAlerts] = useState<any[]>([])
  const [taskInput, setTaskInput] = useState('')
  const [delegating, setDelegating] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const status = await api.coreStatus()
      setLive(status.live_agents || [])
      setBusEvents(status.bus_events_count ?? 0)
      setAlerts(status.alerts || [])
    } catch { /* core offline */ }
  }, [api])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 5000)
    return () => clearInterval(t)
  }, [refresh])

  const delegate = async () => {
    const request = taskInput.trim()
    if (!request) return
    setDelegating(true)
    setError('')
    setResult(null)
    try {
      const r = await api.coreRun(request)
      setResult(r)
      setTaskInput('')
      refresh()
    } catch (e) {
      setError('Delegation failed — the core pipeline may be offline.')
    } finally {
      setDelegating(false)
    }
  }

  const activeCount = AGENT_ROSTER.filter(a => a.state !== 'waiting').length

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      style={{ flex: 1, overflowY: 'auto', padding: 'clamp(24px, 5vh, 48px) clamp(24px, 4vw, 64px)' }}
    >
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div className="nova-meta" style={{ color: 'var(--nova-violet)', marginBottom: 6 }}>ORCHESTRATION LAYER</div>
        <h1 style={{ margin: 0, fontSize: 'clamp(26px, 3.4vw, 38px)', fontWeight: 300, letterSpacing: '-0.03em', color: 'var(--nova-white)' }}>
          Agent Swarm
        </h1>
        <p style={{ margin: '8px 0 0', fontSize: 13, color: 'var(--nova-lunar)' }}>
          Salaar delegates work to specialist agents, tracks each run, and verifies outcomes before reporting back.
        </p>
      </div>

      {/* Metric strip */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 22, flexWrap: 'wrap' }}>
        {[
          { label: 'AGENTS ONLINE', value: `${activeCount}/${AGENT_ROSTER.length}`, color: 'var(--nova-mint)' },
          { label: 'LIVE RUNS', value: live.length, color: 'var(--nova-cyan)' },
          { label: 'EVENTS ON BUS', value: busEvents, color: 'var(--nova-violet)' },
          { label: 'ACTIVE ALERTS', value: alerts.length, color: alerts.length ? 'var(--nova-amber)' : 'var(--nova-lunar)' },
        ].map(m => (
          <div key={m.label} className="nova-glass" style={{ flex: '1 1 140px', padding: '14px 18px', borderRadius: 14 }}>
            <div style={{ fontSize: 22, fontWeight: 500, color: m.color, marginBottom: 3 }}>{m.value}</div>
            <div className="nova-meta" style={{ color: 'var(--nova-lunar)' }}>{m.label}</div>
          </div>
        ))}
      </div>

      {/* Roster */}
      <div className="nova-meta" style={{ marginBottom: 10 }}>SPECIALIST AGENTS</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
        {AGENT_ROSTER.map((a, i) => (
          <motion.div
            key={a.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.05 }}
            className="nova-glass"
            style={{ padding: '16px 18px', borderRadius: 16, display: 'flex', flexDirection: 'column', gap: 8 }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{
                width: 38, height: 38, borderRadius: 12, display: 'grid', placeItems: 'center',
                background: a.state === 'working'
                  ? 'linear-gradient(135deg, rgba(96,239,255,.16), rgba(168,121,255,.16))'
                  : 'rgba(255,255,255,.04)',
                border: a.state === 'working' ? '1px solid var(--nova-line-cyan)' : '1px solid var(--nova-line)',
                color: a.state === 'working' ? 'var(--nova-cyan)' : 'var(--nova-lunar)',
              }}>
                <Bot size={17}/>
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--nova-white)' }}>{a.name}</div>
                <div style={{ fontSize: 10.5, color: 'var(--nova-violet)', letterSpacing: '.06em', textTransform: 'uppercase' }}>{a.specialty}</div>
              </div>
              <span style={{
                width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                background: a.state === 'working' ? 'var(--nova-cyan)' : a.state === 'active' ? 'var(--nova-mint)' : 'var(--nova-amber)',
                boxShadow: a.state === 'working' ? 'var(--nova-glow-cyan)' : a.state === 'active' ? '0 0 6px rgba(120,244,197,.6)' : undefined,
              }}/>
            </div>
            <div style={{ fontSize: 11, color: 'var(--nova-lunar)', lineHeight: 1.5 }}>{a.capability}</div>
            <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,.06)', overflow: 'hidden' }}>
              <div style={{
                width: `${a.load}%`, height: '100%', borderRadius: 2,
                background: a.load > 50 ? 'var(--nova-cyan)' : 'var(--nova-violet)',
              }}/>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Live swarm */}
      {live.length > 0 && (
        <>
          <div className="nova-meta" style={{ margin: '22px 0 10px', color: 'var(--nova-cyan)' }}>LIVE SWARM</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {live.map(r => (
              <div key={r.id} className="nova-intel-glass" style={{ padding: '12px 16px', borderRadius: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--nova-cyan)', boxShadow: 'var(--nova-glow-cyan)' }}/>
                <span style={{ fontSize: 12, color: 'var(--nova-white)' }}>Run {r.id.slice(0, 8)}</span>
                <span style={{ fontSize: 11, color: 'var(--nova-lunar)' }}>agent: {r.kind}</span>
                <span style={{ fontSize: 10, letterSpacing: '.08em', color: 'var(--nova-cyan)', marginLeft: 'auto' }}>
                  <Activity size={11} style={{ verticalAlign: -1 }}/> {r.status.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Alerts */}
      {alerts.length > 0 && (
        <div style={{ marginTop: 22 }}>
          <div className="nova-meta" style={{ marginBottom: 8, color: 'var(--nova-amber)' }}>SUPERVISOR ALERTS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {alerts.map((a, i) => (
              <div key={i} style={{
                padding: '11px 14px', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 9,
                background: 'rgba(255,204,117,.05)', border: '1px solid rgba(255,204,117,.2)',
                fontSize: 11.5, color: 'var(--nova-amber)', lineHeight: 1.5,
              }}>
                <ShieldCheck size={14} style={{ flexShrink: 0 }}/> {a.message || JSON.stringify(a)}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Delegation console */}
      <div style={{ marginTop: 24 }}>
        <div className="nova-meta" style={{ marginBottom: 10 }}>DELEGATION CONSOLE</div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '12px 14px 12px 18px', borderRadius: 16,
          background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
          backdropFilter: 'blur(20px)',
        }}>
          <Layers size={16} style={{ color: 'var(--nova-violet)', flexShrink: 0 }}/>
          <input
            value={taskInput}
            onChange={e => setTaskInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') delegate() }}
            placeholder="Dispatch a task to the swarm — e.g. 'Research the best vector DBs and report'…"
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: 'var(--nova-white)', fontSize: 13.5,
            }}
          />
          <motion.button
            whileTap={{ scale: 0.93 }}
            onClick={delegate}
            disabled={delegating}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '9px 18px', borderRadius: 12,
              background: 'linear-gradient(135deg, rgba(96,239,255,.2), rgba(168,121,255,.2))',
              border: '1px solid var(--nova-line-cyan)', color: 'var(--nova-white)',
              cursor: delegating ? 'default' : 'pointer', fontSize: 12, fontWeight: 600,
              opacity: delegating ? 0.6 : 1,
            }}
          >
            <Users size={14}/> {delegating ? 'DISPATCHING…' : 'DELEGATE'}
          </motion.button>
        </div>

        {error && <div style={{ marginTop: 10, fontSize: 12, color: 'var(--nova-coral)' }}>{error}</div>}

        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="nova-intel-glass"
            style={{ marginTop: 12, padding: '16px 20px', borderRadius: 16 }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 8 }}>
              <Network size={15} style={{ color: 'var(--nova-cyan)' }}/>
              <span className="nova-meta" style={{ color: 'var(--nova-cyan)' }}>DISPATCH RESULT</span>
              <span style={{
                marginLeft: 'auto', fontSize: 10, letterSpacing: '.1em', padding: '4px 10px', borderRadius: 9,
                background: result.status === 'completed' ? 'rgba(120,244,197,.1)' : 'rgba(255,204,117,.1)',
                border: `1px solid ${result.status === 'completed' ? 'rgba(120,244,197,.3)' : 'rgba(255,204,117,.3)'}`,
                color: result.status === 'completed' ? 'var(--nova-mint)' : 'var(--nova-amber)',
              }}>
                {String(result.status).toUpperCase()}
              </span>
            </div>
            {result.requested && <div style={{ fontSize: 12.5, color: 'var(--nova-white)', marginBottom: 6 }}>{result.requested}</div>}
            {result.attempted && result.attempted.length > 0 && (
              <div style={{ fontSize: 11.5, color: 'var(--nova-lunar)', lineHeight: 1.6 }}>
                Planned steps: {result.attempted.join(' → ')}
              </div>
            )}
            {result.verified && result.verified.length > 0 && (
              <div style={{ fontSize: 11.5, color: 'var(--nova-mint)', marginTop: 4, lineHeight: 1.6 }}>
                Verified: {result.verified.join(' · ')}
              </div>
            )}
            <div style={{ fontSize: 11, color: 'var(--nova-violet)', marginTop: 6 }}>
              confidence {Math.round((result.confidence ?? 0) * 100)}% · trace {result.trace_id}
            </div>
          </motion.div>
        )}
      </div>
    </motion.div>
  )
}
