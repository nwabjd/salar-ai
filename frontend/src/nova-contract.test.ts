import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const nova = readFileSync(new URL('./nova/nova.css', import.meta.url), 'utf8')
const main = readFileSync(new URL('./main.tsx', import.meta.url), 'utf8')
const shell = readFileSync(new URL('./nova/NovaShell.tsx', import.meta.url), 'utf8')
const core = readFileSync(new URL('./nova/SalaarCore.tsx', import.meta.url), 'utf8')
const home = readFileSync(new URL('./nova/HomeScreen.tsx', import.meta.url), 'utf8')

describe('Salaar Nova design system', () => {
  it('defines the Nova color palette exactly', () => {
    expect(nova).toContain('--nova-bg-void: #07090f')
    expect(nova).toContain('--nova-bg-navy: #090d18')
    expect(nova).toContain('--nova-bg-violet: #100b1e')
    expect(nova).toContain('--nova-cyan: #60efff')
    expect(nova).toContain('--nova-violet: #a879ff')
    expect(nova).toContain('--nova-white: #f7f9ff')
    expect(nova).toContain('--nova-lunar: #9da7ba')
    expect(nova).toContain('--nova-mint: #78f4c5')
    expect(nova).toContain('--nova-amber: #ffcc75')
    expect(nova).toContain('--nova-coral: #ff7185')
  })

  it('defines glass and intelligence surfaces', () => {
    expect(nova).toContain('.nova-glass')
    expect(nova).toContain('.nova-intel-glass')
    expect(nova).toContain('.nova-solid')
    expect(nova).toContain('backdrop-filter: blur')
  })

  it('provides the four motion timing tokens', () => {
    expect(nova).toContain('--nova-motion-micro: 140ms')
    expect(nova).toContain('--nova-motion-panel: 300ms')
    expect(nova).toContain('--nova-motion-major: 600ms')
  })

  it('respects reduced motion', () => {
    expect(nova).toContain('@media (prefers-reduced-motion: reduce)')
    expect(nova).toContain('animation: none !important')
  })
})

describe('Nova shell wiring', () => {
  it('ships Nova mode into the app with a way back to classic view', () => {
    expect(main).toContain("import { NovaShell } from './nova'")
    expect(main).toContain("import './nova/nova.css'")
    expect(main).toContain('novaMode')
    expect(shell).toContain('CLASSIC VIEW')
  })

  it('renders the core, rail, and home surfaces', () => {
    expect(shell).toContain('<NovaBackground/>')
    expect(shell).toContain('<NovaRail')
    expect(shell).toContain('<HomeScreen')
  })

  it('builds the layered Salaar Core with all states', () => {
    expect(core).toContain('Listening')
    expect(core).toContain('Understanding')
    expect(core).toContain('Thinking')
    expect(core).toContain('Building a plan')
    expect(core).toContain('Working')
    expect(core).toContain('Checking the result')
    expect(core).toContain('Done')
  })

  it('keeps the greeting and ready line on Home', () => {
    expect(home).toContain('Ready when you are.')
    expect(home).toContain('Good morning')
  })
})
