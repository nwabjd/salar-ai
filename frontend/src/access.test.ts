import { describe, expect, it } from 'vitest'
import { resolveAccessState } from './access'

describe('SALAR access state', () => {
  it('opens an unprovisioned desktop shell without a login wall', () => {
    expect(resolveAccessState({ desktop: true, token: '' })).toBe('desktop-disconnected')
  })

  it('requires pairing for an unpaired browser', () => {
    expect(resolveAccessState({ desktop: false, token: '' })).toBe('pairing')
  })

  it('connects either platform with a device session', () => {
    expect(resolveAccessState({ desktop: false, token: 'sds_example' })).toBe('connected')
  })
})
