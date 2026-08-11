import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { describe, expect, it } from 'vitest'

describe('SALAR Live audio worklet contract', () => {
  const source = readFileSync('src/live/audio-processor.js', 'utf8')

  function createProcessor(deviceSampleRate: number) {
    let Processor: new () => {
      playback: Float32Array[]
      postedMessages: Array<{ type?: string }>
      port: { onmessage: (event: { data: { type: string; samples?: Int16Array; enabled?: boolean } }) => void }
      process: (inputs: Float32Array[][], outputs: Float32Array[][]) => boolean
    }
    class AudioWorkletProcessorStub {
      postedMessages: Array<{ type?: string }> = []
      port = { onmessage: () => {}, postMessage: (message: { type?: string }) => this.postedMessages.push(message) }
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

  it('prebuffers mobile playback so ordinary network jitter does not create audio gaps', () => {
    const processor = createProcessor(48_000)
    const packet = Int16Array.from({ length: 1_200 }, (_, index) => (
      Math.round(Math.sin(2 * Math.PI * 440 * index / 24_000) * 0.7 * 32_767)
    ))
    const firstOutput = new Float32Array(128)
    processor.port.onmessage({ data: { type: 'playback', samples: packet } })
    processor.process([], [[firstOutput]])
    expect(firstOutput.every((sample) => sample === 0)).toBe(true)

    const secondOutput = new Float32Array(128)
    processor.port.onmessage({ data: { type: 'playback', samples: packet } })
    processor.process([], [[secondOutput]])
    expect(secondOutput.some((sample) => sample !== 0)).toBe(true)
  })

  it('does not forward iPhone microphone capture while speaker playback is active', () => {
    const processor = createProcessor(48_000)
    const playback = Int16Array.from({ length: 2_400 }, (_, index) => (
      Math.round(Math.sin(2 * Math.PI * 440 * index / 24_000) * 0.7 * 32_767)
    ))
    processor.port.onmessage({ data: { type: 'echo_guard', enabled: true } })
    processor.port.onmessage({ data: { type: 'playback', samples: playback } })
    for (let block = 0; block < 20; block += 1) {
      processor.process([[new Float32Array(128).fill(0.5)]], [[new Float32Array(128)]])
    }
    expect(processor.postedMessages.some((message) => message.type === 'capture')).toBe(false)
  })

  it('holds capture briefly after iPhone speaker playback to reject the acoustic tail', () => {
    const processor = createProcessor(48_000)
    const playback = new Int16Array(2_400).fill(12_000)
    processor.port.onmessage({ data: { type: 'echo_guard', enabled: true } })
    processor.port.onmessage({ data: { type: 'playback', samples: playback } })
    for (let block = 0; block < 40; block += 1) {
      processor.process([[new Float32Array(128)]], [[new Float32Array(128)]])
    }
    processor.postedMessages.length = 0
    for (let block = 0; block < 20; block += 1) {
      processor.process([[new Float32Array(128).fill(0.5)]], [[new Float32Array(128)]])
    }
    expect(processor.postedMessages.some((message) => message.type === 'capture')).toBe(false)
  })

  it('clears queued playback on interruption', () => {
    expect(source).toContain("if (data.type === 'stop')")
    expect(source).toContain('this.playback = []')
  })
})
