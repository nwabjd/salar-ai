import React, { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

/* ============================================================
   SALAAR CORE — Layered 3D intelligence orb.

   Structure (outer → inner):
     1. Shell: translucent outer sphere, subtle refraction
     2. Orbit arcs: two thin elliptical rings (slow rotation)
     3. Inner: luminous violet-to-cyan gradient core
     4. Particles: small dots that orbit and react to state
     5. Text: state label beneath the orb

   States: idle | listening | understanding | thinking | planning
           acting | verifying | waiting | warning | error | complete
   ============================================================ */

type CoreState =
  | 'idle' | 'listening' | 'understanding' | 'thinking'
  | 'planning' | 'acting' | 'verifying' | 'waiting'
  | 'warning' | 'error' | 'complete'

const STATE_TEXT: Record<CoreState, string> = {
  idle: 'Ready',
  listening: 'Listening',
  understanding: 'Understanding',
  thinking: 'Thinking',
  planning: 'Building a plan',
  acting: 'Working',
  verifying: 'Checking the result',
  waiting: 'Waiting for your approval',
  warning: 'Something needs attention',
  error: 'Something went wrong',
  complete: 'Done',
}

interface SalaarCoreProps {
  state?: CoreState
  size?: number       // px diameter of the shell
  text?: string       // override state text
  onClick?: () => void
}

export default function SalaarCore({
  state = 'idle',
  size = 260,
  text,
  onClick,
}: SalaarCoreProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const label = text ?? STATE_TEXT[state]

  /* ---- Particle canvas ---- */
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const dpr = window.devicePixelRatio || 1
    const w = size * 1.4
    const h = size * 1.4
    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.scale(dpr, dpr)

    const particles: { x: number; y: number; vx: number; vy: number; r: number; alpha: number; color: string }[] = []
    const cx = w / 2
    const cy = h / 2

    const isListening = state === 'listening' || state === 'understanding'
    const isThinking = state === 'thinking' || state === 'planning'
    const count = isListening ? 60 : isThinking ? 80 : 40
    const color = isThinking ? '#a879ff' : '#60efff'

    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2
      const dist = size * 0.35 + Math.random() * size * 0.22
      particles.push({
        x: cx + Math.cos(angle) * dist,
        y: cy + Math.sin(angle) * dist,
        vx: (Math.random() - 0.5) * (isThinking ? 0.8 : 0.3),
        vy: (Math.random() - 0.5) * (isThinking ? 0.8 : 0.3),
        r: 1 + Math.random() * 2,
        alpha: 0.25 + Math.random() * 0.6,
        color,
      })
    }

    let raf: number
    function draw() {
      ctx.clearRect(0, 0, w, h)
      for (const p of particles) {
        p.x += p.vx
        p.y += p.vy
        const dx = p.x - cx
        const dy = p.y - cy
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist > size * 0.68) {
          p.vx -= dx * 0.0004
          p.vy -= dy * 0.0004
        }
        if (dist < size * 0.28) {
          p.vx += dx * 0.0004
          p.vy += dy * 0.0004
        }
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = p.color
        ctx.globalAlpha = p.alpha * (state === 'complete' ? 0.3 : 1)
        ctx.fill()
      }
      ctx.globalAlpha = 1
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [state, size])

  const stateColor =
    state === 'error' ? 'var(--nova-coral)' :
    state === 'warning' || state === 'waiting' ? 'var(--nova-amber)' :
    state === 'thinking' || state === 'planning' ? 'var(--nova-violet)' :
    state === 'complete' ? 'var(--nova-white)' :
    'var(--nova-cyan)'

  const isListening = state === 'listening' || state === 'understanding'
  const isThinking = state === 'thinking' || state === 'planning'
  const isActing = state === 'acting'

  return (
    <div
      className="nova-core-wrap"
      style={{
        width: size * 1.4,
        height: size * 1.4,
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: onClick ? 'pointer' : undefined,
      }}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      aria-label={`Salaar Core — ${label}`}
    >
      {/* Particle canvas */}
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
        }}
      />

      {/* Outer shell: translucent sphere with border glow */}
      <motion.div
        className="nova-core-shell"
        animate={{
          scale: isListening ? [1, 1.06, 1] : isActing ? 1.03 : 1,
          opacity: state === 'error' ? 0.75 : 1,
        }}
        transition={{ duration: isListening ? 2.2 : 1.6, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          position: 'absolute',
          width: size,
          height: size,
          borderRadius: '50%',
          border: `1.5px solid ${stateColor}`,
          background: `radial-gradient(circle at 45% 40%, rgba(168, 121, 255, .06), rgba(96, 239, 255, .04), transparent 70%)`,
          boxShadow: `inset 0 2px 40px rgba(0,0,0,.35), 0 0 ${isListening ? '60px' : '40px'} ${stateColor}44`,
        }}
      />

      {/* Orbit arcs — two thin ellipses */}
      <motion.div
        className="nova-core-orbit"
        animate={{ rotate: 360 }}
        transition={{ duration: 28, repeat: Infinity, ease: 'linear' }}
        style={{
          position: 'absolute',
          width: size * 1.15,
          height: size * 0.5,
          border: `1px solid rgba(96, 239, 255, .18)`,
          borderRadius: '50%',
          pointerEvents: 'none',
        }}
      />
      <motion.div
        className="nova-core-orbit"
        animate={{ rotate: -360 }}
        transition={{ duration: 36, repeat: Infinity, ease: 'linear' }}
        style={{
          position: 'absolute',
          width: size * 1.08,
          height: size * 0.42,
          border: `1px solid rgba(168, 121, 255, .15)`,
          borderRadius: '50%',
          pointerEvents: 'none',
          transform: 'rotate(35deg)',
        }}
      />

      {/* Inner core: luminous gradient ball */}
      <motion.div
        className="nova-core-inner"
        animate={{
          scale: [1, 1.04, 1],
          opacity: isThinking ? [0.88, 1, 0.88] : [0.9, 1, 0.9],
        }}
        transition={{ duration: isThinking ? 3.2 : 4.5, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          position: 'absolute',
          width: size * 0.52,
          height: size * 0.52,
          borderRadius: '50%',
          background: isThinking
            ? 'radial-gradient(circle at 50% 46%, #c09aff, #865cff 60%, #3e2d92)'
            : 'radial-gradient(circle at 50% 46%, #b4f5ff, #60efff 50%, #1d6d8a)',
          boxShadow: `0 0 ${isThinking ? '80px' : '60px'} ${stateColor}66`,
          filter: 'blur(1px)',
        }}
      />

      {/* State text */}
      <AnimatePresence mode="wait">
        <motion.span
          key={label}
          className="nova-meta"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={{ duration: 0.25 }}
          style={{
            position: 'absolute',
            bottom: -28,
            left: '50%',
            transform: 'translateX(-50%)',
            whiteSpace: 'nowrap',
            fontSize: '11px',
            letterSpacing: '.12em',
            textTransform: 'uppercase',
            color: stateColor,
          }}
        >
          {label}
        </motion.span>
      </AnimatePresence>
    </div>
  )
}
