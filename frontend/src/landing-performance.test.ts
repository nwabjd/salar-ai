import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const landing = readFileSync(new URL('./components/SalaarLanding.tsx', import.meta.url), 'utf8')

describe('landing animation performance contract', () => {
  it('uses one tuned LiquidEther background without the particle core', () => {
    expect(landing).toContain("import LiquidEther from '../effects/LiquidEther.jsx'")
    expect(landing).not.toContain('CosmicIntelligence')
    expect(landing).not.toContain('cosmic-grain')
    expect(landing).toContain('resolution={0.28}')
    expect(landing).toContain('iterationsPoisson={12}')
    expect(landing).toContain('BFECC={false}')
  })
})
