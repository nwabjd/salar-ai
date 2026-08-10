import { describe, expect, it } from 'vitest'
import { approachMotionTarget, getRingMotionTarget } from './magic-rings-motion'

describe('MagicRings voice motion', () => {
  it('gives every voice phase a distinct deterministic target', () => {
    expect(getRingMotionTarget('listening', 30, false).scaleRate)
      .toBeLessThan(getRingMotionTarget('speaking', 30, false).scaleRate)
    expect(getRingMotionTarget('thinking', 0, false).rotationSpeed).not.toBe(0)
  })

  it('responds to audio volume and honors reduced motion', () => {
    expect(getRingMotionTarget('speaking', 60, false).scaleRate)
      .toBeGreaterThan(getRingMotionTarget('speaking', 0, false).scaleRate)
    expect(getRingMotionTarget('speaking', 60, true).rotationSpeed).toBe(0)
  })

  it('approaches targets without snapping', () => {
    const from = getRingMotionTarget('idle', 0, false)
    const target = getRingMotionTarget('thinking', 0, false)
    const next = approachMotionTarget(from, target, 0.2)
    expect(next.rotationSpeed).not.toBe(from.rotationSpeed)
    expect(next.rotationSpeed).not.toBe(target.rotationSpeed)
  })
})
