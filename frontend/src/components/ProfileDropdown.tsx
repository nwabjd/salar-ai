import React, { useEffect, useRef, useState } from 'react'
import { CreditCard, FileText, LogOut, Settings, User, ChevronRight, ArrowLeft, Check } from 'lucide-react'
import { useMode, SalaarMode, MODE_INFO } from '../contexts/ModeContext'
import { useSettings } from '../contexts/SettingsContext'

interface Profile {
  name: string
  email: string
  avatar: string
  subscription?: string
}

interface ProfileDropdownProps {
  data?: Profile
  onSignOut: () => void
  onShowPricing?: () => void
  onShowTerms?: () => void
  className?: string
}

type Panel = 'main' | 'profile' | 'model' | 'settings'

export default function ProfileDropdown({ data, onSignOut, onShowPricing, onShowTerms, className = '' }: ProfileDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [panel, setPanel] = useState<Panel>('main')
  const ref = useRef<HTMLDivElement>(null)
  const { mode, setMode } = useMode()
  const { settings, toggle } = useSettings()

  const profile: Profile = data || {
    name: 'JD',
    email: 'jd@salaar.cloud',
    avatar: '',
    subscription: 'PRO',
  }

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false)
        setTimeout(() => setPanel('main'), 200)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const close = () => {
    setIsOpen(false)
    setTimeout(() => setPanel('main'), 200)
  }

  const openPanel = (p: Panel) => setPanel(p)

  const menuItems = [
    { label: 'Profile', icon: <User size={15} />, onClick: () => openPanel('profile') },
    { label: 'Model', value: MODE_INFO[mode].label, icon: <span className="pd-icon-dot pd-dot-blue" />, onClick: () => openPanel('model') },
    { label: 'Subscription', value: profile.subscription, icon: <CreditCard size={15} />, onClick: () => { close(); onShowPricing?.() } },
    { label: 'Settings', icon: <Settings size={15} />, onClick: () => openPanel('settings') },
    { label: 'Terms & Policies', icon: <FileText size={15} />, onClick: () => { close(); onShowTerms?.() } },
  ]

  return (
    <div className={`pd-wrap ${className}`} ref={ref}>
      <button className="pd-trigger" onClick={() => { setIsOpen((v) => !v); setPanel('main') }}>
        <div className="pd-info">
          <span className="pd-name">{profile.name}</span>
          <span className="pd-email">{profile.email}</span>
        </div>
        <div className="pd-avatar">
          {profile.avatar
            ? <img src={profile.avatar} alt={profile.name} />
            : <span>{profile.name.charAt(0).toUpperCase()}</span>}
        </div>
      </button>

      {isOpen && (
        <div className="pd-menu">
          {panel === 'main' && (
            <>
              {menuItems.map((item) => (
                <button key={item.label} className="pd-item" onClick={item.onClick}>
                  <div className="pd-item-left">
                    <span className="pd-item-icon">{item.icon}</span>
                    <span className="pd-item-label">{item.label}</span>
                  </div>
                  <div className="pd-item-right">
                    {item.value && (
                      <span className={`pd-badge ${item.label === 'Model' ? 'pd-badge-blue' : 'pd-badge-purple'}`}>
                        {item.value}
                      </span>
                    )}
                    <ChevronRight size={14} className="pd-chevron" />
                  </div>
                </button>
              ))}
              <div className="pd-separator" />
              <button className="pd-item pd-logout" onClick={() => { close(); onSignOut() }}>
                <LogOut size={15} />
                <span>Sign Out</span>
              </button>
            </>
          )}

          {panel === 'profile' && (
            <>
              <div className="pd-panel-header">
                <button className="pd-back" onClick={() => setPanel('main')}><ArrowLeft size={15} /></button>
                <span>Profile</span>
              </div>
              <div className="pd-profile-card">
                <div className="pd-profile-avatar">
                  {profile.avatar ? <img src={profile.avatar} alt={profile.name} /> : <span>{profile.name.charAt(0).toUpperCase()}</span>}
                </div>
                <div className="pd-profile-name">{profile.name}</div>
                <div className="pd-profile-email">{profile.email}</div>
                <div className="pd-profile-badge">{profile.subscription || 'FREE'} Plan</div>
              </div>
            </>
          )}

          {panel === 'model' && (
            <>
              <div className="pd-panel-header">
                <button className="pd-back" onClick={() => setPanel('main')}><ArrowLeft size={15} /></button>
                <span>Model</span>
              </div>
              <div className="pd-mode-list">
                {(Object.keys(MODE_INFO) as SalaarMode[]).map((m) => (
                  <button key={m} className={`pd-mode-card ${mode === m ? 'pd-mode-active' : ''}`} onClick={() => setMode(m)}>
                    <div className="pd-mode-icon">{MODE_INFO[m].icon}</div>
                    <div className="pd-mode-info">
                      <div className="pd-mode-label">{MODE_INFO[m].label}</div>
                      <div className="pd-mode-desc">{MODE_INFO[m].description}</div>
                    </div>
                    {mode === m && <Check size={16} className="pd-mode-check" />}
                  </button>
                ))}
              </div>
            </>
          )}

          {panel === 'settings' && (
            <>
              <div className="pd-panel-header">
                <button className="pd-back" onClick={() => setPanel('main')}><ArrowLeft size={15} /></button>
                <span>Settings</span>
              </div>
              <div className="pd-settings-list">
                <div className="pd-setting-row">
                  <span className="pd-setting-label">Dark Mode</span>
                  <div className={`pd-toggle ${settings.darkMode ? 'on' : ''}`} onClick={() => toggle('darkMode')}><div className="pd-toggle-knob" /></div>
                </div>
                <div className="pd-setting-row">
                  <span className="pd-setting-label">Sound Effects</span>
                  <div className={`pd-toggle ${settings.soundEffects ? 'on' : ''}`} onClick={() => toggle('soundEffects')}><div className="pd-toggle-knob" /></div>
                </div>
                <div className="pd-setting-row">
                  <span className="pd-setting-label">Notifications</span>
                  <div className={`pd-toggle ${settings.notifications ? 'on' : ''}`} onClick={() => toggle('notifications')}><div className="pd-toggle-knob" /></div>
                </div>
                <div className="pd-setting-row">
                  <span className="pd-setting-label">Streaming</span>
                  <div className={`pd-toggle ${settings.streaming ? 'on' : ''}`} onClick={() => toggle('streaming')}><div className="pd-toggle-knob" /></div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
