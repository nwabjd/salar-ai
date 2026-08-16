import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Home, Layers, Target, BrainCircuit, Monitor, Settings,
  User, ChevronRight, Users,
} from 'lucide-react'

/* ============================================================
   NOVA RAIL — Minimal collapsed sidebar on the left.
   Icons: Home, Spaces, Missions, Memory, Devices, System, Agents.
   Bottom: Settings, User profile.
   Expanded on hover. Never more than 220px.
   ============================================================ */

export type RailView = 'home' | 'spaces' | 'missions' | 'memory' | 'devices' | 'system' | 'agents'

interface RailProps {
  active?: RailView
  onNavigate?: (view: RailView) => void
}

const NAV_ITEMS: { id: RailView; icon: React.ReactNode; label: string }[] = [
  { id: 'home',    icon: <Home size={20} strokeWidth={1.6}/>,           label: 'Home' },
  { id: 'spaces',  icon: <Layers size={20} strokeWidth={1.6}/>,         label: 'Spaces' },
  { id: 'missions',icon: <Target size={20} strokeWidth={1.6}/>,         label: 'Missions' },
  { id: 'agents',  icon: <Users size={20} strokeWidth={1.6}/>,          label: 'Agents' },
  { id: 'memory',  icon: <BrainCircuit size={20} strokeWidth={1.6}/>,   label: 'Memory' },
  { id: 'devices', icon: <Monitor size={20} strokeWidth={1.6}/>,        label: 'Devices' },
  { id: 'system',  icon: <Settings size={20} strokeWidth={1.6}/>,       label: 'System' },
]

export default function NovaRail({ active = 'home', onNavigate }: RailProps) {
  const [expanded, setExpanded] = useState(false)

  return (
    <motion.nav
      className="nova-rail"
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
      animate={{ width: expanded ? 200 : 56 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      style={{
        position: 'fixed',
        top: 18,
        left: 18,
        bottom: 18,
        zIndex: 40,
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        padding: '14px 8px',
        background: 'var(--nova-glass)',
        WebkitBackdropFilter: 'blur(28px) saturate(150%)',
        backdropFilter: 'blur(28px) saturate(150%)',
        border: '1px solid var(--nova-line)',
        borderRadius: 18,
        overflow: 'hidden',
      }}
    >
      {/* Brand glyph */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '0 6px 14px',
        marginBottom: 4,
        borderBottom: '1px solid var(--nova-line)',
      }}>
        <div style={{
          width: 34, height: 34, borderRadius: 11,
          display: 'grid', placeItems: 'center',
          background: 'linear-gradient(135deg, rgba(96, 239, 255, .12), rgba(168, 121, 255, .12))',
          border: '1px solid var(--nova-line-cyan)',
          fontSize: 14, fontWeight: 600, color: 'var(--nova-white)',
          flexShrink: 0,
        }}>S</div>
        {expanded && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.08 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.18em', color: 'var(--nova-white)' }}>SALAR</div>
            <div style={{ fontSize: 8, letterSpacing: '.12em', color: 'var(--nova-lunar)', marginTop: 2 }}>NOVA</div>
          </motion.div>
        )}
      </div>

      {/* Navigation */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
        {NAV_ITEMS.map(item => {
          const isActive = item.id === active
          return (
            <motion.button
              key={item.id}
              onClick={() => onNavigate?.(item.id)}
              whileHover={{ backgroundColor: 'rgba(255,255,255,.07)' }}
              whileTap={{ scale: 0.97 }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '10px 10px',
                border: 'none',
                borderRadius: 12,
                background: isActive ? 'rgba(96, 239, 255, .10)' : 'transparent',
                color: isActive ? 'var(--nova-cyan)' : 'var(--nova-lunar)',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                letterSpacing: '.02em',
                transition: 'color 0.18s',
                textAlign: 'left',
                overflow: 'hidden',
                whiteSpace: 'nowrap',
              }}
              title={item.label}
            >
              <span style={{ flexShrink: 0, width: 24, display: 'flex', justifyContent: 'center' }}>{item.icon}</span>
              {expanded && (
                <motion.span initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.06 }}>
                  {item.label}
                </motion.span>
              )}
            </motion.button>
          )
        })}
      </div>

      {/* Bottom */}
      <div style={{ borderTop: '1px solid var(--nova-line)', paddingTop: 8, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <motion.button
          whileHover={{ backgroundColor: 'rgba(255,255,255,.07)' }}
          whileTap={{ scale: 0.97 }}
          style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '10px 10px', border: 'none', borderRadius: 12,
            background: 'transparent', color: 'var(--nova-lunar)',
            cursor: 'pointer', fontSize: 12, textAlign: 'left',
          }}
          title="Settings"
        >
          <span style={{ flexShrink: 0, width: 24, display: 'flex', justifyContent: 'center' }}><Settings size={20} strokeWidth={1.6}/></span>
          {expanded && <span>Settings</span>}
        </motion.button>
        <motion.button
          whileHover={{ backgroundColor: 'rgba(255,255,255,.07)' }}
          whileTap={{ scale: 0.97 }}
          style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '10px 10px', border: 'none', borderRadius: 12,
            background: 'transparent', color: 'var(--nova-lunar)',
            cursor: 'pointer', fontSize: 12, textAlign: 'left',
          }}
          title="Profile"
        >
          <span style={{ flexShrink: 0, width: 24, display: 'flex', justifyContent: 'center' }}><User size={20} strokeWidth={1.6}/></span>
          {expanded && <span>JD</span>}
        </motion.button>
      </div>
    </motion.nav>
  )
}
