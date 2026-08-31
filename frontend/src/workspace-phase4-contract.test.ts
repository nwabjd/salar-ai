import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const shell = readFileSync(new URL('./workspace/WorkspaceShell.tsx', import.meta.url), 'utf8')
const sidebar = readFileSync(new URL('./workspace/Sidebar.tsx', import.meta.url), 'utf8')
const commandsView = readFileSync(new URL('./workspace/CommandsView.tsx', import.meta.url), 'utf8')
const devicePoll = readFileSync(new URL('./device-poll.ts', import.meta.url), 'utf8')
const api = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')
const backend = readFileSync(new URL('../../backend/app/api/devices.py', import.meta.url), 'utf8')

describe('Phase 4 — device commands & relay contract', () => {
  it('registers Commands as a workspace nav view wired in the shell', () => {
    expect(sidebar).toContain(`'commands'`)
    expect(sidebar).toContain(`label: 'Commands'`)
    expect(shell).toContain(`view === 'commands' && <CommandsView`)
  })

  it('exposes the command lifecycle API methods', () => {
    expect(api).toContain('getCommands()')
    expect(api).toContain('approveCommand(')
    expect(api).toContain('nextDeviceCommand(')
    expect(api).toContain('completeDeviceCommand(')
    expect(api).toContain('registerDevice(')
  })

  it('shows approval UI for commands awaiting confirmation', () => {
    expect(commandsView).toContain("c.status === 'awaiting_confirmation'")
    expect(commandsView).toContain('Approve Command')
    expect(commandsView).toContain('api.approveCommand')
  })

  it('polls the backend for relayed device commands on desktop', () => {
    expect(devicePoll).toContain('startDevicePolling(')
    expect(devicePoll).toContain('api.nextDeviceCommand(token)')
    expect(devicePoll).toContain('executeCommand(')
    expect(devicePoll).toContain('api.completeDeviceCommand(')
  })

  it('flags sensitive commands for backend confirmation', () => {
    expect(backend).toContain('CONFIRMATION_REQUIRED')
    expect(backend).toContain('create_directory')
    expect(backend).toContain('reveal_path')
  })
})