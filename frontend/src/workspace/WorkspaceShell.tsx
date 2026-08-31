import { useEffect, useRef, useState } from 'react'
import { SalarApi, type Conversation, type Message } from '../api'
import { IntelModeProvider, useIntelMode } from './intel-mode'
import Sidebar, { VIEWS, readCollapsed, type WorkspaceView } from './Sidebar'
import Topbar from './Topbar'
import HomeView from './HomeView'
import ChatView from './ChatView'
import MemoryView from './MemoryView'
import ProjectsView from './ProjectsView'
import ResearchView from './ResearchView'
import CodeView from './CodeView'
import AutomationsView from './AutomationsView'
import CommandsView from './CommandsView'
import FilesView from './FilesView'
import ScreenshotIntelView from './ScreenshotIntelView'
import { useSettings } from '../contexts/SettingsContext'


function SettingsView({ onShowPricing, onShowTerms, onSignOut, onEnterNova, onEnterClassic }: {
  onShowPricing: () => void
  onShowTerms: () => void
  onSignOut: () => void
  onEnterNova: () => void
  onEnterClassic: () => void
}) {
  const { settings, toggle } = useSettings()
  const rows = [
    { key: 'notifications' as const, label: 'Notifications', hint: 'Surface important alerts and intel.' },
    { key: 'soundEffects' as const, label: 'Sound effects', hint: 'Subtle audio feedback on key actions.' },
    { key: 'streaming' as const, label: 'Streaming responses', hint: 'Display answers as they arrive.' },
  ]
  return (
    <div className="ws-scroll ws-settings">
      <h2 style={{ fontSize: 20, fontWeight: 650, letterSpacing: '-0.01em', margin: '0 0 20px' }}>Settings</h2>
      <div className="ws-settings__group">
        <h3>Experience</h3>
        <p>Preferences are stored locally on this device.</p>
        {rows.map((r) => (
          <div key={r.key} className="ws-row">
            <div>
              <div className="ws-row__label">{r.label}</div>
              <div className="ws-row__hint">{r.hint}</div>
            </div>
            <button
              className={`ws-switch${settings[r.key] ? ' is-on' : ''}`}
              onClick={() => toggle(r.key)}
              role="switch"
              aria-checked={settings[r.key]}
              aria-label={r.label}
            >
              <i />
            </button>
          </div>
        ))}
      </div>
      <div className="ws-settings__group">
        <h3>Interface</h3>
        <p>Salaar ships three surfaces. This premium workspace is the default.</p>
        <div className="ws-row">
          <div>
            <div className="ws-row__label">Premium workspace</div>
            <div className="ws-row__hint">Home, chat, projects, research — this surface.</div>
          </div>
          <span className="ws-row__tag">active</span>
        </div>
        <div className="ws-row">
          <div>
            <div className="ws-row__label">Nova / Quantum</div>
            <div className="ws-row__hint">Spaces, missions and the agent swarm.</div>
          </div>
          <button className="ws-quick" onClick={onEnterNova}>Open</button>
        </div>
        <div className="ws-row">
          <div>
            <div className="ws-row__label">Classic</div>
            <div className="ws-row__hint">The original single-conversation chat.</div>
          </div>
          <button className="ws-quick" onClick={onEnterClassic}>Open</button>
        </div>
      </div>
      <div className="ws-settings__group">
        <h3>Account</h3>
        <div className="ws-row">
          <div>
            <div className="ws-row__label">Plan & billing</div>
            <div className="ws-row__hint">Manage your subscription.</div>
          </div>
          <button className="ws-quick" onClick={onShowPricing}>Open</button>
        </div>
        <div className="ws-row">
          <div>
            <div className="ws-row__label">Terms & help</div>
            <div className="ws-row__hint">Read the terms and get support.</div>
          </div>
          <button className="ws-quick" onClick={onShowTerms}>Open</button>
        </div>
        <div className="ws-row">
          <div>
            <div className="ws-row__label">Sign out</div>
            <div className="ws-row__hint">End this session.</div>
          </div>
          <button className="ws-quick" onClick={onSignOut}>Sign out</button>
        </div>
      </div>
    </div>
  )
}

