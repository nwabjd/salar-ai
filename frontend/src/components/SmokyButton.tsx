import React, { useCallback, useRef, useEffect, useState } from 'react'

interface SmokyButtonProps {
  children: React.ReactNode
  onClick?: () => void
  active?: boolean
  colors?: { primary: string; secondary: string; shadow: string }
  className?: string
}

const DEFAULT_COLORS = { primary: '#8b5cf6', secondary: '#6366f1', shadow: '#050506' }

export default function SmokyButton({ children, onClick, active = false, colors = DEFAULT_COLORS, className = '' }: SmokyButtonProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animRef = useRef<number>(0)
  const particlesRef = useRef<Array<{ x: number; y: number; vx: number; vy: number; life: number; maxLife: number; size: number; color: string }>>([])
  const mouseRef = useRef({ x: 0, y: 0 })

  const spawnParticles = useCallback((cx: number, cy: number, count: number) => {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2
      const speed = 0.3 + Math.random() * 1.5
      const life = 40 + Math.random() * 60
      const c = Math.random() > 0.5 ? colors.primary : colors.secondary
      particlesRef.current.push({
        x: cx + (Math.random() - 0.5) * 20,
        y: cy + (Math.random() - 0.5) * 20,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 0.5,
        life,
        maxLife: life,
        size: 2 + Math.random() * 4,
        color: c,
      })
    }
  }, [colors])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect()
      if (rect) {
        canvas.width = rect.width * 2
        canvas.height = rect.height * 2
        canvas.style.width = rect.width + 'px'
        canvas.style.height = rect.height + 'px'
        ctx.scale(2, 2)
      }
    }
    resize()

    let running = true
    const loop = () => {
      if (!running) return
      const w = canvas.width / 2
      const h = canvas.height / 2
      ctx.clearRect(0, 0, w, h)

      if (active) {
        spawnParticles(w / 2, h / 2, 2)
      }

      const particles = particlesRef.current
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i]
        p.x += p.vx
        p.y += p.vy
        p.vy -= 0.02
        p.vx *= 0.99
        p.life--

        const alpha = (p.life / p.maxLife) * 0.6
        const size = p.size * (p.life / p.maxLife)

        ctx.beginPath()
        ctx.arc(p.x, p.y, size, 0, Math.PI * 2)
        ctx.fillStyle = p.color + Math.round(alpha * 255).toString(16).padStart(2, '0')
        ctx.fill()

        // Glow
        ctx.beginPath()
        ctx.arc(p.x, p.y, size * 2, 0, Math.PI * 2)
        const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, size * 2)
        grad.addColorStop(0, p.color + Math.round(alpha * 128).toString(16).padStart(2, '0'))
        grad.addColorStop(1, p.color + '00')
        ctx.fillStyle = grad
        ctx.fill()

        if (p.life <= 0) particles.splice(i, 1)
      }

      animRef.current = requestAnimationFrame(loop)
    }
    loop()

    return () => { running = false; cancelAnimationFrame(animRef.current) }
  }, [active, spawnParticles])

  return (
    <div className={`smoky-btn-wrap ${className}`}>
      <canvas ref={canvasRef} className="smoky-canvas" />
      <button className={`smoky-btn${active ? ' active' : ''}`} onClick={onClick}>
        {children}
      </button>
      <div className="smoky-shadow" style={{ background: `radial-gradient(ellipse at center, ${colors.shadow}40 0%, transparent 70%)` }} />
    </div>
  )
}
