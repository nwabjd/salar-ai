import { useEffect, useRef, useState } from 'react'
import { Bell, ChevronDown, LogOut, Menu, Mic2, Sparkles } from 'lucide-react'
import { INTEL_MODES, useIntelMode, type IntelMode } from './intel-mode'
import type { WorkspaceView } from './Sidebar'
import { useSettings } from '../contexts/SettingsContext'

interface TopbarProps {
  view: WorkspaceView
  usageLabel?: string
  onShowPricing: () => void
  onSignOut: () => void
  onLive: () => void
  onOpenMobileNav: () => void
}

const viewTitles: Record<WorkspaceView, string> = {
  home: 'Home',
  chat: 'Chat',
  projects: 'Projects',
  research: 'Research',
  code: 'Code',
  files: 'Files',
  automations: 'Automations',
  settings: 'Settings',
  memory: 'Memory',
  vision: 'Vision',
  commands: 'Commands',
}

function ModeSelector() {
  const { mode, setMode } = useIntelMode()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const pick = (m: IntelMode) => {
    setMode(m)
    setOpen(false)
  }

  return (
    <div className="ws-mode" ref={ref}>
      <button className="ws-mode__trigger" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="menu">
        <span className="ws-mode__dot" aria-hidden />
        {mode.toUpperCase()}
        <span className="ws-mode__chevron"><ChevronDown size={13} /></span>
      </button>
      {open && (
        <div className="ws-mode__panel" role="menu">
          <div className="ws-mode__grid">
            {INTEL_MODES.map((m) => (
              <button
                key={m.id}
                role="menuitemradio"
                aria-checked={mode === m.id}
                className={`ws-mode__opt${mode === m.id ? ' is-active' : ''}`}
                onClick={() => pick(m.id)}
              >
                <span className="ws-mode__name">{m.name}</span>
                <span className="ws-mode__hint">{m.hint}</span>
              </button>
            ))}
          </div>
          <div className="ws-mode__note">
            Salaar adapts response depth to the active mode. The backend model router still decides the best model for the job.
          </div>
        </div>
      )}
    </div>
  )
}

export default function Topbar({
  view, usageLabel, onShowPricing, onSignOut, onLive, onOpenMobileNav,
}: TopbarProps) {
  const { settings, toggle } = useSettings()
  return (
    <header className="ws-topbar">
      <button className="ws-icon-btn ws-mobile-nav" onClick={onOpenMobileNav} aria-label="Open menu">
        <Menu size={17} />
      </button>
      <span className="ws-topbar__title">{viewTitles[view]}</span>
      <span className="ws-topbar__spacer" />
      <div className="ws-topbar__actions">
        {usageLabel && (
          <button className="ws-quick ws-quick--usage" onClick={onShowPricing} title="Plan & billing">
            <Sparkles size={12} />
            {usageLabel}
          </button>
        )}
        <ModeSelector />
        <button
          className={`ws-icon-btn${settings.notifications ? ' is-bordered' : ''}`}
          onClick={() => toggle('notifications')}
          title={`Notifications ${settings.notifications ? 'on' : 'off'}`}
          aria-pressed={settings.notifications}
        >
          <Bell size={16} />
        </button>
        <button className="ws-icon-btn" onClick={onLive} title="Voice mode" aria-label="Voice mode">
          <Mic2 size={16} />
        </button>
        <button className="ws-icon-btn" onClick={onSignOut} title="Sign out" aria-label="Sign out">
          <LogOut size={16} />
        </button>
      </div>
    </header>
  )
}