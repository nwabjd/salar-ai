import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const shell = readFileSync(new URL('./nova/NovaShell.tsx', import.meta.url), 'utf8')
const overview = readFileSync(new URL('./nova/spaces/SpacesOverview.tsx', import.meta.url), 'utf8')
const container = readFileSync(new URL('./nova/spaces/SpaceContainer.tsx', import.meta.url), 'utf8')
const dev = readFileSync(new URL('./nova/spaces/DevSpace.tsx', import.meta.url), 'utf8')
const research = readFileSync(new URL('./nova/spaces/ResearchSpace.tsx', import.meta.url), 'utf8')
const rail = readFileSync(new URL('./nova/NovaRail.tsx', import.meta.url), 'utf8')

describe('Spaces (Phase 6)', () => {
  it('exposes Spaces as a first-class rail destination', () => {
    expect(rail).toContain("id: 'spaces'")
    expect(shell).toContain("import { SpacesOverview, SpaceContainer, DEFAULT_SPACES } from './spaces'")
    expect(shell).toContain("view === 'spaces' && openSpace === null")
    expect(shell).toContain('<SpaceContainer')
  })

  it('shows a spatial overview with a featured space and recent spaces', () => {
    expect(overview).toContain('SPATIAL LAYER')
    expect(overview).toContain('Your Spaces')
    expect(overview).toContain('FEATURED SPACE')
    expect(overview).toContain('RECENTLY USED')
    expect(overview).toContain("onCreateSpace")
  })

  it('defines the core Space kinds', () => {
    expect(overview).toContain("'development'")
    expect(overview).toContain("'research'")
    expect(overview).toContain("'creative'")
    expect(overview).toContain("'business'")
    expect(overview).toContain("'personal'")
    expect(overview).toContain("'device'")
  })

  it('routes each space kind through the Space Container', () => {
    expect(container).toContain("kind === 'development'")
    expect(container).toContain('<DevSpace')
    expect(container).toContain("kind === 'research'")
    expect(container).toContain('<ResearchSpace')
  })

  it('builds an adaptive development workspace shell', () => {
    expect(dev).toContain('DEVELOPMENT SPACE')
    expect(dev).toContain('api.fileTree')
    expect(dev).toContain('api.fileRead')
    expect(dev).toContain('CURRENT TASK')
    expect(dev).toContain('ACTIVE AGENTS')
    expect(dev).toContain('SIGNALS')
  })

  it('builds a research workspace shell around sources and synthesis', () => {
    expect(research).toContain('RESEARCH SPACE')
    expect(research).toContain('api.knowledgeDocs')
    expect(research).toContain('api.knowledgeChunks')
    expect(research).toContain('SOURCES')
    expect(research).toContain('INTELLIGENCE')
    expect(research).toContain('KNOWLEDGE MAP')
  })
})
