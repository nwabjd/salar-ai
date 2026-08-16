import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import type { RailView } from '../NovaRail'

/* ============================================================
   CONTEXT SYSTEM — Context Dock.
   A floating panel (hidden by default) that surfaces the
   current situation: what Salaar knows about this view,
   recent signals, and suggested next actions.
   ============================================================ */

const VIEW_CONTEXT: Record<RailView, { label: string; summary: string; signals: string[]; suggestions: string[] }> = {
  home: {
    label: 'HOME',
    summary: 'You are at the center. Salaar is idle and listening.',
    signals: ['All systems nominal', 'No pending approvals'],
    suggestions: ['Ask Salaar anything', 'Start a mission'],
  },
  spaces: {
    label: 'SPACES',
    summary: 'Spatial environments for task-specific work.',
    signals: ['Development Space active', 'File tree loaded'],
    suggestions: ['Open Development Space', 'Begin research'],
  },
  missions: {
    label: 'MISSIONS',
    summary: 'Branching goals Salaar executes with oversight.',
    signals: ['Mission orchestration ready'],
    suggestions: ['Launch a mission', 'Review running missions'],
  },
  agents: {
    label: 'AGENTS',
    summary: 'Specialist agents Salaar delegates work to.',
    signals: ['Swarm online', 'Event bus connected'],
    suggestions: ['Dispatch a task', 'Review live runs'],
  },
  memory: {
    label: 'MEMORY',
    summary: 'The permanent substrate of what Salaar knows.',
    signals: ['Long-term store connected'],
    suggestions: ['Search memory', 'Save an insight'],
  },
  devices: {
    label: 'DEVICES',
    summary: 'Connected surfaces Salaar can command.',
    signals: ['Device channel online'],
    suggestions: ['Register a device', 'Send a command'],
  },
  system: {
    label: 'SYSTEM',
    summary: 'Runtime health and control surfaces.',
    signals: ['Backend responding'],
    suggestions: ['Review health', 'Check history'],
  },
}

interface ContextDockProps {
  view: RailView
}

export default function ContextDock({ view }: ContextDockProps) {
  const [open, setOpen] = React.useState(false)
  const ctx = VIEW_CONTEXT[view] ?? VIEW_CONTEXT.home

  return (
    <>
      {/* Toggle */}
      <button
        onClick={() => setOpen(o => !o)}
        aria-label={open ? 'Hide context' : 'Show context'}
        style={{
          position: 'fixed', right: 18, bottom: 18, zIndex: 80,
          width: 36, height: 36, borderRadius: 12,
          display: 'grid', placeItems: 'center',
          background: 'var(--nova-glass)',
          WebkitBackdropFilter: 'blur(16px)', backdropFilter: 'blur(16px)',
          border: open ? '1px solid var(--nova-line-cyan)' : '1px solid var(--nova-line)',
          color: open ? 'var(--nova-cyan)' : 'var(--nova-lunar)',
          cursor: 'pointer',
        }}
      >
        {open ? <PanelRightClose size={15}/> : <PanelRightOpen size={15}/>}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            key="dock"
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 40 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="nova-solid"
            style={{
              position: 'fixed', right: 18, bottom: 62, zIndex: 80,
              width: 300, borderRadius: 18, overflow: 'hidden',
              border: '1px solid var(--nova-line)',
            }}
          >
            <div style={{ padding: '16px 18px', borderBottom: '1px solid var(--nova-line)' }}>
              <div className="nova-meta" style={{ color: 'var(--nova-cyan)', marginBottom: 5 }}>CONTEXT · {ctx.label}</div>
              <div style={{ fontSize: 13, color: 'var(--nova-white)', lineHeight: 1.55 }}>{ctx.summary}</div>
            </div>

            <div style={{ padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <div className="nova-meta" style={{ marginBottom: 7, color: 'var(--nova-violet)' }}>SIGNALS</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {ctx.signals.map(s => (
                    <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 11.5, color: 'var(--nova-lunar)' }}>
                      <span style={{
                        width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
                        background: 'var(--nova-mint)',
                        boxShadow: '0 0 6px rgba(120,244,197,.6)',
                      }}/>
                      {s}
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="nova-meta" style={{ marginBottom: 7, color: 'var(--nova-violet)' }}>SUGGESTED</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                  {ctx.suggestions.map(s => (
                    <div key={s} style={{
                      fontSize: 11.5, color: 'var(--nova-cyan)',
                      padding: '6px 10px', borderRadius: 9,
                      background: 'rgba(96,239,255,.05)', border: '1px solid var(--nova-line-cyan)',
                      cursor: 'pointer',
                    }}>
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
