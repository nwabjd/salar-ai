/** 16kHz PCM capture and 24kHz PCM playback for SALAR Live. */
class StreamingLinearResampler {
  constructor(fromRate, toRate) {
    this.ratio = fromRate / toRate
    this.position = 0
    this.pending = new Float32Array(0)
  }

  push(input) {
    if (!input.length) return new Float32Array(0)
    const combined = new Float32Array(this.pending.length + input.length)
    combined.set(this.pending)
    combined.set(input, this.pending.length)
    const output = []
    while (this.position < combined.length - 1) {
      const left = Math.floor(this.position)
      const mix = this.position - left
      output.push(combined[left] * (1 - mix) + combined[left + 1] * mix)
      this.position += this.ratio
    }
    const consumed = Math.floor(this.position)
    this.pending = combined.slice(consumed)
    this.position -= consumed
    return Float32Array.from(output)
  }

  reset() {
    this.position = 0
    this.pending = new Float32Array(0)
  }
}

class SalarAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.captureRate = 16000
    this.playbackRate = 24000
    this.captureFrameSize = 640
    this.captureResampler = new StreamingLinearResampler(sampleRate, this.captureRate)
    this.playbackResampler = new StreamingLinearResampler(this.playbackRate, sampleRate)
    this.capture = []
    this.playback = []
    this.playbackIndex = 0
    this.wasPlaying = false
    this.port.onmessage = ({ data }) => {
      if (data.type === 'playback' && data.samples) {
        const playbackSamples = this.pcm16ToFloat(data.samples)
        const resampled = this.playbackResampler.push(playbackSamples)
        if (resampled.length) this.playback.push(resampled)
      }
      if (data.type === 'stop') {
        this.playback = []
        this.playbackIndex = 0
        this.wasPlaying = false
        this.playbackResampler.reset()
      }
    }
  }

  process(inputs, outputs) {
    const input = inputs[0]?.[0]
    const output = outputs[0]?.[0]
    if (input) this.captureInput(input)
    if (output) this.renderPlayback(output)
    return true
  }

  captureInput(input) {
    const resampled = this.captureResampler.push(input)
    for (const value of resampled) this.capture.push(value)
    while (this.capture.length >= this.captureFrameSize) {
      const frame = this.capture.splice(0, this.captureFrameSize)
      const samples = new Int16Array(frame.length)
      let energy = 0
      for (let index = 0; index < frame.length; index += 1) {
        const value = Math.max(-1, Math.min(1, frame[index]))
        samples[index] = Math.round(value * 32767)
        energy += value * value
      }
      this.port.postMessage({ type: 'capture', samples, volume: Math.min(1, Math.sqrt(energy / frame.length) * 5) })
    }
  }

  renderPlayback(output) {
    output.fill(0)
    let energy = 0
    let written = 0
    while (written < output.length && this.playback.length) {
      const frame = this.playback[0]
      const available = frame.length - this.playbackIndex
      const count = Math.min(output.length - written, available)
      const slice = frame.subarray(this.playbackIndex, this.playbackIndex + count)
      output.set(slice, written)
      for (const value of slice) energy += value * value
      written += count
      this.playbackIndex += count
      if (this.playbackIndex >= frame.length) {
        this.playback.shift()
        this.playbackIndex = 0
      }
    }
    if (written) {
      this.wasPlaying = true
      this.port.postMessage({ type: 'playback_volume', volume: Math.min(1, Math.sqrt(energy / written) * 4) })
    } else if (this.wasPlaying) {
      this.wasPlaying = false
      this.port.postMessage({ type: 'playback_drained' })
    }
  }

  pcm16ToFloat(input) {
    const output = new Float32Array(input.length)
    for (let index = 0; index < input.length; index += 1) {
      output[index] = Math.max(-1, input[index] / 32768)
    }
    return output
  }

}

registerProcessor('salar-audio', SalarAudioProcessor)
