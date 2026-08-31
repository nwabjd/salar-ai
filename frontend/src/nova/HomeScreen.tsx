import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import SalaarCore from './SalaarCore'
import CommandBar from './CommandBar'

/* ============================================================
   HOME SCREEN — Salaar Nova visual centerpiece.
   Structure:
     1. Greeting ("Good morning / Ready when you are.")
     2. Large Salaar Core (center-stage)
     3. Universal command bar
     4. Three intelligent action suggestions
     5. Four intelligence indicators
   ============================================================ */

type CoreState = 'idle' | 'listening' | 'understanding' | 'thinking'
  | 'planning' | 'acting' | 'verifying' | 'waiting' | 'warning' | 'error' | 'complete'

interface HomeProps {
  coreState?: CoreState
  onSend?: (text: string, files?: File[]) => void
  onVoice?: () => void
  onAttach?: (files: File[]) => void
  onSign?: () => void
  onCoreClick?: () => void
  greeting?: string
}

function timeGreeting(): string {
  const h = new Date().getHours()
  if (h < 6) return 'Good night'
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

const SUGGESTIONS = [
  { label: 'Continue development', sub: 'Resume your last mission', icon: '⚡' },
  { label: 'Review priorities', sub: "Today's tasks and deadlines", icon: '🎯' },
  { label: 'Check system health', sub: 'Devices, models, services', icon: '🔬' },
]

interface IntelIndicator {
  label: string
  value: string
  icon: string
}

const defaultIntel: IntelIndicator[] = [
  { label: 'Mission', value: 'Salaar Nova', icon: '🎯' },
  { label: 'Today', value: '3 priorities', icon: '📋' },
  { label: 'Devices', value: '4 online', icon: '💻' },
  { label: 'Status', value: 'Operational', icon: '✦' },
]

export default function HomeScreen({
  coreState = 'idle',
  onSend,
  onVoice,
  onAttach,
  onSign,
  onCoreClick,
  greeting,
}: HomeProps) {
  const [greetingText, setGreetingText] = useState(greeting ?? timeGreeting())
  const [showUI, setShowUI] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setShowUI(true), 600)
    return () => clearTimeout(t)
  }, [])

  return (
    <div style={container}>
      {/* Greeting */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
        style={{ textAlign: 'center', marginBottom: 12 }}
      >
        <h1 style={heroText}>{greetingText}</h1>
        <p style={subText}>Ready when you are.</p>
      </motion.div>

      {/* Core */}
      <motion.div
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
        style={{ display: 'flex', justifyContent: 'center', margin: '8px 0 32px' }}
      >
        <SalaarCore
          state={coreState}
          size={240}
          onClick={onCoreClick}
        />
      </motion.div>

      {/* Command bar */}
      <AnimatePresence>
        {showUI && (
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
            style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}
          >
            <CommandBar onSend={onSend} onVoice={onVoice} onAttach={onAttach} onSign={onSign}/>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Suggestions */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.7, ease: [0.22, 1, 0.36, 1] }}
        style={suggestionsRow}
      >
        {SUGGESTIONS.map((s, i) => (
          <motion.button
            key={s.label}
            whileHover={{ y: -3, boxShadow: '0 12px 36px rgba(0,0,0,.35)' }}
            whileTap={{ scale: 0.97 }}
            onClick={() => onSend?.(`I want to: ${s.label}`)}
            style={suggestionCard}
          >
            <span style={suggestionIcon}>{s.icon}</span>
            <span style={suggestionTitle}>{s.label}</span>
            <span style={suggestionSub}>{s.sub}</span>
          </motion.button>
        ))}
      </motion.div>

      {/* Intelligence strip */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 1 }}
        style={intelRow}
      >
        {defaultIntel.map(ind => (
          <button key={ind.label} style={intelCard}>
            <span style={intelLabel}>{ind.label}</span>
            <span style={intelValue}>{ind.value}</span>
          </button>
        ))}
      </motion.div>
    </div>
  )
}

/* ---- Styles ---- */

const container: React.CSSProperties = {
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 'clamp(40px, 8vh, 100px) 24px 48px',
  overflowY: 'auto',
  gap: 0,
}

const heroText: React.CSSProperties = {
  margin: 0,
  fontWeight: 300,
  fontSize: 'clamp(34px, 5vw, 60px)',
  letterSpacing: '-0.04em',
  lineHeight: 1.1,
  color: 'var(--nova-white)',
}

const subText: React.CSSProperties = {
  margin: '10px 0 0',
  fontSize: 16,
  color: 'var(--nova-lunar)',
  fontWeight: 400,
  letterSpacing: '.01em',
}

const suggestionsRow: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(3, minmax(180px, 220px))',
  gap: 12,
  width: 'min(720px, 90vw)',
  marginBottom: 28,
}

const suggestionCard: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'flex-start',
  gap: 6,
  padding: '16px 18px',
  border: '1px solid var(--nova-line)',
  borderRadius: 14,
  background: 'var(--nova-glass)',
  WebkitBackdropFilter: 'blur(18px)',
  backdropFilter: 'blur(18px)',
  cursor: 'pointer',
  textAlign: 'left',
  transition: 'border-color .2s, box-shadow .3s',
}

const suggestionIcon: React.CSSProperties = { fontSize: 20, lineHeight: 1 }
const suggestionTitle: React.CSSProperties = { fontSize: 13, fontWeight: 600, color: 'var(--nova-white)', lineHeight: 1.3 }
const suggestionSub: React.CSSProperties = { fontSize: 11, color: 'var(--nova-lunar)', lineHeight: 1.4 }

const intelRow: React.CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(4, minmax(120px, 160px))',
  gap: 10,
  width: 'min(660px, 88vw)',
}

const intelCard: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: 4,
  padding: '12px 10px',
  border: '1px solid var(--nova-line)',
  borderRadius: 12,
  background: 'rgba(10, 12, 22, .35)',
  cursor: 'pointer',
  textAlign: 'center',
}

const intelLabel: React.CSSProperties = {
  fontSize: 10, fontWeight: 600, letterSpacing: '.12em',
  textTransform: 'uppercase' as const, color: 'var(--nova-lunar)',
}
const intelValue: React.CSSProperties = {
  fontSize: 14, fontWeight: 400, color: 'var(--nova-white)',
}
