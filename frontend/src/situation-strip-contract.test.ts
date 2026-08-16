import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const main = readFileSync(new URL('./main.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('./api.ts', import.meta.url), 'utf8')
const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8')

describe('world situation surface contract', () => {
  it('polls the world model for active situations and actions', () => {
    expect(main).toContain('worldSituations()')
    expect(main).toContain('worldActions()')
    expect(main).toContain('setInterval(load, 45000)')
    expect(api).toContain('worldSituations(limit = 12)')
    expect(api).toContain('/api/world/situations')
    expect(api).toContain('worldActions()')
    expect(api).toContain('/api/world/actions')
    expect(api).toContain('worldSimulate(')
    expect(api).toContain('/api/world/simulate')
  })

  it('executes actions through the endpoint and lets SALAR narrate results', () => {
    expect(main).toContain('worldExecuteAction(')
    expect(main).toContain('Executed "${a.title}"')
    expect(main).toContain("api.worldExecuteAction")
    expect(api).toContain('worldExecuteAction(')
    expect(api).toContain('/api/world/actions/execute')
  })

  it('learns from outcomes via the evolve/policies endpoints', () => {
    expect(api).toContain('worldEvolve()')
    expect(api).toContain('/api/world/evolve')
    expect(api).toContain('worldPolicies()')
    expect(api).toContain('/api/world/policies')
    expect(main).toContain('action-score')
  })

  it('hides the strip when nothing is happening', () => {
    expect(main).toContain('if (situations.length === 0 && actions.length === 0) return null')
  })

  it('styles severity, risk, and action states', () => {
    expect(styles).toContain('.situation-chip')
    expect(styles).toContain('.situation-chip.critical')
    expect(styles).toContain('.situation-chip.high')
    expect(styles).toContain('.situation-dot')
    expect(styles).toContain('.situation-chip.action-chip')
    expect(styles).toContain('.action-glyph')
    expect(styles).toContain('.action-score')
    expect(styles).toContain('.situation-chip.action-chip.risky')
    expect(styles).toContain('.situation-chip.action-chip.running')
  })
})
