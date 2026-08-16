import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const api = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')
const shell = readFileSync(new URL('./nova/NovaShell.tsx', import.meta.url), 'utf8')
const notif = readFileSync(new URL('./nova/context/NotificationCenter.tsx', import.meta.url), 'utf8')
const permission = readFileSync(new URL('./nova/context/PermissionOverlay.tsx', import.meta.url), 'utf8')
const dock = readFileSync(new URL('./nova/context/ContextDock.tsx', import.meta.url), 'utf8')

describe('Context System (Phase 4)', () => {
  it('exposes notification APIs to the client', () => {
    expect(api).toContain("notifications(limit = 50)")
    expect(api).toContain("notificationUnreadCount()")
    expect(api).toContain("markNotificationRead(id: string)")
    expect(api).toContain("markAllNotificationsRead()")
  })

  it('mounts the Notification Center from the Nova Shell', () => {
    expect(shell).toContain("import { NotificationCenter, PermissionOverlay, ContextDock } from './context'")
    expect(shell).toContain('<NotificationCenter')
    expect(shell).toContain('<ContextDock')
    expect(shell).toContain('<PermissionOverlay')
  })

  it('renders a floating notification drawer with kinds and unread markers', () => {
    expect(notif).toContain('NOTIFICATIONS')
    expect(notif).toContain('notificationUnreadCount')
    expect(notif).toContain('markAllNotificationsRead')
    expect(notif).toContain("'intel' | 'alert' | 'mission' | 'system' | 'email'")
    expect(notif).toContain('is_read')
    expect(notif).toContain('unread')
  })

  it('gates high-stakes actions behind a permission overlay', () => {
    expect(permission).toContain('PERMISSION REQUIRED')
    expect(permission).toContain('IRREVERSIBLE ACTION')
    expect(permission).toContain('SALAAR CONFIDENCE')
    expect(permission).toContain('onApprove')
    expect(permission).toContain('onDeny')
    expect(shell).toContain('highRisk')
    expect(shell).toContain('setPermission')
  })

  it('provides a floating context dock for the active view', () => {
    expect(dock).toContain('CONTEXT')
    expect(dock).toContain('SIGNALS')
    expect(dock).toContain('SUGGESTED')
    expect(dock).toContain("VIEW_CONTEXT")
    expect(dock).toContain('home')
    expect(dock).toContain('missions')
    expect(dock).toContain('spaces')
  })
})
