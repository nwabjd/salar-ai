import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const api = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')
const backendSwarm = readFileSync(new URL('../../backend/app/services/swarm.py', import.meta.url), 'utf8')
const backendUsers = readFileSync(new URL('../../backend/app/api/users.py', import.meta.url), 'utf8')

describe('Multi-user and Agent Swarm contract', () => {
  it('exposes multi-user and workspace sharing API methods', () => {
    expect(api).toContain('userProfile()')
    expect(api).toContain('listUsers()')
    expect(api).toContain('inviteUser(')
    expect(api).toContain('listWorkspaceMembers(')
    expect(api).toContain('removeWorkspaceMember(')
  })

  it('exposes swarm decomposition, execution, and run tracking API methods', () => {
    expect(api).toContain('swarmAgents()')
    expect(api).toContain('swarmDecompose(')
    expect(api).toContain('swarmRun(')
    expect(api).toContain('swarmRuns(')
    expect(api).toContain('swarmRunGet(')
  })

  it('includes expanded agent specs in backend swarm engine', () => {
    expect(backendSwarm).toContain('"Architect"')
    expect(backendSwarm).toContain('"Analyst"')
    expect(backendSwarm).toContain('"Security"')
    expect(backendSwarm).toContain('"Communicator"')
    expect(backendSwarm).toContain('SwarmBlackboard')
    expect(backendSwarm).toContain('asyncio.gather')
  })

  it('implements workspace member roles and user invitation in backend', () => {
    expect(backendUsers).toContain('router = APIRouter(prefix="/api/users"')
    expect(backendUsers).toContain('/invite')
    expect(backendUsers).toContain('/workspaces/{workspace_id}/members')
    expect(backendUsers).toContain('WorkspaceMember')
  })
})