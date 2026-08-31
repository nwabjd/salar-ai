import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const shell = readFileSync(new URL('./workspace/WorkspaceShell.tsx', import.meta.url), 'utf8')
const sidebar = readFileSync(new URL('./workspace/Sidebar.tsx', import.meta.url), 'utf8')
const codeView = readFileSync(new URL('./workspace/CodeView.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')

describe('Phase 3/6 — full workspace contract', () => {
  it('no workspace view remains a placeholder', () => {
    expect(shell).not.toContain('coming to your workspace')
    expect(shell).not.toContain('PlaceholderView')
  })

  it('registers Code as a wired workspace view', () => {
    expect(sidebar).toContain(`'code'`)
    expect(sidebar).toContain(`label: 'Code'`)
    expect(shell).toContain(`view === 'code' && <CodeView`)
  })

  it('renders a code runner and exposes the execute API', () => {
    expect(codeView).toContain('api.codeExecute(code)')
    expect(codeView).toContain('Run')
    expect(api).toContain('codeExecute(code:')
  })

  it('exposes code history management', () => {
    expect(api).toContain('codeHistory(')
    expect(api).toContain('codeClearHistory(')
  })
})