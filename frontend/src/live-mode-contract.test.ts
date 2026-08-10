import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const main = readFileSync(new URL('./main.tsx', import.meta.url), 'utf8')

describe('Live voice mode contract', () => {
  it('mounts the orb only inside active Live and exposes every realtime phase label', () => {
    const live = main.slice(main.indexOf('function Live('), main.indexOf('function LegacyLive('))
    expect(live).toContain('<MagicRings')
    expect(main.match(/<MagicRings/g)).toHaveLength(1)
    for (const label of ['Connecting', 'Reconnecting', 'Listening', 'Thinking', 'Speaking']) expect(live).toContain(label)
  })

  it('uses native Gemini Live with an automatic polished fallback', () => {
    const live = main.slice(main.indexOf('function Live('), main.indexOf('function LegacyLive('))
    expect(live).toContain('new GeminiLiveClient')
    expect(live).toContain('new FallbackVoiceClient')
    expect(live).toContain('new HybridVoiceClient')
    expect(live).toContain('onEvent: dispatch')
    expect(live).not.toContain('MediaRecorder')
    expect(live).not.toContain('api.stt')
    expect(live).not.toContain('api.tts')
  })
})
