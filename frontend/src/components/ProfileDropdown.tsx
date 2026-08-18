import React, { useEffect, useRef, useState } from 'react'
import { CreditCard, FileText, LogOut, Settings, User, ChevronRight } from 'lucide-react'

interface Profile {
  name: string
  email: string
  avatar: string
  subscription?: string
  model?: string
}

interface ProfileDropdownProps {
  data?: Profile
  onSignOut: () => void
  onShowPricing?: () => void
  className?: string
}

export default function ProfileDropdown({ data, onSignOut, onShowPricing, className = '' }: ProfileDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const profile: Profile = data || {
    name: 'JD',
    email: 'jd@salaar.cloud',
    avatar: '',
    subscription: 'PRO',
    model: 'Gemini 2.0 Flash',
  }

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setIsOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const menuItems = [
    { label: 'Profile', icon: <User size={15} />, onClick: () => setIsOpen(false) },
    { label: 'Model', value: profile.model, icon: <span className="pd-icon-dot pd-dot-blue" />, onClick: () => setIsOpen(false) },
    { label: 'Subscription', value: profile.subscription, icon: <CreditCard size={15} />, onClick: () => { setIsOpen(false); onShowPricing?.() } },
    { label: 'Settings', icon: <Settings size={15} />, onClick: () => setIsOpen(false) },
    { label: 'Terms & Policies', icon: <FileText size={15} />, onClick: () => setIsOpen(false) },
  ]

  return (
    <div className={`pd-wrap ${className}`} ref={ref}>
      <button className="pd-trigger" onClick={() => setIsOpen((v) => !v)}>
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

          <button className="pd-item pd-logout" onClick={() => { setIsOpen(false); onSignOut() }}>
            <LogOut size={15} />
            <span>Sign Out</span>
          </button>
        </div>
      )}
    </div>
  )
}
