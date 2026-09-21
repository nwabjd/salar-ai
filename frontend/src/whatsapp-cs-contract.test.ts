import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const api = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')
const sidebar = readFileSync(new URL('./workspace/Sidebar.tsx', import.meta.url), 'utf8')
const shell = readFileSync(new URL('./workspace/WorkspaceShell.tsx', import.meta.url), 'utf8')
const view = readFileSync(new URL('./workspace/WhatsAppCSView.tsx', import.meta.url), 'utf8')

describe('WhatsApp Customer Service (official Cloud API) frontend contract', () => {
  it('exposes the admin API surface through SalarApi', () => {
    expect(api).toContain('whatsappCsOverview()')
    expect(api).toContain('whatsappCsConversations(')
    expect(api).toContain('whatsappCsConversation(id: string)')
    expect(api).toContain('whatsappCsReply(')
    expect(api).toContain('whatsappCsAssign(')
    expect(api).toContain('whatsappCsResumeAi(')
    expect(api).toContain('whatsappCsResolve(')
    expect(api).toContain('whatsappCsReopen(')
    expect(api).toContain('whatsappCsNotes(')
    expect(api).toContain('whatsappCsKnowledge(')
    expect(api).toContain('whatsappCsKnowledgeCreate(')
    expect(api).toContain('whatsappCsKnowledgeUpdate(')
    expect(api).toContain('whatsappCsKnowledgeToggle(')
    expect(api).toContain('whatsappCsKnowledgeDelete(')
    expect(api).toContain('whatsappCsAiSettingsGet()')
    expect(api).toContain('whatsappCsAiSettingsSet(')
    expect(api).toContain('whatsappCsConnectionGet()')
    expect(api).toContain('whatsappCsConnectionUpdate(')
  })

  it('talks to the modular /api/whatsapp-cs endpoints, not the personal bridge', () => {
    expect(api).toContain('/api/whatsapp-cs/overview')
    expect(api).toContain('/api/whatsapp-cs/conversations')
    expect(api).toContain('/api/whatsapp-cs/knowledge')
    expect(api).toContain('/api/whatsapp-cs/ai-settings')
    expect(api).toContain('/api/whatsapp-cs/connection')
    // The existing personal WhatsApp bridge stays untouched.
    expect(api).toContain("'/api/whatsapp/status'")
    expect(api).toContain("'/api/whatsapp/logout'")
  })

  it('registers the view in the workspace navigation and shell', () => {
    expect(sidebar).toContain("'whatsapp-cs'")
    expect(sidebar).toContain("label: 'WhatsApp CS'")
    expect(shell).toContain("import WhatsAppCSView from './WhatsAppCSView'")
    expect(shell).toContain("view === 'whatsapp-cs' && <WhatsAppCSView api={api} />")
  })

  it('renders the four dashboard tabs', () => {
    for (const label of ['Overview', 'Inbox', 'Knowledge', 'Connection']) {
      expect(view).toContain(`label: '${label}'`)
    }
    expect(view).toContain('WhatsApp Customer Service')
  })

  it('supports human handover controls and internal notes', () => {
    expect(view).toContain('Resume AI')
    expect(view).toContain('Assign')
    expect(view).toContain('Unassign')
    expect(view).toContain('Internal note')
  })

  it('never embeds server secrets or credentials in the client bundle', () => {
    // No literal secret values or environment variable names ship to the browser.
    expect(api).not.toMatch(/access_token['"]?\s*:\s*['"][A-Za-z0-9]{20,}/)
    expect(api).not.toContain('SALAR_WHATSAPP_CS')
    expect(view).not.toContain('SALAR_WHATSAPP_CS')
    expect(view).not.toMatch(/app_secret\s*[:=]\s*['"][^'"]+['"]/)
    expect(view).not.toMatch(/verify_token\s*[:=]\s*['"][^'"]+['"]/)
    // The UI only ever shows booleans for whether a secret is configured.
    expect(view).toContain('has_access_token')
    expect(view).toContain('has_app_secret')
    expect(view).toContain('never in the database or the browser')
  })
})
