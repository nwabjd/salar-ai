import React, { useCallback, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Play, Check, X, Target, Zap } from 'lucide-react'
import type { Mission } from '../../api'
import MissionGraph from './MissionGraph'
import LiveMissionView from './LiveMissionView'
import type { AgentInfo } from './AgentNode'

/* ============================================================
   MISSION CENTER — replaces the old task manager.
   Top: featured mission with large branching progress graph.
   Below: recent missions.
   Clicking a mission opens the Live Mission View.
   ============================================================ */

interface MissionCenterProps {
  api: any
}

const STATUS_LABEL: Record<string, string> = {
  queued: 'QUEUED',
  planning: 'PLANNING',
  running: 'RUNNING',
  waiting_approval: 'WAITING APPROVAL',
  completed: 'COMPLETED',
  failed: 'FAILED',
  cancelled: 'CANCELLED',
  interrupted: 'INTERRUPTED',
}

const STATUS_COLOR: Record<string, string> = {
  queued: 'var(--nova-lunar)',
  planning: 'var(--nova-violet)',
  running: 'var(--nova-cyan)',
  waiting_approval: 'var(--nova-amber)',
  completed: 'var(--nova-mint)',
  failed: 'var(--nova-coral)',
  cancelled: 'var(--nova-lunar)',
  interrupted: 'var(--nova-amber)',
}

function makeAgents(mission: Mission): AgentInfo[] {
  const steps = mission.steps ?? []
  const running = steps.filter(s => s.status === 'running')
  const waiting = steps.filter(s => s.status === 'waiting_approval')
  const roles = ['Architect', 'Designer', 'Engineer', 'Researcher']
  const agents: AgentInfo[] = []
  running.forEach((s, i) => agents.push({
    role: roles[i % roles.length],
    state: 'active',
    action: `Executing ${s.tool}`,
  }))
  waiting.forEach((s, i) => agents.push({
    role: roles[(running.length + i) % roles.length],
    state: 'waiting',
    action: `Awaiting approval for ${s.tool}`,
  }))
  return agents
}

