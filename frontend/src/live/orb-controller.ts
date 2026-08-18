import type { LivePhase } from './realtime-state'

export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking'

const VOICE_THRESHOLD = 0.04
const DECAY_RATE = 0.88

export class OrbController {
  private smoothMic = 0
  private smoothAi = 0

  private micVolume = 0
  private aiVolume = 0
  private phase: LivePhase = 'connecting'

  setMicVolume(volume: number) {
    this.micVolume = volume
  }

  setPlaybackVolume(volume: number) {
    this.aiVolume = volume
  }

  setPhase(phase: LivePhase) {
    this.phase = phase
  }

  getMicVolume(): number {
    return this.smoothMic
  }

  getAiVolume(): number {
    return this.smoothAi
  }

  getState(): OrbState {
    this.smoothMic += (this.micVolume - this.smoothMic) * 0.15
    this.smoothAi += (this.aiVolume - this.smoothAi) * 0.15

    this.smoothMic *= DECAY_RATE
    this.smoothAi *= DECAY_RATE

    const micActive = this.smoothMic > VOICE_THRESHOLD
    const aiActive = this.smoothAi > VOICE_THRESHOLD

    if (aiActive) return 'speaking'
    if (micActive) return 'listening'
    if (this.phase === 'thinking') return 'thinking'
    if (this.phase === 'connecting' || this.phase === 'reconnecting') return 'idle'
    if (this.phase === 'error') return 'idle'
    return 'idle'
  }
}