interface ShellProps {
  api: SalarApi
  onShowPricing: () => void
  onShowTerms: () => void
  onSignOut: () => void
  onLive: () => void
  usageLabel?: string
  displayName?: string
  email?: string
  onEnterNova: () => void
  onEnterClassic: () => void
}

function parseView(raw: string | null): WorkspaceView {
  const v = String(raw || '/home').replace(/^#?\/?/, '') as WorkspaceView
  return VIEWS.some((item) => item.id === v) ? v : 'home'
}

function ShellInner({ api, onShowPricing, onShowTerms, onSignOut, onLive, usageLabel, displayName, email, onEnterNova, onEnterClassic }: ShellProps) {
  const [view, setView] = useState<WorkspaceView>(() => parseView(window.location.hash))
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [mobileNav, setMobileNav] = useState(false)
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [busy, setBusy] = useState(false)
  const [streamingPartial, setStreamingPartial] = useState('')
  const [error, setError] = useState('')
  const [toolActivity, setToolActivity] = useState<{ tool: string; args?: Record<string, unknown>; result?: Record<string, unknown> } | null>(null)
  const { fast, prefix } = useIntelMode()
  const streamBuf = useRef('')
  const lastUserRef = useRef<Message | null>(null)

  useEffect(() => {
    const onHash = () => setView(parseView(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const loadLatest = async () => {
    try {
      const list = await api.conversations()
      if (!list || list.length === 0) return
      const c = await api.conversation(list[0].id)
      setConversation(c)
      setMessages(c.messages || [])
    } catch { /* backend unavailable — stay empty */ }
  }

  useEffect(() => {
    void loadLatest()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const startNew = async () => {
    setError('')
    setStreamingPartial('')
    setToolActivity(null)
    setBusy(false)
    try {
      const c = await api.createConversation()
      setConversation(c)
      setMessages([])
      lastUserRef.current = null
      setView('chat')
      window.location.hash = '/chat'
    } catch (e) {
      setError((e as Error).message || 'Could not start a conversation')
    }
  }

  const loadConversation = async (id: string) => {
    try {
      const c = await api.conversation(id)
      setConversation(c)
      setMessages(c.messages || [])
      setError('')
    } catch (e) {
      setError((e as Error).message || 'Could not load conversation')
    }
  }

  const send = async (text: string, files: File[]) => {
    if (!text.trim() && files.length === 0) return
    if (busy) return
    setError('')
    setToolActivity(null)

    let uploaded = ''
    if (files.length > 0) {
      try {
        const attachments = await api.uploadAttachments(files)
        if (attachments.length) {
          uploaded = `\n[Uploaded: ${attachments.map((d) => d.filename).join(', ')}]`
          const analyzed = attachments.filter((a) => a.analysis)
          if (analyzed.length) {
            const summaries = analyzed
              .map((a) => `- ${a.filename}: ${(a.analysis || '').split('\n')[0].slice(0, 200)}`)
            uploaded += `\nAnalyzed with:\n${summaries.join('\n')}`
          }
        }
      } catch {
        uploaded = `\n[Attached ${files.length} file(s) — upload failed, continuing without them]`
      }
    }

    let conv = conversation
    if (!conv) {
      try {
        conv = await api.createConversation(text.slice(0, 48) || 'Conversation')
        setConversation(conv)
      } catch (e) {
        setError((e as Error).message || 'Could not start a conversation')
        return
      }
    }

    const full = text + uploaded
    const userMsg: Message = {
      id: `local-${Date.now()}`,
      role: 'user',
      content: full,
      created_at: new Date().toISOString(),
    }
    lastUserRef.current = userMsg
    const desired = prefix ? `${prefix}\n\n${text}` : text
    setMessages((prev) => [...prev, userMsg])
    setBusy(true)
    setStreamingPartial('')
    streamBuf.current = ''

    const onAsrMessage = async (mid: string, createdAt: string) => {
      setMessages((prev) => {
        const withAssistant = [...prev]
        const clean = withAssistant[withAssistant.length - 1]?.role === 'assistant' ? withAssistant.slice(0, -1) : withAssistant
        return [...clean, { id: mid, role: 'assistant', content: streamBuf.current, created_at: createdAt }]
      })
      setStreamingPartial('')
      setBusy(false)
    }

    api.chatStream(
      conv.id,
      desired,
      (token) => {
        streamBuf.current += token
        setStreamingPartial(streamBuf.current)
      },
      onAsrMessage,
      (err) => {
        const msg = String(err?.message || err)
        const friendly = msg.includes('quota') || msg.includes('Authentication')
          ? msg
          : 'Salaar couldn’t complete that request.'
        setError(msg.includes('quota') || msg.includes('Authentication') ? msg : friendly)
        setMessages((prev) => [...prev, { id: `err-${Date.now()}`, role: 'assistant', content: '', created_at: new Date().toISOString() }])
        setStreamingPartial('')
        setBusy(false)
      },
      (tool, args) => setToolActivity({ tool, args }),
      (tool, result) => setToolActivity({ tool, result }),
      fast,
    )
  }

  const retry = () => {
    if (lastUserRef.current) {
      const text = lastUserRef.current.content
      setMessages((prev) => prev.filter((m) => m.id !== lastUserRef.current!.id))
      void send(text, [])
    } else {
      setError('')
    }
  }

  const stop = () => setBusy(false)

  const navigateTo = (v: WorkspaceView) => {
    setView(v)
    window.location.hash = `/${v}`
  }

  const goChat = () => {
    setView('chat')
    window.location.hash = '/chat'
  }

  return (
    <div className="workspace-shell">
      <Sidebar
        view={view}
        onNavigate={navigateTo}
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((c) => !c)}
        onShowPricing={onShowPricing}
        onShowTerms={onShowTerms}
        onSignOut={onSignOut}
        usageLabel={usageLabel}
        displayName={displayName}
        email={email}
      />
      {mobileNav && (
        <>
          <div className="ws-backdrop" onClick={() => setMobileNav(false)} />
          <div className="ws-mobile-drawer" style={{ width: 'var(--ws-rail-w)', height: '100%' }}>
            <Sidebar
              view={view}
              onNavigate={navigateTo}
              collapsed={false}
              onToggleCollapsed={() => {}}
              onShowPricing={onShowPricing}
              onShowTerms={onShowTerms}
              onSignOut={onSignOut}
              usageLabel={usageLabel}
              displayName={displayName}
              email={email}
              onNavigateDone={() => setMobileNav(false)}
            />
          </div>
        </>
      )}
      <div className="ws-main">
        <Topbar
          view={view}
          usageLabel={usageLabel}
          onShowPricing={onShowPricing}
          onSignOut={onSignOut}
          onLive={onLive}
          onOpenMobileNav={() => setMobileNav(true)}
        />
        {view === 'home' && <HomeView api={api} onSend={(t, f) => { void send(t, f); goChat() }} onStartChat={goChat} />}
        {view === 'chat' && (
          <ChatView
            apiConversation={conversation}
            messages={messages}
            busy={busy}
            streamingPartial={streamingPartial}
            toolActivity={toolActivity}
            error={error}
            onSend={(t, f) => void send(t, f)}
            onStop={stop}
            onRetry={() => { void retry() }}
            onNewChat={() => { void startNew() }}
            onAttachFiles={() => {}}
          />
        )}
        {view === 'settings' && <SettingsView onShowPricing={onShowPricing} onShowTerms={onShowTerms} onSignOut={onSignOut} onEnterNova={onEnterNova} onEnterClassic={onEnterClassic} />}
        {view === 'memory' && <MemoryView api={api} />}
        {view === 'projects' && <ProjectsView api={api} />}
        {view === 'research' && <ResearchView api={api} />}
        {view === 'vision' && <ScreenshotIntelView api={api} />}
        {view === 'automations' && <AutomationsView api={api} />}
        {view === 'commands' && <CommandsView api={api} />}
        {view === 'files' && <FilesView api={api} />}
        {view === 'code' && <CodeView api={api} />}
      </div>
    </div>
  )
}

export default function WorkspaceShell(props: ShellProps) {
  return (
    <IntelModeProvider>
      <ShellInner {...props} />
    </IntelModeProvider>
  )
}