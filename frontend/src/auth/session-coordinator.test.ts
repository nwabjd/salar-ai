import { describe, expect, it, vi } from 'vitest'
import { createSessionCoordinator, type SessionDependencies } from './session-coordinator'

function dependencies(overrides: Partial<SessionDependencies> = {}): SessionDependencies {
  return {
    loadBackendToken: vi.fn().mockResolvedValue(''),
    saveBackendToken: vi.fn().mockResolvedValue(undefined),
    clearBackendToken: vi.fn().mockResolvedValue(undefined),
    validateBackendToken: vi.fn().mockResolvedValue(false),
    getSupabaseToken: vi.fn().mockResolvedValue(null),
    exchangeSupabaseToken: vi.fn().mockResolvedValue(''),
    ...overrides,
  }
}

describe('SALAR session coordinator', () => {
  it('accepts a stored backend token only after validation', async () => {
    const deps = dependencies({
      loadBackendToken: vi.fn().mockResolvedValue('stored'),
      validateBackendToken: vi.fn().mockResolvedValue(true),
    })

    const result = await createSessionCoordinator(deps).connect()

    expect(result).toEqual({ status: 'connected', token: 'stored' })
    expect(deps.exchangeSupabaseToken).not.toHaveBeenCalled()
  })

  it('renews an expired backend token through the current Supabase identity', async () => {
    const validateBackendToken = vi.fn(async (token: string) => token === 'fresh')
    const deps = dependencies({
      loadBackendToken: vi.fn().mockResolvedValue('expired'),
      validateBackendToken,
      getSupabaseToken: vi.fn().mockResolvedValue('supabase-token'),
      exchangeSupabaseToken: vi.fn().mockResolvedValue('fresh'),
    })

    const result = await createSessionCoordinator(deps).connect()

    expect(result).toEqual({ status: 'connected', token: 'fresh' })
    expect(deps.saveBackendToken).toHaveBeenCalledWith('fresh')
    expect(validateBackendToken).toHaveBeenNthCalledWith(1, 'expired')
    expect(validateBackendToken).toHaveBeenNthCalledWith(2, 'fresh')
  })

  it('returns signed out and clears only the backend token without a Supabase identity', async () => {
    const deps = dependencies({ loadBackendToken: vi.fn().mockResolvedValue('expired') })

    const result = await createSessionCoordinator(deps).connect()

    expect(result).toEqual({ status: 'signed-out' })
    expect(deps.clearBackendToken).toHaveBeenCalledOnce()
  })

  it('keeps a valid Supabase identity recoverable when the backend is unavailable', async () => {
    const deps = dependencies({
      getSupabaseToken: vi.fn().mockResolvedValue('supabase-token'),
      exchangeSupabaseToken: vi.fn().mockRejectedValue(new Error('offline')),
    })

    const result = await createSessionCoordinator(deps).connect()

    expect(result.status).toBe('backend-unavailable')
    expect(deps.clearBackendToken).toHaveBeenCalledOnce()
  })

  it('deduplicates simultaneous handoff attempts', async () => {
    let release!: (token: string) => void
    const exchanged = new Promise<string>((resolve) => { release = resolve })
    const deps = dependencies({
      getSupabaseToken: vi.fn().mockResolvedValue('supabase-token'),
      exchangeSupabaseToken: vi.fn().mockReturnValue(exchanged),
      validateBackendToken: vi.fn(async (token: string) => token === 'fresh'),
    })
    const coordinator = createSessionCoordinator(deps)

    const first = coordinator.connect()
    const second = coordinator.connect('supabase-token')
    release('fresh')

    expect(await first).toEqual({ status: 'connected', token: 'fresh' })
    expect(await second).toEqual({ status: 'connected', token: 'fresh' })
    expect(deps.exchangeSupabaseToken).toHaveBeenCalledTimes(1)
  })
})
