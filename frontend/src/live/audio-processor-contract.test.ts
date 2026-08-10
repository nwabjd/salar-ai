import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('SALAR Live audio worklet contract', () => {
  const source = readFileSync('public/audio-processor.js', 'utf8')

  it('captures 16kHz PCM in short chunks and plays 24kHz PCM', () => {
    expect(source).toContain('this.captureRate = 16000')
    expect(source).toContain('this.playbackRate = 24000')
    expect(source).toContain('this.captureFrameSize = 640')
    expect(source).toContain('this.resample(input, sampleRate, this.captureRate)')
    expect(source).toContain('this.pcm16ToFloat(data.samples)')
    expect(source).toContain('this.resample(playbackSamples, this.playbackRate, sampleRate)')
  })

  it('normalizes signed PCM16 before sending samples to Web Audio output', () => {
    expect(source).toContain('pcm16ToFloat(input)')
    expect(source).toContain('output[index] = Math.max(-1, input[index] / 32768)')
  })

  it('clears queued playback on interruption', () => {
    expect(source).toContain("if (data.type === 'stop')")
    expect(source).toContain('this.playback = []')
  })
})
