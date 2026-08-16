import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ShieldAlert, Check, X, Sparkles } from 'lucide-react'

/* ============================================================
   CONTEXT SYSTEM — Permission Overlay.
   A floating confirmation gate that appears before Salaar
   commits to high-stakes or irreversible actions.
   ============================================================ */

export interface PermissionRequest {
  id: string
  title: string
  description: string
  detail: string
  confidence: number // 0..1 Salaar's confidence this is the right action
  irreversible?: boolean
}

interface PermissionOverlayProps {
  request: PermissionRequest | null
  onApprove: () => void
  onDeny: () => void
}

export default function PermissionOverlay({ request, onApprove, onDeny }: PermissionOverlayProps) {
  return (
    <AnimatePresence>
      {request && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            display: 'grid', placeItems: 'center',
            background: 'rgba(6,10,18,0.55)',
            WebkitBackdropFilter: 'blur(6px)', backdropFilter: 'blur(6px)',
          }}
        >
          <motion.div
            key={request.id}
            initial={{ opacity: 0, scale: 0.94, y: 14 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 10 }}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
            className="nova-solid"
            style={{
              width: 'min(440px, 92vw)', borderRadius: 20, overflow: 'hidden',
              border: '1px solid var(--nova-line)',
            }}
          >
            {/* Header strip */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '16px 20px',
              background: request.irreversible
                ? 'linear-gradient(135deg, rgba(255,113,133,.1), rgba(255,204,117,.08))'
                : 'linear-gradient(135deg, rgba(96,239,255,.08), rgba(168,121,255,.1))',
              borderBottom: '1px solid var(--nova-line)',
            }}>
              <span style={{
                width: 36, height: 36, borderRadius: 12, display: 'grid', placeItems: 'center',
                background: request.irreversible
                  ? 'rgba(255,113,133,.14)'
                  : 'rgba(96,239,255,.12)',
                color: request.irreversible ? 'var(--nova-coral)' : 'var(--nova-cyan)',
              }}>
                {request.irreversible ? <ShieldAlert size={17}/> : <Sparkles size={17}/>}
              </span>
              <div>
                <div className="nova-meta" style={{ color: request.irreversible ? 'var(--nova-coral)' : 'var(--nova-cyan)' }}>
                  {request.irreversible ? 'IRREVERSIBLE ACTION' : 'PERMISSION REQUIRED'}
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--nova-white)' }}>{request.title}</div>
              </div>
            </div>

            {/* Body */}
            <div style={{ padding: '18px 20px 20px' }}>
              <p style={{ margin: 0, fontSize: 13, color: 'var(--nova-lunar)', lineHeight: 1.6 }}>
                {request.description}
              </p>
              <div style={{
                marginTop: 14, padding: '11px 14px', borderRadius: 12,
                background: 'rgba(255,255,255,.03)', border: '1px solid var(--nova-line)',
                fontSize: 11.5, color: 'var(--nova-lunar)', lineHeight: 1.6,
              }}>
                {request.detail}
              </div>

              {/* Confidence meter */}
              <div style={{ marginTop: 16 }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  marginBottom: 6,
                }}>
                  <span style={{ fontSize: 10.5, color: 'var(--nova-lunar)', letterSpacing: '.08em' }}>SALAAR CONFIDENCE</span>
                  <span style={{ fontSize: 11, color: 'var(--nova-cyan)' }}>
                    {Math.round(request.confidence * 100)}%
                  </span>
                </div>
                <div style={{ height: 5, borderRadius: 3, background: 'rgba(255,255,255,.07)', overflow: 'hidden' }}>
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.round(request.confidence * 100)}%` }}
                    transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                    style={{
                      height: '100%', borderRadius: 3,
                      background: request.confidence > 0.7
                        ? 'linear-gradient(90deg, var(--nova-cyan), var(--nova-mint))'
                        : 'linear-gradient(90deg, var(--nova-amber), var(--nova-coral))',
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Actions */}
            <div style={{
              display: 'flex', gap: 10, padding: '0 20px 18px',
            }}>
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={onDeny}
                style={{
                  flex: 1, padding: '11px 0', borderRadius: 12,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                  background: 'rgba(255,255,255,.04)',
                  border: '1px solid var(--nova-line)',
                  color: 'var(--nova-lunar)', cursor: 'pointer', fontSize: 12.5, fontWeight: 600,
                }}
              >
                <X size={15}/> DENY
              </motion.button>
              <motion.button
                whileTap={{ scale: 0.97 }}
                onClick={onApprove}
                style={{
                  flex: 1, padding: '11px 0', borderRadius: 12,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                  background: 'linear-gradient(135deg, rgba(96,239,255,.2), rgba(120,244,197,.2))',
                  border: '1px solid var(--nova-line-cyan)',
                  color: 'var(--nova-white)', cursor: 'pointer', fontSize: 12.5, fontWeight: 600,
                }}
              >
                <Check size={15}/> APPROVE
              </motion.button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
