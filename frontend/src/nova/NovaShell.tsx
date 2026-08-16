import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import NovaBackground from './NovaBackground'
import NovaRail from './NovaRail'
import HomeScreen from './HomeScreen'
import QuantumEngine from './quantum/QuantumEngine'
import { MissionCenter } from './missions'
import { SpacesOverview, SpaceContainer, DEFAULT_SPACES } from './spaces'
import { NotificationCenter, PermissionOverlay, ContextDock } from './context'
import AgentCenter from './agents/AgentCenter'
import type { PermissionRequest } from './context'
import type { RailView } from './NovaRail'
import type { SpaceKind } from './spaces'
import type { SalarApi, Message, Conversation } from '../api'

/* ============================================================
   NOVA SHELL — The top-level Nova layout.
   Layout: NovaRail | Main content area | Context Dock (hidden by default).
   ============================================================ */

type CoreState = 'idle' | 'listening' | 'understanding' | 'thinking'
  | 'planning' | 'acting' | 'verifying' | 'waiting'
  | 'warning' | 'error' | 'complete'

interface ShellProps {
  api: SalarApi
  onLive?: () => void
  onSignOut?: () => void
  onExitNova?: () => void
}

export default function NovaShell({ api, onLive, onSignOut, onExitNova }: ShellProps) {
  const [view, setView] = useState<RailView>('quantum')
  const [openSpace, setOpenSpace] = useState<SpaceKind | null>(null)
  const [coreState, setCoreState] = useState<CoreState>('idle')
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [permission, setPermission] = useState<PermissionRequest | null>(null)
  const [pendingText, setPendingText] = useState('')

  const navigate = (next: RailView) => {
    setOpenSpace(null)
    setView(next)
  }

  const handleSend = async (text: string, approved?: boolean) => {
    if (!text.trim()) return

    // Context gate: high-stakes intents pause for explicit approval.
    const highRisk = /(delete|wipe|erase|kill|terminate|shut ?down|remove|uninstall|send (money|payment)|transfer|cancel|permanent)/i.test(text)
    if (highRisk && !approved) {
      setPendingText(text)
      setPermission({
        id: 'risk-' + Date.now(),
        title: 'High-stakes action detected',
        description: `Salaar intends to act on: "${text.slice(0, 90)}${text.length > 90 ? '…' : ''}"`,
        detail: 'This action is classified as high-stakes. Salaar will not commit until you approve it here.',
        confidence: 0.82,
        irreversible: /(delete|wipe|erase|permanent|uninstall|terminate)/i.test(text),
      })
      return
    }

    if (!conversation) {
      try {
        const list = await api.conversations()
        const conv = list[0] || await api.createConversation()
        setConversation(conv)
        if (list[0]) {
          const detail = await api.conversation(conv.id)
          setMessages(detail.messages || [])
        }
      } catch {
        setConversation({ id: 'temp', title: 'Nova chat' })
      }
    }

    const userMsg: Message = {
      id: 'tmp-' + Date.now(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setCoreState('thinking')

    const convId = conversation?.id || 'temp'
    const streamBuf: string[] = []

    try {
      await api.chatStream(convId, text,
        (token) => {
          streamBuf.push(token)
          setCoreState('thinking')
        },
        (messageId, createdAt) => {
          const reply = streamBuf.join('')
          setMessages(prev => [...prev.slice(0, -1), userMsg, {
            id: messageId, role: 'assistant', content: reply, created_at: createdAt,
          }])
          setCoreState('complete')
          setTimeout(() => setCoreState('idle'), 1800)
        },
        (err) => {
          console.error('Nova stream error:', err)
          setCoreState('error')
          setTimeout(() => setCoreState('idle'), 2500)
        },
        () => setCoreState('acting'),
        () => {},
      )
    } catch {
      setCoreState('error')
      setTimeout(() => setCoreState('idle'), 2500)
    }
  }

  const handleVoice = () => {
    onLive?.()
  }

  const handleApprove = () => {
    const text = pendingText
    setPendingText('')
    setPermission(null)
    if (text) handleSend(text, true)
  }

  const handleDeny = () => {
    setPendingText('')
    setPermission(null)
    setCoreState('complete')
    setTimeout(() => setCoreState('idle'), 1200)
  }

  return (
    <div className="nova-shell" style={{
      position: 'fixed',
      inset: 0,
      overflow: 'hidden',
      color: 'var(--nova-white)',
      fontFamily: 'var(--nova-font-sans)',
    }}>
      <NovaBackground/>
      <NovaRail active={view} onNavigate={setView}/>

      {/* Main content area */}
      <motion.main
        className="nova-main"
        style={{
          position: 'relative',
          zIndex: 1,
          marginLeft: 56,
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
        }}
      >
        <AnimatePresence mode="wait">
          {view === 'quantum' && (
            <QuantumEngine key="quantum" api={api} onExitNova={onExitNova}/>
          )}
          {view === 'home' && (
            <HomeScreen
              key="home"
              coreState={coreState}
              onSend={handleSend}
              onVoice={handleVoice}
              onCoreClick={handleVoice}
            />
          )}
          {view === 'missions' && (
            <MissionCenter key="missions" api={api}/>
          )}
          {view === 'agents' && (
            <AgentCenter key="agents" api={api}/>
          )}
          {view === 'spaces' && openSpace === null && (
            <SpacesOverview
              key="spaces"
              spaces={DEFAULT_SPACES}
              onOpenSpace={kind => setOpenSpace(kind)}
              onCreateSpace={() => setOpenSpace('development')}
            />
          )}
          {view === 'spaces' && openSpace !== null && (
            <SpaceContainer
              key={`space-${openSpace}`}
              kind={openSpace}
              api={api}
              onSend={handleSend}
              onBack={() => setOpenSpace(null)}
            />
          )}
          {view !== 'home' && view !== 'missions' && view !== 'spaces' && view !== 'agents' && (
            <NovaViewPlaceholder key={view} view={view}/>
          )}
        </AnimatePresence>
      </motion.main>

      {/* Context System */}
      <div style={{ position: 'fixed', right: 18, top: 18, zIndex: 90 }}>
        <NotificationCenter api={api}/>
      </div>

      <ContextDock view={view}/>

      <PermissionOverlay
        request={permission}
        onApprove={handleApprove}
        onDeny={handleDeny}
      />

      {/* Exit Nova toggle */}
      <button
        onClick={onExitNova}
        aria-label="Exit Nova mode"
        style={{
          position: 'fixed', right: 62, top: 18, zIndex: 50,
          padding: '7px 14px', borderRadius: 12,
          background: 'var(--nova-glass)',
          WebkitBackdropFilter: 'blur(16px)',
          backdropFilter: 'blur(16px)',
          border: '1px solid var(--nova-line)',
          color: 'var(--nova-lunar)',
          fontSize: 10, letterSpacing: '.1em',
          cursor: 'pointer',
          textTransform: 'uppercase' as const,
        }}
      >
        CLASSIC VIEW
      </button>
    </div>
  )
}

/* ---- Placeholder views for non-Home screens ---- */
function NovaViewPlaceholder({ view }: { view: RailView }) {
  const labels: Record<RailView, string> = {
    quantum: '',
    home: '',
    spaces: 'Spaces — Coming soon',
    missions: 'Missions — Coming soon',
    agents: 'Agents — Coming soon',
    memory: 'Memory — Coming soon',
    devices: 'Devices — Coming soon',
    system: 'System — Coming soon',
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -16 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 12,
      }}
    >
      <h2 style={{
        fontSize: 'clamp(24px, 3vw, 34px)',
        fontWeight: 300,
        letterSpacing: '-0.03em',
        color: 'var(--nova-white)',
      }}>{labels[view]}</h2>
      <p style={{ fontSize: 13, color: 'var(--nova-lunar)' }}>
        This section of Salaar Nova is under construction.
      </p>
    </motion.div>
  )
}
