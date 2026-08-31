import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import NovaBackground from './NovaBackground'
import GradientWaves from '../effects/GradientWaves'
import NovaRail from './NovaRail'
import HomeScreen from './HomeScreen'
import QuantumEngine from './quantum/QuantumEngine'
import { MissionCenter } from './missions'
import { SpacesOverview, SpaceContainer, DEFAULT_SPACES } from './spaces'
import { NotificationCenter, PermissionOverlay, ContextDock } from './context'
import AgentCenter from './agents/AgentCenter'
import { MemoryView } from './memory/MemoryView'
import { DevicesView } from './devices/DevicesView'
import { SystemView } from './system/SystemView'
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
  onExitQuantum?: () => void
}

export default function NovaShell({ api, onLive, onSignOut, onExitQuantum }: ShellProps) {
  const [view, setView] = useState<RailView>('home')
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

  const handleSend = async (text: string, _files?: File[]) => {
    if (!text.trim()) return

    // Context gate: high-stakes intents pause for explicit approval.
    const highRisk = /(delete|wipe|erase|kill|terminate|shut ?down|remove|uninstall|send (money|payment)|transfer|cancel|permanent)/i.test(text)
    if (highRisk) {
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

    await sendToAgent(text)
  }

  const sendToAgent = async (text: string) => {
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
        setConversation({ id: 'temp', title: 'Quantum chat' })
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

  const handleAttach = async (files: File[]) => {
    if (!files.length) return
    try {
      await api.uploadFiles(files)
      setCoreState('complete')
      setTimeout(() => setCoreState('idle'), 1600)
    } catch (err) {
      console.error('Upload failed:', err)
      setCoreState('error')
      setTimeout(() => setCoreState('idle'), 2400)
    }
  }

  const handleSign = () => {
    setPermission({
      id: 'sign-' + Date.now(),
      title: 'Document signature',
      description: 'Signing mode is ready. Attach a document to sign it digitally.',
      detail: 'Salaar can capture your signature and embed it into PDF and Office documents.',
      confidence: 0.9,
      irreversible: false,
    })
  }

  const handleApproveSign = () => {
    setPermission(null)
    setCoreState('complete')
    setTimeout(() => setCoreState('idle'), 1600)
  }

  const handleApprove = () => {
    const isSignRequest = permission?.id.startsWith('sign-')
    const text = pendingText
    setPendingText('')
    setPermission(null)
    if (isSignRequest) {
      setCoreState('complete')
      setTimeout(() => setCoreState('idle'), 1600)
      return
    }
    if (text) sendToAgent(text)
  }

  const handleDeny = () => {
    setPendingText('')
    setPermission(null)
    setCoreState('complete')
    setTimeout(() => setCoreState('idle'), 1200)
  }

  if (view === 'quantum') {
    return <QuantumEngine key="quantum" api={api} onExitQuantum={onExitQuantum}/>
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
      <GradientWaves
        className="nova-gradient-bg"
        horizonColor="#e61359"
        waveColor="#ff7ba4"
        crestColor="#ffffff"
        speed={0.4}
        amplitude={2.5}
        waveScale={0.6}
        waveRatio={0.9}
        swell={35}
        turbulence={20}
        tilt={1.11}
        zoom={1.0}
        height={5.5}
        fogDepth={15}
        detail="medium"
        brightness={1.0}
        opacity={1.0}
        mouseInteraction={true}
        parallaxStrength={0.5}
        grain={false}
        grainIntensity={0}
      />
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
          {view === 'home' && (
            <HomeScreen
              key="home"
              coreState={coreState}
              onSend={handleSend}
              onVoice={handleVoice}
              onAttach={handleAttach}
              onSign={handleSign}
              onCoreClick={handleVoice}
            />
          )}
          {view === 'missions' && (
            <MissionCenter key="missions" api={api} />
          )}
          {view === 'agents' && (
            <AgentCenter key="agents" api={api} />
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
          {view === 'memory' && (
            <MemoryView key="memory" api={api} />
          )}
          {view === 'devices' && (
            <DevicesView key="devices" api={api} />
          )}
          {view === 'system' && (
            <SystemView key="system" api={api} />
          )}
          {(['memory', 'devices', 'system', 'quantum', 'home', 'missions', 'spaces', 'agents'] as RailView[]).includes(view) === false && (
            <NovaViewPlaceholder key={view} view={view} />
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

      {/* Exit Quantum toggle */}
      <button
        onClick={onExitQuantum}
        aria-label="Exit Nova mode back to classic view"
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
        This section of Salaar Quantum is under construction.
      </p>
    </motion.div>
  )
}