export default function MissionCenter({ api }: MissionCenterProps) {
  const [missions, setMissions] = useState<Mission[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [active, setActive] = useState<Mission | null>(null)
  const [launchGoal, setLaunchGoal] = useState('')
  const [launching, setLaunching] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const list = await api.missions()
      setMissions(list)
      setError('')
    } catch {
      setError('Mission service unavailable')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { refresh() }, [refresh])

  // Poll while a mission is running/waiting.
  useEffect(() => {
    if (!autoRefresh) return
    const t = setInterval(async () => {
      await refresh()
      if (active) {
        try { setActive(await api.mission(active.id)) } catch { /* keep last */ }
      }
    }, 4000)
    return () => clearInterval(t)
  }, [autoRefresh, active, refresh, api])

  useEffect(() => {
    const running = missions.some(m => m.status === 'running' || m.status === 'planning' || m.status === 'waiting_approval')
    setAutoRefresh(running)
  }, [missions])

  const openMission = async (m: Mission) => {
    try { setActive(await api.mission(m.id)) } catch { setActive(m) }
  }

  const launch = async () => {
    if (!launchGoal.trim() || launching) return
    setLaunching(true)
    try {
      const m = await api.launchMission(launchGoal.trim())
      setLaunchGoal('')
      await refresh()
      openMission(m)
    } catch {
      setError('Could not launch mission')
    } finally {
      setLaunching(false)
    }
  }

  const approve = async (stepId: string) => {
    if (!active) return
    try {
      await api.approveMissionStep(active.id, stepId)
      setActive(await api.mission(active.id))
      refresh()
    } catch { /* ignore */ }
  }

  const deny = async (stepId: string) => {
    if (!active) return
    try {
      await api.denyMissionStep(active.id, stepId)
      setActive(await api.mission(active.id))
      refresh()
    } catch { /* ignore */ }
  }

  const cancel = async () => {
    if (!active) return
    try {
      await api.cancelMission(active.id)
      setActive(await api.mission(active.id))
      refresh()
    } catch { /* ignore */ }
  }

  const featured = missions[0] ?? null

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      style={{
        flex: 1,
        overflowY: 'auto',
        padding: 'clamp(24px, 5vh, 48px) clamp(24px, 4vw, 64px)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <div className="nova-meta" style={{ color: 'var(--nova-violet)', marginBottom: 6 }}>EXECUTION LAYER</div>
          <h1 style={screenTitle}>Missions</h1>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '7px 12px', borderRadius: 12,
            background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
          }}>
            <input
              value={launchGoal}
              onChange={e => setLaunchGoal(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') launch() }}
              placeholder="Give Salaar a mission…"
              style={{
                background: 'transparent', border: 'none', outline: 'none',
                color: 'var(--nova-white)', fontSize: 13, width: 220,
              }}
            />
            <motion.button
              onClick={launch}
              disabled={launching}
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.95 }}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 14px', borderRadius: 9,
                background: 'linear-gradient(135deg, rgba(96,239,255,.18), rgba(168,121,255,.18))',
                border: '1px solid var(--nova-line-cyan)',
                color: 'var(--nova-white)', cursor: 'pointer', fontSize: 12, fontWeight: 600,
              }}
            >
              <Zap size={13}/> {launching ? 'Launching…' : 'Launch'}
            </motion.button>
          </div>
        </div>
      </div>

      {error && <div style={{ color: 'var(--nova-coral)', fontSize: 13, marginBottom: 16 }}>{error}</div>}

      {loading && <div style={{ textAlign: 'center', padding: 80, color: 'var(--nova-lunar)' }}>Reading missions…</div>}

      {!loading && missions.length === 0 && (
        <div style={{
          display: 'grid', placeItems: 'center', padding: '80px 20px', textAlign: 'center',
          border: '1px dashed var(--nova-line)', borderRadius: 22,
        }}>
          <h3 style={{ color: 'var(--nova-white)', fontWeight: 300, fontSize: 22, margin: '0 0 6px' }}>No active missions</h3>
          <p style={{ color: 'var(--nova-lunar)', fontSize: 14, margin: 0 }}>
            Give Salaar something ambitious.
          </p>
          <button onClick={() => { /* focus the launch input */ }}
            style={{ marginTop: 16, padding: '10px 22px', borderRadius: 12, border: '1px solid var(--nova-line-cyan)', background: 'transparent', color: 'var(--nova-cyan)', cursor: 'pointer', fontSize: 13 }}>
            Start a mission
          </button>
        </div>
      )}

      {/* Featured mission */}
      {featured && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          onClick={() => openMission(featured)}
          className="nova-intel-glass"
          style={{
            padding: '24px 28px', cursor: 'pointer',
            display: 'flex', flexDirection: 'column', gap: 16,
            marginBottom: 20,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="nova-meta" style={{ color: 'var(--nova-violet)', marginBottom: 4 }}>FEATURED MISSION</div>
              <h2 style={{ margin: 0, fontSize: 'clamp(20px, 2.4vw, 26px)', fontWeight: 400, letterSpacing: '-0.02em', color: 'var(--nova-white)' }}>
                {featured.goal}
              </h2>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 28, fontWeight: 300, color: 'var(--nova-cyan)', fontVariantNumeric: 'tabular-nums' }}>
                {featured.step_count > 0 ? Math.round((featured.completed_count / featured.step_count) * 100) : 0}%
              </div>
              <div className="nova-meta" style={{ color: STATUS_COLOR[featured.status] ?? 'var(--nova-lunar)' }}>
                {STATUS_LABEL[featured.status] ?? featured.status}
              </div>
            </div>
          </div>

          {/* Branching timeline */}
          <MissionGraph mission={featured} height={340}/>

          {/* Summary row */}
          <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', fontSize: 12, color: 'var(--nova-lunar)' }}>
            <span><b style={{ color: 'var(--nova-white)', fontWeight: 500 }}>{featured.completed_count}</b> / {featured.step_count} steps</span>
            <span>{featured.replan_count > 0 ? `${featured.replan_count} replans` : 'No replans'}</span>
            {featured.result_summary && <span>{featured.result_summary}</span>}
          </div>
        </motion.div>
      )}

      {/* Recent missions */}
      {missions.length > 1 && (
        <div style={{ marginTop: 24 }}>
          <div className="nova-meta" style={{ marginBottom: 12 }}>RECENT MISSIONS</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {missions.slice(1, 8).map(m => {
              const pct = m.step_count > 0 ? Math.round((m.completed_count / m.step_count) * 100) : 0
              return (
                <motion.button
                  key={m.id}
                  whileHover={{ x: 4 }}
                  onClick={() => openMission(m)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 16,
                    padding: '14px 18px', borderRadius: 14, textAlign: 'left',
                    background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
                    cursor: 'pointer', width: '100%',
                  }}
                >
                  <Target size={16} style={{ color: 'var(--nova-violet)', flexShrink: 0 }}/>
                  <span style={{ flex: 1, fontSize: 13.5, color: 'var(--nova-white)' }}>{m.goal}</span>
                  <div style={{ width: 90, height: 4, borderRadius: 4, background: 'rgba(255,255,255,.08)', overflow: 'hidden' }}>
                    <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, var(--nova-cyan), var(--nova-violet))' }}/>
                  </div>
                  <span style={{ width: 44, textAlign: 'right', fontSize: 12, color: STATUS_COLOR[m.status] ?? 'var(--nova-lunar)' }}>
                    {STATUS_LABEL[m.status]?.split(' ')[0] ?? m.status}
                  </span>
                </motion.button>
              )
            })}
          </div>
        </div>
      )}

      {/* Live mission view */}
      <AnimatePresence>
        {active && (
          <motion.div
            key="live-mission-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{
              position: 'fixed', inset: 0, zIndex: 60,
              background: 'rgba(5,6,10,.85)',
              backdropFilter: 'blur(16px)',
              display: 'flex',
              overflowY: 'auto',
            }}
          >
            <LiveMissionView
              mission={active}
              agents={makeAgents(active)}
              onApprove={approve}
              onDeny={deny}
              onClose={() => setActive(null)}
            />
            {/* Cancel button */}
            {(active.status === 'running' || active.status === 'planning' || active.status === 'waiting_approval') && (
              <button onClick={cancel}
                style={{
                  position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
                  padding: '10px 24px', borderRadius: 12, zIndex: 61,
                  background: 'rgba(255,113,133,.08)', border: '1px solid var(--nova-coral)',
                  color: 'var(--nova-coral)', cursor: 'pointer', fontSize: 12, fontWeight: 600,
                }}>
                Cancel Mission
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

const screenTitle: React.CSSProperties = {
  margin: 0, fontSize: 'clamp(28px, 3.6vw, 40px)', fontWeight: 300,
  letterSpacing: '-0.03em', color: 'var(--nova-white)',
}
