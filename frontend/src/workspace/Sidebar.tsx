import { useEffect, useState } from 'react'
import {
  Bot, ChevronLeft, ChevronRight, Code2, FileBox,
  FolderKanban, HelpCircle, Home, MessageSquare,
  Network, Rocket,
  ScanLine, Search, Settings, Wrench,
} from 'lucide-react'

export type WorkspaceView =
  | 'home'
  | 'chat'
  | 'projects'
  | 'research'
  | 'code'
  | 'files'
  | 'automations'
  | 'commands'
  | 'settings'
  | 'memory'
  | 'vision'

export interface ViewItem {
  id: WorkspaceView
  label: string
  icon: typeof Home
  section: 'workspace' | 'system'
}

export const VIEWS: ViewItem[] = [
  { id: 'home', label: 'Home', icon: Home, section: 'workspace' },
  { id: 'chat', label: 'Chat', icon: MessageSquare, section: 'workspace' },
  { id: 'projects', label: 'Projects', icon: FolderKanban, section: 'workspace' },
  { id: 'research', label: 'Research', icon: Search, section: 'workspace' },
  { id: 'code', label: 'Code', icon: Code2, section: 'workspace' },
  { id: 'files', label: 'Files', icon: FileBox, section: 'workspace' },
  { id: 'automations', label: 'Automations', icon: Wrench, section: 'workspace' },
  { id: 'commands', label: 'Commands', icon: Rocket, section: 'workspace' },
  { id: 'memory', label: 'Memory', icon: Network, section: 'workspace' },
  { id: 'settings', label: 'Settings', icon: Settings, section: 'system' },
]

const NAV_KEY = 'salaar.rail-collapsed'

export function readCollapsed(): boolean {
  try {
    return localStorage.getItem(NAV_KEY) === '1'
  } catch {
    return false
  }
}

interface SidebarProps {
  view: WorkspaceView
  onNavigate: (v: WorkspaceView) => void
  collapsed: boolean
  onToggleCollapsed: () => void
  onShowPricing: () => void
  onShowTerms: () => void
  onSignOut: () => void
  usageLabel?: string
  displayName?: string
  email?: string
  onNavigateDone?: () => void
}

export default function Sidebar({
  view, onNavigate, collapsed, onToggleCollapsed,
  onShowPricing, onShowTerms, onSignOut, usageLabel, displayName, email, onNavigateDone,
}: SidebarProps) {
  const [searchOpen, setSearchOpen] = useState(false)

  const go = (v: WorkspaceView) => {
    onNavigate(v)
    onNavigateDone?.()
  }

  useEffect(() => {
    try {
      localStorage.setItem(NAV_KEY, collapsed ? '1' : '0')
    } catch { /* ignore */ }
  }, [collapsed])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'b') {
        e.preventDefault()
        onToggleCollapsed()
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen((v) => !v)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onToggleCollapsed])

  const renderItem = (item: ViewItem) => {
    const Icon = item.icon
    const label = item.label
    return (
      <button
        key={item.id}
        className={`ws-rail__item${view === item.id ? ' is-active' : ''}`}
        onClick={() => go(item.id)}
        title={collapsed ? label : undefined}
        aria-current={view === item.id ? 'page' : undefined}
      >
        <span className="ws-rail__icon"><Icon size={17} strokeWidth={1.9} /></span>
        <span className="ws-rail__label">{label}</span>
      </button>
    )
  }

  return (
    <aside className="ws-rail" style={{ width: collapsed ? 'var(--ws-rail-w-collapsed)' : 'var(--ws-rail-w)' }} aria-label="Workspace navigation">
      <div className="ws-rail__brand">
        <div className="ws-rail__glyph">S</div>
        {!collapsed && (
          <div className="ws-rail__brand-name">
            <b>SALAR</b>
            <span>workspace</span>
          </div>
        )}
      </div>

      {searchOpen && !collapsed && (
        <div className="ws-rail__search">
          <Search size={14} />
          <input autoFocus placeholder="Search…" aria-label="Search" />
        </div>
      )}

      <div className="ws-rail__nav">
        <span className="ws-rail__section">{collapsed ? '·' : 'Workspace'}</span>
        {VIEWS.filter((v) => v.section === 'workspace').map(renderItem)}
        <span className="ws-rail__section">{collapsed ? '·' : 'System'}</span>
        <button className={`ws-rail__item${view === 'settings' ? ' is-active' : ''}`} onClick={() => go('settings')} title={collapsed ? 'Settings' : undefined}>
          <span className="ws-rail__icon"><Settings size={17} strokeWidth={1.9} /></span>
          <span className="ws-rail__label">Settings</span>
        </button>
        <button className="ws-rail__item" onClick={onShowPricing} title={collapsed ? 'Plan & billing' : undefined}>
          <span className="ws-rail__icon"><Bot size={17} strokeWidth={1.9} /></span>
          <span className="ws-rail__label">Plan & billing</span>
        </button>
        <button className="ws-rail__item" onClick={onShowTerms} title={collapsed ? 'Help' : undefined}>
          <span className="ws-rail__icon"><HelpCircle size={17} strokeWidth={1.9} /></span>
          <span className="ws-rail__label">Terms & help</span>
        </button>
      </div>

      <div className="ws-rail__foot">
        {!collapsed && (
          <div className="ws-rail__profile">
            <div className="ws-rail__avatar">{(displayName || 'U').slice(0, 1).toUpperCase()}</div>
            <div className="ws-rail__profile-info">
              <b>{displayName || 'User'}</b>
              <span>{email || 'SALAAR'}{usageLabel ? ` · ${usageLabel}` : ''}</span>
            </div>
          </div>
        )}
        <button className="ws-rail__collapse" onClick={onToggleCollapsed} title={collapsed ? "Expand sidebar (Ctrl+B)" : "Collapse sidebar (Ctrl+B)"}>
          {collapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
          <span>{collapsed ? "Expand" : "Collapse"}</span>
        </button>
      </div>
    </aside>
  )
}