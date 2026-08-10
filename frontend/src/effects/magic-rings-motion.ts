export type VoicePhase = 'idle' | 'listening' | 'thinking' | 'speaking'

export type RingMotionTarget = {
  timeSpeed: number
  scaleRate: number
  noiseAmount: number
  lineThickness: number
  attenuation: number
  ringCount: number
  rotationSpeed: number
  opacity: number
}

const clamp01 = (value: number) => Math.max(0, Math.min(1, value))

export function getRingMotionTarget(phase: VoicePhase, volume: number, reducedMotion: boolean): RingMotionTarget {
  const audio = clamp01(volume / 60)
  const reducedScale = reducedMotion ? 0.18 : 1

  if (phase === 'listening') return {
    timeSpeed: reducedMotion ? 0.24 : 0.55 + audio * 0.65,
    scaleRate: 0.045 + audio * 0.07 * reducedScale,
    noiseAmount: 0.025 + audio * 0.09,
    lineThickness: 1.55 + audio * 0.55,
    attenuation: 11.5,
    ringCount: 5 + Math.round(audio),
    rotationSpeed: reducedMotion ? 0 : 0.06,
    opacity: 0.78 + audio * 0.2,
  }

  if (phase === 'thinking') return {
    timeSpeed: reducedMotion ? 0.35 : 1.9,
    scaleRate: 0.12 + 0.025 * reducedScale,
    noiseAmount: 0.19,
    lineThickness: reducedMotion ? 2.35 : 2.55,
    attenuation: 7.4,
    ringCount: 6,
    rotationSpeed: reducedMotion ? 0 : -0.46,
    opacity: 0.92,
  }

  if (phase === 'speaking') return {
    timeSpeed: reducedMotion ? 0.3 : 1.05 + audio * 0.55,
    scaleRate: 0.14 + audio * 0.13 * reducedScale,
    noiseAmount: 0.05 + audio * 0.1,
    lineThickness: 2.05 + audio * (reducedMotion ? 0.25 : 0.75),
    attenuation: 9.2,
    ringCount: 6,
    rotationSpeed: reducedMotion ? 0 : 0.2,
    opacity: 0.86 + audio * 0.14,
  }

  return {
    timeSpeed: reducedMotion ? 0.12 : 0.32,
    scaleRate: reducedMotion ? 0.025 : 0.055,
    noiseAmount: 0.02,
    lineThickness: 1.35,
    attenuation: 12,
    ringCount: 5,
    rotationSpeed: 0,
    opacity: 0.58,
  }
}

export function approachMotionTarget(current: RingMotionTarget, target: RingMotionTarget, amount: number): RingMotionTarget {
  const alpha = clamp01(amount)
  const next = {} as RingMotionTarget
  for (const key of Object.keys(target) as Array<keyof RingMotionTarget>) {
    next[key] = current[key] + (target[key] - current[key]) * alpha
  }
  return next
}
