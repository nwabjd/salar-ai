import React, { useCallback, useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bell, AlertTriangle, Rocket, Activity, ServerCog, Mail, Circle, CheckCheck } from 'lucide-react'

/* ============================================================
   CONTEXT SYSTEM — Notification Center.
   Floating drawer (hidden by default) reveals intel, alerts,
   mission and system updates from the Notification API.
   ============================================================ */

export interface NovaNotification {
  id: string
  kind: 'intel' | 'alert' | 'mission' | 'system' | 'email'
  title: string
  body?: string
  link?: string
  severity?: 'info' | 'success' | 'warning' | 'critical'
  is_read?: boolean
  created_at?: string
}

const KIND_META: Record<NovaNotification['kind'], { icon: React.ReactNode; color: string }> = {
  intel: { icon: <Activity size={13}/>, color: 'var(--nova-cyan)' },
  alert: { icon: <AlertTriangle size={13}/>, color: 'var(--nova-amber)' },
  mission: { icon: <Rocket size={13}/>, color: 'var(--nova-violet)' },
  system: { icon: <ServerCog size={13}/>, color: 'var(--nova-mint)' },
  email: { icon: <Mail size={13}/>, color: 'var(--nova-coral)' },
}

interface NotificationCenterProps {
  api: any
}

export default function NotificationCenter({ api }: NotificationCenterProps) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NovaNotification[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const refresh = useCallback(async () => {
    try {
      const [list, count] = await Promise.all([
        api.notifications(20),
        api.notificationUnreadCount(),
      ])
      setItems(list || [])
      setUnread(count?.count ?? 0)
    } catch { /* notifications unavailable */ }
  }, [api])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 30000)
    return () => clearInterval(t)
  }, [refresh])

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const markAll = async () => {
    try {
      await api.markAllNotificationsRead()
      setItems(prev => prev.map(n => ({ ...n, is_read: true })))
      setUnread(0)
    } catch { /* ignore */ }
  }

  const markRead = async (id: string) => {
    try {
      await api.markNotificationRead(id)
      setItems(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
      setUnread(prev => Math.max(0, prev - 1))
    } catch { /* ignore */ }
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {/* Bell trigger */}
      <button
        onClick={() => { setOpen(o => !o); if (!open) refresh() }}
        aria-label="Notifications"
        style={{
          position: 'relative', width: 36, height: 36, borderRadius: 12,
          display: 'grid', placeItems: 'center',
          background: 'var(--nova-glass)',
          WebkitBackdropFilter: 'blur(16px)', backdropFilter: 'blur(16px)',
          border: '1px solid var(--nova-line)',
          color: unread > 0 ? 'var(--nova-white)' : 'var(--nova-lunar)',
          cursor: 'pointer',
        }}
      >
        <Bell size={15}/>
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: 5, right: 5,
            width: 9, height: 9, borderRadius: '50%',
            background: 'var(--nova-coral)',
            boxShadow: '0 0 10px rgba(255,113,133,.7)',
          }}/>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.97 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="nova-solid"
            style={{
              position: 'absolute', top: 46, right: 0, width: 360,
              maxHeight: '70vh', overflowY: 'auto',
              borderRadius: 16, zIndex: 100,
              display: 'flex', flexDirection: 'column',
            }}
          >
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '14px 16px', borderBottom: '1px solid var(--nova-line)',
            }}>
              <span className="nova-meta">NOTIFICATIONS</span>
              {unread > 0 && (
                <button onClick={markAll} style={{
                  display: 'flex', alignItems: 'center', gap: 5,
                  background: 'transparent', border: 'none',
                  color: 'var(--nova-violet)', fontSize: 10.5, cursor: 'pointer',
                  letterSpacing: '.06em',
                }}>
                  <CheckCheck size={13}/> MARK ALL READ
                </button>
              )}
            </div>

            {items.length === 0 ? (
              <div style={{ padding: '32px 20px', textAlign: 'center', fontSize: 12.5, color: 'var(--nova-lunar)' }}>
                {loading ? 'Loading…' : 'No notifications yet.'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {items.map(n => {
                  const meta = KIND_META[n.kind] ?? KIND_META.system
                  const isUnread = !n.is_read
                  const critical = n.severity === 'critical' || n.severity === 'warning'
                  return (
                    <button
                      key={n.id}
                      onClick={() => markRead(n.id)}
                      style={{
                        display: 'flex', gap: 11, padding: '12px 16px', textAlign: 'left',
                        background: isUnread ? 'rgba(255,255,255,.025)' : 'transparent',
                        border: 'none', borderBottom: '1px solid var(--nova-line)',
                        cursor: 'pointer',
                      }}
                    >
                      <span style={{
                        width: 30, height: 30, borderRadius: 10, flexShrink: 0,
                        display: 'grid', placeItems: 'center',
                        background: `color-mix(in srgb, ${meta.color} 12%, transparent)`,
                        color: meta.color, fontSize: 13,
                      }}>
                        {meta.icon}
                      </span>
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{
                          display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3,
                        }}>
                          <span style={{
                            fontSize: 12, fontWeight: 600, color: 'var(--nova-white)',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>{n.title}</span>
                          {critical && <span style={{ fontSize: 8, color: 'var(--nova-coral)' }}>▲</span>}
                        </span>
                        {n.body && (
                          <span style={{
                            fontSize: 11.5, color: 'var(--nova-lunar)', lineHeight: 1.5,
                            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                          }}>{n.body}</span>
                        )}
                        {n.created_at && (
                          <span style={{ display: 'block', marginTop: 4, fontSize: 9.5, color: 'var(--nova-violet)', letterSpacing: '.05em' }}>
                            {new Date(n.created_at).toLocaleString()}
                          </span>
                        )}
                      </span>
                      {isUnread && <Circle size={8} fill="var(--nova-cyan)" style={{ color: 'transparent', flexShrink: 0, marginTop: 3 }}/>}
                    </button>
                  )
                })}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
