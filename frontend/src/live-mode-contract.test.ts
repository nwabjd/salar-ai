import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const main = readFileSync(new URL('./main.tsx', import.meta.url), 'utf8')

describe('Live voice mode contract', () => {
  it('mounts the orb only inside Live and exposes every phase label', () => {
    const live = main.slice(main.indexOf('function Live('), main.indexOf('function StatusCard('))
    expect(live).toContain('<MagicRings')
    expect(main.match(/<MagicRings/g)).toHaveLength(1)
    for (const label of ['Starting', 'Listening', 'Thinking', 'Speaking']) expect(live).toContain(label)
  })

  it('drives speaking volume from TTS output and cleans it up', () => {
    expect(main).toContain('outputFrameRef')
    expect(main).toContain('ctx.createAnalyser()')
    expect(main).toContain('source.connect(outputAnalyser)')
    expect(main).toContain('cancelAnimationFrame(outputFrameRef.current)')
    expect(main).toContain("phaseRef.current === 'listening'")
    expect(main).toContain('getTracks().forEach(t => t.stop())')
    expect(main).toContain('audioCtxRef.current.close()')
  })
})
