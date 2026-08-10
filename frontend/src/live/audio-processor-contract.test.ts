import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { describe, expect, it } from 'vitest'

describe('SALAR Live audio worklet contract', () => {
  const source = readFileSync('public/audio-processor.js', 'utf8')

  function createProcessor(deviceSampleRate: number) {
    let Processor: new () => {
      playback: Float32Array[]
      port: { onmessage: (event: { data: { type: string; samples: Int16Array } }) => void }
    }
    class AudioWorkletProcessorStub {
      port = { onmessage: () => {}, postMessage: () => {} }
    }
    runInNewContext(source, {
      AudioWorkletProcessor: AudioWorkletProcessorStub,
      Float32Array,
      Int16Array,
      Math,
      sampleRate: deviceSampleRate,
      registerProcessor: (_name: string, RegisteredProcessor: typeof Processor) => { Processor = RegisteredProcessor },
    })
    return new Processor!()
  }

  it('captures 16kHz PCM in short chunks and plays 24kHz PCM', () => {
    expect(source).toContain('this.captureRate = 16000')
    expect(source).toContain('this.playbackRate = 24000')
    expect(source).toContain('this.captureFrameSize = 640')
    expect(source).toContain('this.captureResampler.push(input)')
    expect(source).toContain('this.pcm16ToFloat(data.samples)')
    expect(source).toContain('this.playbackResampler.push(playbackSamples)')
  })

  it('normalizes signed PCM16 before sending samples to Web Audio output', () => {
    expect(source).toContain('pcm16ToFloat(input)')
    expect(source).toContain('output[index] = Math.max(-1, input[index] / 32768)')
  })

  it('preserves timing and phase across Gemini packet boundaries on 44.1kHz phones', () => {
    const processor = createProcessor(44_100)
    const input = Int16Array.from({ length: 24_000 }, (_, index) => (
      Math.round(Math.sin(2 * Math.PI * 440 * index / 24_000) * 0.7 * 32_767)
    ))
    for (let offset = 0; offset < input.length; offset += 384) {
      processor.port.onmessage({ data: { type: 'playback', samples: input.slice(offset, offset + 384) } })
    }
    const output = new Float32Array(processor.playback.reduce((total, packet) => total + packet.length, 0))
    let cursor = 0
    for (const packet of processor.playback) { output.set(packet, cursor); cursor += packet.length }
    let squaredError = 0
    for (let index = 0; index < output.length; index += 1) {
      const expected = Math.sin(2 * Math.PI * 440 * index / 44_100) * 0.7
      squaredError += (output[index] - expected) ** 2
    }
    expect(output.length).toBe(44_099)
    expect(Math.sqrt(squaredError / output.length)).toBeLessThan(0.005)
  })

  it('clears queued playback on interruption', () => {
    expect(source).toContain("if (data.type === 'stop')")
    expect(source).toContain('this.playback = []')
  })
})
