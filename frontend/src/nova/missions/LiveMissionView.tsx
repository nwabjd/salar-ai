import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import type { Mission, MissionStep } from '../../api'
import AgentNode, { AgentInfo } from './AgentNode'

/* ============================================================
   LIVE MISSION VIEW — immersive execution.
   Center: mission objective.
   Around it: active task nodes, connected by animated lines.
   ============================================================ */

interface LiveMissionViewProps {
  mission: Mission
  agents?: AgentInfo[]
  onApprove?: (stepId: string) => void
  onDeny?: (stepId: string) => void
  onClose?: () => void
}

function stepTitle(step: MissionStep): string {
  return (step.tool || '').replace(/_/g, ' ')
}

export default function LiveMissionView({ mission, agents = [], onApprove, onDeny, onClose }: LiveMissionViewProps) {
  const steps = mission.steps ?? []
  const activeSteps = steps.filter(s => s.status === 'running')
  const waitingSteps = steps.filter(s => s.status === 'waiting_approval')
  const doneCount = steps.filter(s => s.status === 'completed' || s.status === 'approved').length
  const pct = mission.step_count > 0 ? Math.round((doneCount / mission.step_count) * 100) : 0

  // Distribute active steps around the objective.
  const ringItems = activeSteps.slice(0, 6).map((s, i) => ({ step: s, angle: (i / Math.max(activeSteps.length, 1)) * Math.PI * 2 - Math.PI / 2 }))

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="nova-live-mission"
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '40px 24px',
        position: 'relative',
      }}
    >
      {/* Close */}
      {onClose && (
        <button onClick={onClose} style={{
          position: 'absolute', top: 24, right: 24,
          padding: '8px 14px', borderRadius: 12,
          background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
          color: 'var(--nova-lunar)', cursor: 'pointer', fontSize: 11, letterSpacing: '.08em',
        }}>
          EXIT MISSION
        </button>
      )}

      {/* Progress header */}
      <div style={{ marginBottom: 24, textAlign: 'center' }}>
        <div className="nova-meta" style={{ color: 'var(--nova-cyan)', marginBottom: 8 }}>LIVE MISSION</div>
        <h2 style={{ fontSize: 'clamp(24px, 3vw, 36px)', fontWeight: 300, letterSpacing: '-0.03em', color: 'var(--nova-white)', margin: 0 }}>
          {mission.goal}
        </h2>
        <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'center' }}>
          <div style={{ width: 180, height: 3, borderRadius: 3, background: 'rgba(255,255,255,.08)', overflow: 'hidden' }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
              style={{ height: '100%', background: 'linear-gradient(90deg, var(--nova-cyan), var(--nova-violet))', boxShadow: 'var(--nova-glow-cyan)' }}
            />
          </div>
          <span style={{ fontSize: 12, color: 'var(--nova-lunar)', fontVariantNumeric: 'tabular-nums' }}>{pct}%</span>
        </div>
      </div>

      {/* Orbital ring with task nodes */}
      <div style={{ position: 'relative', width: 420, height: 420, display: 'grid', placeItems: 'center', margin: '10px 0 20px' }}>
        {/* Static rings */}
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 60, repeat: Infinity, ease: 'linear' }}
          style={{
            position: 'absolute', width: 420, height: 420, borderRadius: '50%',
            border: '1px solid rgba(96,239,255,.10)',
          }}
        />
        <motion.div
          animate={{ rotate: -360 }}
          transition={{ duration: 90, repeat: Infinity, ease: 'linear' }}
          style={{
            position: 'absolute', width: 330, height: 330, borderRadius: '50%',
            border: '1px dashed rgba(168,121,255,.15)',
          }}
        />

        {/* Connector lines from objective to active nodes */}
        <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
          {ringItems.map(({ step, angle }, i) => {
            const x1 = 210, y1 = 210
            const x2 = 210 + Math.cos(angle) * 160
            const y2 = 210 + Math.sin(angle) * 160
            return (
              <motion.line
                key={`l-${i}`}
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke="rgba(96,239,255,.4)"
                strokeWidth={1}
                strokeDasharray="5 5"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 0.8 }}
                transition={{ duration: 0.5, delay: 0.3 }}
              />
            )
          })}
        </svg>

        {/* Center objective */}
        <motion.div
          animate={{ scale: [1, 1.03, 1] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            width: 90, height: 90, borderRadius: '50%',
            display: 'grid', placeItems: 'center',
            textAlign: 'center',
            background: 'radial-gradient(circle at 45% 40%, rgba(168,121,255,.16), rgba(10,12,22,.8))',
            border: '1px solid var(--nova-line-violet)',
            boxShadow: 'var(--nova-glow-violet)',
          }}
        >
          <div style={{ fontSize: 11, color: 'var(--nova-white)', lineHeight: 1.4, padding: 10 }}>
            <span style={{ display: 'block', fontSize: 8, letterSpacing: '.14em', color: 'var(--nova-violet)', marginBottom: 4 }}>OBJECTIVE</span>
            {mission.goal.length > 32 ? mission.goal.slice(0, 30) + '…' : mission.goal}
          </div>
        </motion.div>

        {/* Orbiting task nodes */}
        {ringItems.map(({ step, angle }, i) => (
          <motion.div
            key={`n-${i}`}
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 + i * 0.08 }}
            style={{
              position: 'absolute',
              left: 210 + Math.cos(angle) * 150,
              top: 210 + Math.sin(angle) * 150,
              transform: 'translate(-50%, -50%)',
              padding: '8px 12px',
              borderRadius: 10,
              background: 'var(--nova-glass)',
              backdropFilter: 'blur(12px)',
              border: '1px solid var(--nova-line-cyan)',
              boxShadow: 'var(--nova-glow-cyan)',
              fontSize: 11,
              color: 'var(--nova-white)',
              whiteSpace: 'nowrap',
              maxWidth: 150,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            <span style={{ color: 'var(--nova-cyan)' }}>◉</span> {stepTitle(step)}
          </motion.div>
        ))}
      </div>

      {/* Waiting for approval */}
      <AnimatePresence>
        {waitingSteps.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{
              display: 'flex', alignItems: 'center', gap: 14,
              padding: '14px 18px', borderRadius: 16,
              background: 'rgba(255,204,117,.06)',
              border: '1px solid var(--nova-line)',
              boxShadow: 'var(--nova-glow-amber)',
            }}
          >
            <span className="nova-meta" style={{ color: 'var(--nova-amber)' }}>AWAITING APPROVAL</span>
            <span style={{ fontSize: 13, color: 'var(--nova-white)' }}>{waitingSteps.map(stepTitle).join(', ')}</span>
            <button onClick={() => onApprove?.(waitingSteps[0].id)}
              style={approvalBtn('var(--nova-mint)')}>Approve</button>
            <button onClick={() => onDeny?.(waitingSteps[0].id)}
              style={approvalBtn('var(--nova-coral)')}>Deny</button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Agent nodes */}
      {agents.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center', marginTop: 16 }}>
          {agents.map((a, i) => <AgentNode key={i} agent={a}/>)}
        </div>
      )}
    </motion.div>
  )
}

function approvalBtn(color: string): React.CSSProperties {
  return {
    padding: '7px 16px', borderRadius: 10,
    background: 'transparent', border: `1px solid ${color}`,
    color, cursor: 'pointer', fontSize: 12, fontWeight: 600,
  }
}
