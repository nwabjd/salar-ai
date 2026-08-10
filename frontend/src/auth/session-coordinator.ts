export type SessionResult =
  | { status: 'connected'; token: string }
  | { status: 'signed-out' }
  | { status: 'backend-unavailable'; message: string }

export type SessionDependencies = {
  loadBackendToken: () => Promise<string>
  saveBackendToken: (token: string) => Promise<void>
  clearBackendToken: () => Promise<void>
  validateBackendToken: (token: string) => Promise<boolean>
  getSupabaseToken: () => Promise<string | null>
  exchangeSupabaseToken: (token: string) => Promise<string>
}

async function isValid(deps: SessionDependencies, token: string): Promise<boolean> {
  if (!token) return false
  try {
    return await deps.validateBackendToken(token)
  } catch {
    return false
  }
}

async function connectOnce(
  deps: SessionDependencies,
  suppliedSupabaseToken?: string | null,
): Promise<SessionResult> {
  const hasSuppliedIdentity = suppliedSupabaseToken !== undefined

  if (!hasSuppliedIdentity) {
    const stored = await deps.loadBackendToken().catch(() => '')
    if (await isValid(deps, stored)) return { status: 'connected', token: stored }
  }

  let supabaseToken = suppliedSupabaseToken
  if (!hasSuppliedIdentity) {
    try {
      supabaseToken = await deps.getSupabaseToken()
    } catch {
      supabaseToken = null
    }
  }

  if (!supabaseToken) {
    await deps.clearBackendToken()
    return { status: 'signed-out' }
  }

  try {
    const backendToken = await deps.exchangeSupabaseToken(supabaseToken)
    await deps.saveBackendToken(backendToken)
    if (!(await isValid(deps, backendToken))) {
      await deps.clearBackendToken()
      return { status: 'backend-unavailable', message: 'SALAR could not validate the new session.' }
    }
    return { status: 'connected', token: backendToken }
  } catch (reason) {
    await deps.clearBackendToken()
    return {
      status: 'backend-unavailable',
      message: reason instanceof Error ? reason.message : 'SALAR is temporarily unavailable.',
    }
  }
}

export function createSessionCoordinator(deps: SessionDependencies) {
  let inFlight: Promise<SessionResult> | null = null

  function connect(supabaseToken?: string | null): Promise<SessionResult> {
    if (inFlight) return inFlight
    inFlight = connectOnce(deps, supabaseToken).finally(() => { inFlight = null })
    return inFlight
  }

  return { connect }
}
