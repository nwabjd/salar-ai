import React from 'react'
import { motion } from 'framer-motion'

/* ============================================================
   AGENT NODE — temporary intelligence node visualization.
   Each node: icon, role, state, current action.
   ============================================================ */

export type AgentState = 'active' | 'waiting' | 'done'

export interface AgentInfo {
  role: string
  state: AgentState
  action: string
  icon?: string
}

const STATE_COLOR: Record<AgentState, string> = {
  active: 'var(--nova-cyan)',
  waiting: 'var(--nova-amber)',
  done: 'var(--nova-mint)',
}

interface AgentNodeProps {
  agent: AgentInfo
}

export default function AgentNode({ agent }: AgentNodeProps) {
  const color = STATE_COLOR[agent.state]
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.8 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '10px 14px',
        borderRadius: 14,
        background: 'var(--nova-glass)',
        WebkitBackdropFilter: 'blur(18px)',
        backdropFilter: 'blur(18px)',
        border: `1px solid ${agent.state === 'active' ? 'var(--nova-line-cyan)' : 'var(--nova-line)'}`,
        boxShadow: agent.state === 'active' ? 'var(--nova-glow-cyan)' : undefined,
        minWidth: 210,
      }}
    >
      <div style={{
        width: 34, height: 34, borderRadius: 11,
        display: 'grid', placeItems: 'center',
        fontSize: 16,
        background: 'linear-gradient(135deg, rgba(96,239,255,.12), rgba(168,121,255,.12))',
        border: `1px solid ${color}`,
        flexShrink: 0,
      }}>
        {agent.icon ?? '◆'}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--nova-white)' }}>{agent.role}</span>
          <span style={{
            fontSize: 8, letterSpacing: '.12em', textTransform: 'uppercase',
            color, padding: '2px 6px', borderRadius: 6,
            border: `1px solid ${color}55`, opacity: 0.9,
          }}>
            {agent.state}
          </span>
        </div>
        <span style={{ fontSize: 11, color: 'var(--nova-lunar)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {agent.action}
        </span>
      </div>
    </motion.div>
  )
}
