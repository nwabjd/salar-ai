import React, { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'

/* ============================================================
   NOVA BACKGROUND — subtle volumetric environment.
   Three layers:
     1. Static gradient base (Midnight Graphite → Deep Navy → Dark Violet)
     2. Canvas haze: slow-moving soft radial glows
     3. Drifting particles
   Barely noticeable. Never distracting.
   ============================================================ */

export default function NovaBackground() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const w = window.innerWidth
    const h = window.innerHeight
    canvas.width = w * dpr
    canvas.height = h * dpr
    ctx.scale(dpr, dpr)

    // Haze blobs
    const blobs = [
      { x: w * 0.2, y: h * 0.3, r: w * 0.35, color: '96, 239, 255', alpha: 0.05, vx: 0.03, vy: 0.02 },
      { x: w * 0.8, y: h * 0.6, r: w * 0.4, color: '168, 121, 255', alpha: 0.05, vx: -0.02, vy: 0.03 },
      { x: w * 0.55, y: h * 0.15, r: w * 0.3, color: '96, 239, 255', alpha: 0.03, vx: 0.02, vy: 0.04 },
    ]

    // Particles
    const particles = Array.from({ length: 26 }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.15,
      vy: (Math.random() - 0.5) * 0.15,
      r: 0.6 + Math.random() * 1.2,
      alpha: 0.06 + Math.random() * 0.12,
    }))

    let raf: number
    let t = 0
    function draw() {
      t += 0.004
      ctx.clearRect(0, 0, w, h)

      // Haze
      for (const b of blobs) {
        const x = b.x + Math.sin(t + b.alpha) * 30
        const y = b.y + Math.cos(t * 0.8) * 20
        const grad = ctx.createRadialGradient(x, y, 0, x, y, b.r)
        grad.addColorStop(0, `rgba(${b.color}, ${b.alpha})`)
        grad.addColorStop(1, `rgba(${b.color}, 0)`)
        ctx.fillStyle = grad
        ctx.fillRect(0, 0, w, h)
      }

      // Particles
      for (const p of particles) {
        p.x += p.vx
        p.y += p.vy
        if (p.x < 0) p.x = w
        if (p.x > w) p.x = 0
        if (p.y < 0) p.y = h
        if (p.y > h) p.y = 0
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(247, 249, 255, ${p.alpha})`
        ctx.fill()
      }

      raf = requestAnimationFrame(draw)
    }
    draw()

    const onResize = () => {
      const nw = window.innerWidth
      const nh = window.innerHeight
      canvas.width = nw * dpr
      canvas.height = nh * dpr
      ctx.scale(dpr, dpr)
    }
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return (
    <div className="nova-background" style={{
      position: 'fixed',
      inset: 0,
      zIndex: 0,
      background: 'linear-gradient(160deg, var(--nova-bg-void) 0%, var(--nova-bg-navy) 45%, var(--nova-bg-violet) 100%)',
    }}>
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      />
      {/* Vignette */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(5,6,10,.55) 100%)',
        pointerEvents: 'none',
      }}/>
      {/* Slow rotating light */}
      <motion.div
        animate={{ opacity: [0.0, 0.04, 0.0] }}
        transition={{ duration: 18, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          position: 'absolute',
          left: '50%', top: '38%',
          width: '60vw', height: '60vw',
          marginLeft: '-30vw', marginTop: '-30vw',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(168,121,255,.08), transparent 65%)',
          pointerEvents: 'none',
        }}
      />
    </div>
  )
}
