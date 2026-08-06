import { describe, expect, it } from 'vitest'
import { resolveAccessState } from './access'

describe('SALAR access state', () => {
  it('connects when a stored session exists', () => {
    expect(resolveAccessState({ token: 'sds_example' })).toBe('connected')
  })

  it('shows the sign-in gate when no session exists', () => {
    expect(resolveAccessState({ token: '' })).toBe('signed-out')
  })

  it('returns signed-out after clearing the session', () => {
    expect(resolveAccessState({ token: '' })).toBe('signed-out')
    expect(resolveAccessState({ token: 'sds_after' })).toBe('connected')
  })
})
