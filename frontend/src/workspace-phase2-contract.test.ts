import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const shell = readFileSync(new URL('./workspace/WorkspaceShell.tsx', import.meta.url), 'utf8')
const sidebar = readFileSync(new URL('./workspace/Sidebar.tsx', import.meta.url), 'utf8')
const composer = readFileSync(new URL('./workspace/Composer.tsx', import.meta.url), 'utf8')
const memoryView = readFileSync(new URL('./workspace/MemoryView.tsx', import.meta.url), 'utf8')
const projectsView = readFileSync(new URL('./workspace/ProjectsView.tsx', import.meta.url), 'utf8')
const memoryApi = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')

describe('Phase 2 workspace contract', () => {
  it('registers Memory as a workspace nav view', () => {
    expect(sidebar).toContain(`'memory'`)
    expect(sidebar).toContain(`label: 'Memory'`)
    expect(shell).toContain(`view === 'memory' && <MemoryView`)
    expect(shell).toContain(`import MemoryView from './MemoryView'`)
  })

  it('renders the Memory view with search, layers and creation', () => {
    expect(memoryView).toContain('Search memories')
    expect(memoryView).toContain('New memory')
    expect(memoryView).toContain('short-term')
    expect(memoryView).toContain('vault')
    expect(memoryView).toContain('Save memory')
  })

  it('exposes memory API methods with filters', () => {
    expect(memoryApi).toContain('memories(params:')
    expect(memoryApi).toContain('search')
    expect(memoryApi).toContain('layer')
    expect(memoryApi).toContain('deleteMemory')
    expect(memoryApi).toContain('/api/memories/${id}')
  })

  it('keeps the composer attachment flow wired', () => {
    expect(composer).toContain(`onSend(text, draft.map((d) => d.file))`)
    expect(composer).toContain('Attach files')
    expect(memoryView).toContain('ws-scroll ws-mem')
  })

  it('renders the Projects view with create, goals and delete', () => {
    expect(projectsView).toContain('New project')
    expect(projectsView).toContain('Create project')
    expect(projectsView).toContain('Goals')
    expect(projectsView).toContain('Add a goal…')
    expect(shell).toContain(`view === 'projects' && <ProjectsView`)
  })

  it('exposes project API methods with CRUD', () => {
    expect(memoryApi).toContain('projects()')
    expect(memoryApi).toContain('createProject')
    expect(memoryApi).toContain('updateProject')
    expect(memoryApi).toContain('deleteProject')
  })
})