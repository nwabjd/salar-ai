import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('SALAR Live audio worklet contract', () => {
  const source = readFileSync('public/audio-processor.js', 'utf8')

  it('captures 16kHz PCM in short chunks and plays 24kHz PCM', () => {
    expect(source).toContain('this.captureRate = 16000')
    expect(source).toContain('this.playbackRate = 24000')
    expect(source).toContain('this.captureFrameSize = 640')
    expect(source).toContain('this.resample(input, sampleRate, this.captureRate)')
    expect(source).toContain('this.resample(data.samples, this.playbackRate, sampleRate)')
  })

  it('clears queued playback on interruption', () => {
    expect(source).toContain("if (data.type === 'stop')")
    expect(source).toContain('this.playback = []')
  })
})
