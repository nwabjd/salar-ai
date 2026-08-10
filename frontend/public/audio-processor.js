/** 24kHz PCM capture and playback for SALAR Live. */
class SalarAudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.targetRate = 24000
    this.capture = []
    this.playback = []
    this.playbackIndex = 0
    this.wasPlaying = false
    this.port.onmessage = ({ data }) => {
      if (data.type === 'playback' && data.samples) this.playback.push(this.resample(data.samples, this.targetRate, sampleRate))
      if (data.type === 'stop') {
        this.playback = []
        this.playbackIndex = 0
        this.wasPlaying = false
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
    const resampled = this.resample(input, sampleRate, this.targetRate)
    for (const value of resampled) this.capture.push(value)
    while (this.capture.length >= 2400) {
      const frame = this.capture.splice(0, 2400)
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

  resample(input, fromRate, toRate) {
    if (fromRate === toRate) return new Float32Array(input)
    const size = Math.max(1, Math.round(input.length * toRate / fromRate))
    const output = new Float32Array(size)
    const ratio = fromRate / toRate
    for (let index = 0; index < size; index += 1) {
      const position = index * ratio
      const left = Math.floor(position)
      const right = Math.min(left + 1, input.length - 1)
      const mix = position - left
      output[index] = input[left] * (1 - mix) + input[right] * mix
    }
    return output
  }
}

registerProcessor('salar-audio', SalarAudioProcessor)
