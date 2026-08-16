import React from 'react'
import { motion } from 'framer-motion'
import DevSpace from './DevSpace'
import ResearchSpace from './ResearchSpace'
import type { SpaceKind } from './SpacesOverview'

/* ============================================================
   SPACE CONTAINER — renders the adaptive workspace shell
   for a given Space kind. Contextual UI appears per kind.
   ============================================================ */

interface SpaceContainerProps {
  kind: SpaceKind
  api: any
  onSend?: (text: string) => void
  onBack: () => void
}

export default function SpaceContainer({ kind, api, onSend, onBack }: SpaceContainerProps) {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      {/* Back header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '16px clamp(20px, 3vw, 40px) 0',
      }}>
        <button onClick={onBack} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 14px', borderRadius: 10, cursor: 'pointer',
          background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
          color: 'var(--nova-lunar)', fontSize: 11, letterSpacing: '.08em',
        }}>
          ← SPACES
        </button>
        <motion.span
          key={kind}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="nova-meta"
          style={{ textTransform: 'capitalize' as const }}
        >
          {kind}
        </motion.span>
      </div>

      <motion.div
        key={kind}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
      >
        {kind === 'development' && <DevSpace api={api} onSend={onSend}/>}
        {kind === 'research' && <ResearchSpace api={api} onSend={onSend}/>}
        {(kind === 'creative' || kind === 'business' || kind === 'personal' || kind === 'device') && (
          <div style={{ flex: 1, display: 'grid', placeItems: 'center', textAlign: 'center', gap: 8, flexDirection: 'column' }}>
            <h2 style={{ fontSize: 'clamp(22px, 3vw, 32px)', fontWeight: 300, letterSpacing: '-0.03em', color: 'var(--nova-white)', margin: 0 }}>
              {kind[0].toUpperCase() + kind.slice(1)} Space
            </h2>
            <p style={{ fontSize: 13, color: 'var(--nova-lunar)', margin: 0 }}>
              This Space is warming up. Ask Salaar to begin work here.
            </p>
          </div>
        )}
      </motion.div>
    </div>
  )
}
