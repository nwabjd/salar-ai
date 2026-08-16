import React, { useMemo } from 'react'
import { motion } from 'framer-motion'
import type { Mission, MissionStep } from '../../api'

/* ============================================================
   MISSION GRAPH — branching timeline visualization.

   Steps are grouped into "waves" (single node, then a fan-out of
   parallel nodes, then a merge). Edges are drawn as SVG paths.
   - Active node: illuminated cyan glow
   - Completed nodes: fade gracefully to dim mint
   - Failed / waiting nodes: coral / amber
   ============================================================ */

type Node = {
  id: string
  label: string
  status: MissionStep['status']
  x: number
  y: number
  wave: number
  tool: string
}

function shortLabel(step: MissionStep): string {
  const tool = (step.tool || '').replace(/_/g, ' ')
  if (tool.length <= 18) return tool
  return tool.slice(0, 16) + '…'
}

function layoutSteps(steps: MissionStep[]): { nodes: Node[]; edges: [number, number][] } {
  // Group steps into waves: 1, 3, 1, 3, ... gives a natural branch/merge.
  const waves: MissionStep[][] = []
  let idx = 0
  let want = 1
  while (idx < steps.length) {
    waves.push(steps.slice(idx, idx + want))
    idx += want
    want = want === 1 ? 3 : 1
  }

  const nodeW = 148
  const waveH = 104
  const marginX = 90

  const nodes: Node[] = []
  const edges: [number, number][] = []

  waves.forEach((wave, wi) => {
    const maxPerWave = Math.max(...waves.map(w => w.length))
    const spread = (maxPerWave - 1) * (nodeW + 46) / 2
    wave.forEach((step, si) => {
      const x = -spread + si * (nodeW + 46)
      const y = wi * waveH
      const n: Node = {
        id: step.id,
        label: shortLabel(step),
        status: step.status,
        x,
        y,
        wave: wi,
        tool: step.tool || '',
      }
      nodes.push(n)

      // Edge from the nearest node in the previous wave (fan-out merge).
      if (wi > 0) {
        const prevWaveStart = waves.slice(0, wi).reduce((a, w) => a + w.length, 0)
        const prevStart = nodes[prevWaveStart - waves[wi - 1].length]
        edges.push([prevStart.id === undefined ? prevWaveStart - 1 : nodes.indexOf(prevStart), nodes.indexOf(n)])
      }
    })
  })

  // Recompute edge indices by node id for robustness.
  const byId = new Map(nodes.map((n, i) => [n.id, i]))
  const cleanEdges: [number, number][] = []
  waves.forEach((wave, wi) => {
    if (wi === 0) return
    const prevWave = waves[wi - 1]
    const lastPrev = prevWave[prevWave.length - 1]
    for (const s of wave) {
      const a = byId.get(lastPrev.id)!
      const b = byId.get(s.id)!
      cleanEdges.push([a, b])
    }
  })

  return { nodes, edges: cleanEdges }
}

const STATUS_COLOR: Record<MissionStep['status'], string> = {
  pending: '#9da7ba',
  running: '#60efff',
  completed: '#78f4c5',
  failed: '#ff7185',
  waiting_approval: '#ffcc75',
  approved: '#78f4c5',
  denied: '#ff7185',
}

interface MissionGraphProps {
  mission?: Mission | null
  steps?: MissionStep[]
  height?: number
  className?: string
}

export default function MissionGraph({ mission, steps, height = 420, className }: MissionGraphProps) {
  const list = steps ?? mission?.steps ?? []
  const { nodes, edges } = useMemo(() => layoutSteps(list), [list])

  if (nodes.length === 0) {
    return (
      <div className={`nova-mission-empty ${className ?? ''}`}
        style={{ height, display: 'grid', placeItems: 'center', color: 'var(--nova-lunar)', fontSize: 14 }}>
        No steps planned yet. Salaar is preparing the mission…
      </div>
    )
  }

  // Center the graph vertically.
  const width = 520
  const heightPx = Math.max((Math.max(...nodes.map(n => n.y)) + 120), 140)
  const xOff = width / 2

  return (
    <div className={`nova-mission-graph ${className ?? ''}`} style={{ width: '100%', overflow: 'hidden' }}>
      <svg viewBox={`0 0 ${width} ${Math.min(heightPx, height)}`} style={{ width: '100%', height: 'auto', maxHeight: height }}>
        {/* Edges */}
        {edges.map(([a, b], i) => {
          const na = nodes[a]
          const nb = nodes[b]
          const x1 = na.x + xOff
          const y1 = na.y + 46
          const x2 = nb.x + xOff
          const y2 = nb.y + 8
          const mx = (x1 + x2) / 2
          const path = `M ${x1} ${y1} C ${x1} ${(y1 + y2) / 2}, ${x2} ${(y1 + y2) / 2}, ${x2} ${y2}`
          const active = nb.status === 'running' || nb.status === 'waiting_approval'
          return (
            <motion.path
              key={`e-${i}`}
              d={path}
              fill="none"
              stroke={active ? 'var(--nova-cyan)' : 'var(--nova-line)'}
              strokeWidth={active ? 1.6 : 1}
              strokeDasharray={active ? '6 4' : undefined}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: active ? 0.9 : 0.55 }}
              transition={{ duration: 0.6, delay: 0.1 + i * 0.05 }}
            />
          )
        })}

        {/* Nodes */}
        {nodes.map((n, i) => {
          const color = STATUS_COLOR[n.status] ?? '#9da7ba'
          const active = n.status === 'running' || n.status === 'waiting_approval'
          const done = n.status === 'completed' || n.status === 'approved'
          return (
            <g key={n.id} transform={`translate(${n.x + xOff}, ${n.y})`}>
              <motion.circle
                r={40}
                fill="rgba(10,12,22,.7)"
                stroke={color}
                strokeWidth={active ? 1.8 : 1}
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: done ? 0.65 : 1 }}
                transition={{ duration: 0.45, delay: i * 0.04 }}
                style={{
                  filter: active ? 'drop-shadow(0 0 12px rgba(96,239,255,.5))' : undefined,
                }}
              />
              {/* Inner node ring */}
              <motion.circle
                r={28}
                fill="none"
                stroke={color}
                strokeWidth={0.75}
                strokeOpacity={active ? 0.6 : 0.3}
                animate={active ? { rotate: 360 } : undefined}
                style={{ transformOrigin: 'center', transformBox: 'fill-box' }}
                transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
              />
              {/* Status dot */}
              <circle cx={-26} cy={-26} r={4} fill={color} />
              <text
                textAnchor="middle"
                dy=".35em"
                fontSize="11"
                fontWeight={active ? 600 : 400}
                fill="var(--nova-white)"
                opacity={done ? 0.7 : 1}
              >
                {n.label.length > 14 ? n.label.slice(0, 14) + '…' : n.label}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
