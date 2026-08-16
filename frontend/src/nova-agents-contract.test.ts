import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const api = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')
const shell = readFileSync(new URL('./nova/NovaShell.tsx', import.meta.url), 'utf8')
const center = readFileSync(new URL('./nova/agents/AgentCenter.tsx', import.meta.url), 'utf8')
const rail = readFileSync(new URL('./nova/NovaRail.tsx', import.meta.url), 'utf8')

describe('Multi-Agent Coordination (Phase 7)', () => {
  it('exposes the core orchestration APIs to the client', () => {
    expect(api).toContain("coreRun(request: string, goal = '')")
    expect(api).toContain("coreApprove(taskId: string, approve: boolean)")
    expect(api).toContain('coreStatus()')
    expect(api).toContain('coreTraces()')
    expect(api).toContain('coreTrace(traceId: string)')
    expect(api).toContain('/api/core/run')
    expect(api).toContain('/api/core/status')
  })

  it('surfaces the Agent Swarm from the Nova Rail', () => {
    expect(rail).toContain("id: 'agents'")
    expect(rail).toContain("<Users size={20}")
    expect(shell).toContain("import AgentCenter from './agents/AgentCenter'")
    expect(shell).toContain("view === 'agents'")
    expect(shell).toContain('<AgentCenter')
  })

  it('renders a roster of specialist agents with live state', () => {
    expect(center).toContain('Agent Swarm')
    expect(center).toContain('Architect')
    expect(center).toContain('Researcher')
    expect(center).toContain('Engineer')
    expect(center).toContain('QA')
    expect(center).toContain('Automation')
    expect(center).toContain("state: 'working'")
    expect(center).toContain("api.coreStatus()")
  })

  it('provides a delegation console with live run feedback', () => {
    expect(center).toContain('DELEGATION CONSOLE')
    expect(center).toContain('api.coreRun')
    expect(center).toContain('DISPATCH RESULT')
    expect(center).toContain('live_agents')
    expect(center).toContain('bus_events_count')
  })

  it('surfaces supervisor alerts and live swarm runs', () => {
    expect(center).toContain('LIVE SWARM')
    expect(center).toContain('SUPERVISOR ALERTS')
    expect(center).toContain('AGENTS ONLINE')
  })
})
