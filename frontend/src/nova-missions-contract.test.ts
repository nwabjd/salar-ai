import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const api = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')
const shell = readFileSync(new URL('./nova/NovaShell.tsx', import.meta.url), 'utf8')
const graph = readFileSync(new URL('./nova/missions/MissionGraph.tsx', import.meta.url), 'utf8')
const center = readFileSync(new URL('./nova/missions/MissionCenter.tsx', import.meta.url), 'utf8')
const live = readFileSync(new URL('./nova/missions/LiveMissionView.tsx', import.meta.url), 'utf8')
const agent = readFileSync(new URL('./nova/missions/AgentNode.tsx', import.meta.url), 'utf8')

describe('Mission Center (Phase 5)', () => {
  it('exposes mission APIs to the client', () => {
    expect(api).toContain('missions(): Promise<Mission[]>')
    expect(api).toContain("'/api/missions'")
    expect(api).toContain('launchMission(goal: string, mode = \'autonomous\')')
    expect(api).toContain('approveMissionStep(')
    expect(api).toContain('denyMissionStep(')
    expect(api).toContain('cancelMission(')
  })

  it('renders the Mission Center from the Nova Rail', () => {
    expect(shell).toContain("import { MissionCenter } from './missions'")
    expect(shell).toContain("view === 'missions'")
    expect(shell).toContain('<MissionCenter')
  })

  it('builds a branching mission graph with status-aware nodes', () => {
    expect(graph).toContain('waves')
    expect(graph).toContain('edges')
    expect(graph).toContain('running')
    expect(graph).toContain('completed')
    expect(graph).toContain('waiting_approval')
    expect(graph).toContain("'#60efff'")
    expect(graph).toContain("'#ff7185'")
    expect(graph).toContain("'#ffcc75'")
    expect(graph).toContain("'#78f4c5'")
  })

  it('shows the featured mission and recent missions list', () => {
    expect(center).toContain('FEATURED MISSION')
    expect(center).toContain('RECENT MISSIONS')
    expect(center).toContain('Give Salaar a mission')
    expect(center).toContain('No active missions')
    expect(center).toContain('Start a mission')
  })

  it('provides an immersive live mission view', () => {
    expect(live).toContain('LIVE MISSION')
    expect(live).toContain('OBJECTIVE')
    expect(live).toContain('AWAITING APPROVAL')
    expect(live).toContain('Approve')
    expect(live).toContain('Deny')
  })

  it('visualizes agents as temporary nodes', () => {
    expect(agent).toContain('active')
    expect(agent).toContain('waiting')
    expect(agent).toContain('done')
    expect(agent).toContain('agent.state')
  })
})
