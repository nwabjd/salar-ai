# SALAR Authentication and Ambient Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair SALAR's Supabase-to-backend session handoff and ship the approved focused workspace plus state-morphing Live voice orb.

**Architecture:** A pure, dependency-injected access coordinator serializes backend token validation and Supabase exchange so no UI action can bypass authentication. The existing React application consumes that coordinator, reshapes the authenticated shell without replacing providers or APIs, and delegates WebGL phase targets to a testable motion module while keeping one renderer instance alive.

**Tech Stack:** React, TypeScript, Vite, Vitest, Supabase JS, Three.js/WebGL, FastAPI, PyJWT, pytest

---

## File structure

- Create `frontend/src/auth/session-coordinator.ts`: pure serialized SALAR session validation and Supabase exchange.
- Create `frontend/src/auth/session-coordinator.test.ts`: guarded entry, renewal, stale identity, backend outage, and deduplication coverage.
- Modify `frontend/src/main.tsx`: consume the coordinator, guard all workspace entry, add conversation history and profile/tools controls, and connect Live output volume.
- Modify `frontend/src/components/SalaarLanding.tsx`: make `Open SALAR` await guarded entry and fall back to the existing auth modal.
- Create `frontend/src/effects/magic-rings-motion.ts`: deterministic phase-to-motion targets and interpolation.
- Create `frontend/src/effects/magic-rings-motion.test.ts`: phase distinction and reduced-motion target coverage.
- Modify `frontend/src/effects/MagicRings.jsx`: interpolate state targets without recreating WebGL resources.
- Modify `frontend/src/styles.css`: focused authenticated workspace, responsive drawers, and Live composition.
- Modify `frontend/src/theme.css`: restrained neutral authenticated palette and one SALAR violet accent.
- Modify `backend/app/api/auth.py`: keep the single approved admin address explicit and normalized.
- Modify `backend/tests/test_auth.py`: prove the approved address is the only admin.

### Task 1: Serialized access coordinator

**Files:**
- Create: `frontend/src/auth/session-coordinator.ts`
- Test: `frontend/src/auth/session-coordinator.test.ts`

- [ ] **Step 1: Write failing coordinator tests**

Cover valid stored token, expired token renewed through Supabase, missing Supabase identity, temporary exchange failure, and two simultaneous `connect()` calls sharing one exchange. Use dependency spies such as:

```ts
const coordinator = createSessionCoordinator({
  loadBackendToken: vi.fn().mockResolvedValue('expired'),
  saveBackendToken: vi.fn(),
  clearBackendToken: vi.fn(),
  validateBackendToken: vi.fn(async token => token === 'fresh'),
  getSupabaseToken: vi.fn().mockResolvedValue('supabase-token'),
  exchangeSupabaseToken: vi.fn().mockResolvedValue('fresh'),
})

const [first, second] = await Promise.all([coordinator.connect(), coordinator.connect()])
expect(first.status).toBe('connected')
expect(second.status).toBe('connected')
expect(deps.exchangeSupabaseToken).toHaveBeenCalledTimes(1)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- --run src/auth/session-coordinator.test.ts`  
Expected: FAIL because `createSessionCoordinator` does not exist.

- [ ] **Step 3: Implement the coordinator**

Define:

```ts
export type SessionResult =
  | { status: 'connected'; token: string }
  | { status: 'signed-out' }
  | { status: 'backend-unavailable'; message: string }

export function createSessionCoordinator(deps: SessionDependencies) {
  let inFlight: Promise<SessionResult> | null = null
  const connect = (supabaseToken?: string | null) => {
    if (inFlight) return inFlight
    inFlight = connectOnce(deps, supabaseToken).finally(() => { inFlight = null })
    return inFlight
  }
  return { connect }
}
```

`connectOnce` validates a stored backend token first, obtains or accepts a Supabase token only when renewal is needed, exchanges once, saves the result, then validates the new backend token before returning `connected`.

- [ ] **Step 4: Run focused and full frontend tests**

Run: `npm test -- --run src/auth/session-coordinator.test.ts`  
Expected: PASS.  
Run: `npm test -- --run`  
Expected: all existing and new tests PASS.

- [ ] **Step 5: Commit the coordinator**

```bash
git add frontend/src/auth/session-coordinator.ts frontend/src/auth/session-coordinator.test.ts
git commit -m "fix(auth): serialize backend session handoff"
```

### Task 2: Guard boot, auth events, and manual app entry

**Files:**
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/components/SalaarLanding.tsx`
- Modify: `frontend/src/landing-auth-contract.test.ts`

- [ ] **Step 1: Extend the landing auth contract test**

Require the landing component to await a guarded result instead of calling an unvalidated state setter:

```ts
expect(landing).toContain('await onEnterApp?.()')
expect(landing).toContain('if (!entered)')
expect(landing).not.toContain('onClick={onEnterApp}>Open SALAR')
```

- [ ] **Step 2: Run the contract test and verify RED**

Run: `npm test -- --run src/landing-auth-contract.test.ts`  
Expected: FAIL because `Open SALAR` still calls `onEnterApp` directly.

- [ ] **Step 3: Wire the coordinator into `App`**

Create one coordinator with adapters for `storedSession`, `saveSession`, `clearSession`, `api.validateSession`, `api.supabaseLogin`, and a verified Supabase session getter. Treat a Supabase `getSession()` error as signed-out and clear local Supabase state with `signOut({ scope: 'local' })`.

Replace direct `setAccess('connected')` entry with:

```ts
const enterApp = useCallback(async (supabaseToken?: string | null) => {
  setAccess('checking')
  const result = await sessionCoordinator.connect(supabaseToken)
  if (result.status === 'connected') {
    api.token = result.token
    setAccess('connected')
    return true
  }
  setAccess('signed-out')
  return false
}, [])
```

Boot and the five-second health check use the same coordinator. Relevant Supabase auth events call `enterApp(session?.access_token)` and therefore share the coordinator's in-flight promise.

- [ ] **Step 4: Guard `Open SALAR` in the landing component**

Change the prop to `onEnterApp?: () => Promise<boolean>`. Add a busy guarded handler. If entry fails, call the existing `launchSignup()` instead of rendering the workspace.

- [ ] **Step 5: Run focused and full frontend tests**

Run: `npm test -- --run src/landing-auth-contract.test.ts src/auth/session-coordinator.test.ts`  
Expected: PASS.  
Run: `npm test -- --run`  
Expected: all tests PASS.

- [ ] **Step 6: Commit guarded entry**

```bash
git add frontend/src/main.tsx frontend/src/components/SalaarLanding.tsx frontend/src/landing-auth-contract.test.ts
git commit -m "fix(auth): guard every workspace entry"
```

### Task 3: Confirm the single-admin backend rule

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/tests/test_auth.py`

- [ ] **Step 1: Add a failing non-admin boundary test**

```py
def test_only_approved_email_is_admin(client, supabase_token):
    for email in ('admin@example.com', 'owner@example.com', 'nwabjd+alias@gmail.com'):
        response = client.post('/api/auth/supabase', json={'token': supabase_token(email=email)})
        profile = client.get('/api/auth/me', headers={'Authorization': f"Bearer {response.json()['access_token']}"})
        assert profile.json()['is_admin'] is False
```

- [ ] **Step 2: Run the focused backend test**

Run: `python -m pytest tests/test_auth.py -q`  
Expected: the new boundary test passes against the current rule; if so, retain it as regression evidence and proceed with the naming cleanup only.

- [ ] **Step 3: Make the rule explicit and immutable**

Rename the constant to `SOLE_ADMIN_EMAIL` and keep normalized exact comparison:

```py
SOLE_ADMIN_EMAIL = 'nwabjd@gmail.com'
is_admin = email.strip().lower() == SOLE_ADMIN_EMAIL
```

- [ ] **Step 4: Run auth and full backend suites**

Run: `python -m pytest tests/test_auth.py -q`  
Expected: PASS.  
Run: `python -m pytest -q`  
Expected: all backend tests PASS.

- [ ] **Step 5: Commit admin verification**

```bash
git add backend/app/api/auth.py backend/tests/test_auth.py
git commit -m "test(auth): lock admin access to approved email"
```

### Task 4: Focused conversation workspace

**Files:**
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/theme.css`
- Create: `frontend/src/workspace-contract.test.ts`

- [ ] **Step 1: Write a failing workspace contract test**

Assert the source contains a conversation history rail, new conversation control, tools drawer, profile menu, and the approved empty-state copy, while the default workspace no longer renders `StatusRail` as a permanent column.

```ts
expect(main).toContain('New conversation')
expect(main).toContain('Recent conversations')
expect(main).toContain('Tools')
expect(main).toContain('How can I help?')
expect(main).not.toContain('<StatusRail/>')
```

- [ ] **Step 2: Run the contract test and verify RED**

Run: `npm test -- --run src/workspace-contract.test.ts`  
Expected: FAIL because the current workspace uses a fixed right status rail.

- [ ] **Step 3: Reshape `Chat` around conversation selection**

Load all conversations into state, select the newest available conversation, add `createNewConversation`, and add `selectConversation`. Render recent conversation buttons in a collapsible rail. Preserve the existing streaming implementation and API calls.

- [ ] **Step 4: Replace permanent status rail with drawers and menus**

Move usage and sign-out to a profile menu. Move existing WhatsApp, calendar, memory, knowledge, and device status content into a tools drawer opened from the rail. Keep all existing API status calls and pricing overlay behavior.

- [ ] **Step 5: Apply the authenticated visual system**

Use an off-black neutral canvas, one restrained violet accent, readable 680–760px conversation width, unboxed assistant messages, compact user bubbles, a fixed rounded composer, visible keyboard focus, pressed states, and smooth 180–240ms transitions. Add desktop collapse and mobile slide-over behavior at `900px` and `640px` breakpoints.

- [ ] **Step 6: Run tests and production build**

Run: `npm test -- --run src/workspace-contract.test.ts`  
Expected: PASS.  
Run: `npm test -- --run`  
Expected: all tests PASS.  
Run: `npm run build`  
Expected: TypeScript and Vite build succeed; a bundle-size advisory is acceptable.

- [ ] **Step 7: Commit workspace redesign**

```bash
git add frontend/src/main.tsx frontend/src/styles.css frontend/src/theme.css frontend/src/workspace-contract.test.ts
git commit -m "feat(ui): build focused ambient workspace"
```

### Task 5: Testable state-morph motion

**Files:**
- Create: `frontend/src/effects/magic-rings-motion.ts`
- Create: `frontend/src/effects/magic-rings-motion.test.ts`
- Modify: `frontend/src/effects/MagicRings.jsx`

- [ ] **Step 1: Write failing motion target tests**

```ts
expect(getRingMotionTarget('listening', 30, false).scaleRate)
  .toBeLessThan(getRingMotionTarget('speaking', 30, false).scaleRate)
expect(getRingMotionTarget('thinking', 0, false).rotationSpeed).not.toBe(0)
expect(getRingMotionTarget('speaking', 60, true).rotationSpeed).toBe(0)
```

- [ ] **Step 2: Run the motion test and verify RED**

Run: `npm test -- --run src/effects/magic-rings-motion.test.ts`  
Expected: FAIL because the motion module does not exist.

- [ ] **Step 3: Implement deterministic phase targets**

Export `VoicePhase`, `RingMotionTarget`, `getRingMotionTarget`, and `approachMotionTarget`. Clamp volume to `0..1`. Reduced motion must remove continuous rotation, sharply reduce scale range, and retain visible phase distinction through opacity and line thickness.

- [ ] **Step 4: Make `MagicRings` interpolate targets**

Replace snapping phase branches with one mutable visual state that approaches the target each animation frame. Continue reading props through `propsRef`; keep the renderer effect dependency array empty so state changes never recreate WebGL resources.

- [ ] **Step 5: Run focused and full frontend tests**

Run: `npm test -- --run src/effects/magic-rings-motion.test.ts`  
Expected: PASS.  
Run: `npm test -- --run`  
Expected: all tests PASS.

- [ ] **Step 6: Commit motion behavior**

```bash
git add frontend/src/effects/magic-rings-motion.ts frontend/src/effects/magic-rings-motion.test.ts frontend/src/effects/MagicRings.jsx
git commit -m "feat(live): add state-morphing voice orb"
```

### Task 6: Connect speaking output and polish Live composition

**Files:**
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/effects/MagicRings.css`
- Create: `frontend/src/live-mode-contract.test.ts`

- [ ] **Step 1: Write a failing Live-mode contract test**

Assert `MagicRings` only occurs inside `Live`, all four phase labels are present, output-volume sampling is wired during TTS, and teardown stops tracks and closes the audio context.

- [ ] **Step 2: Run the contract test and verify RED**

Run: `npm test -- --run src/live-mode-contract.test.ts`  
Expected: FAIL because speaking currently reacts to microphone volume rather than TTS output.

- [ ] **Step 3: Sample TTS output volume**

In `playTtsBlob`, connect the buffer source through an `AnalyserNode` before `ctx.destination`. Sample its frequency data while playback is active and update `volume`. The microphone monitor updates volume only while listening; thinking resets toward zero.

- [ ] **Step 4: Complete lifecycle cleanup**

Track and cancel output sampling animation frames or intervals. Ensure `teardown` clears microphone and output monitors, recording timers, queued TTS, media tracks, and the audio context before calling `onClose`.

- [ ] **Step 5: Apply the approved Live layout**

Keep the orb central. Place state label above the transcript, keep tool activity and transcript below the orb, retain voice selection and text fallback, and use safe-area-aware controls. Add `prefers-reduced-motion` and mobile shader-container sizing.

- [ ] **Step 6: Run tests and build**

Run: `npm test -- --run src/live-mode-contract.test.ts src/effects/magic-rings-motion.test.ts`  
Expected: PASS.  
Run: `npm test -- --run`  
Expected: all tests PASS.  
Run: `npm run build`  
Expected: build succeeds.

- [ ] **Step 7: Commit Live integration**

```bash
git add frontend/src/main.tsx frontend/src/styles.css frontend/src/effects/MagicRings.css frontend/src/live-mode-contract.test.ts
git commit -m "feat(live): connect orb to voice output"
```

### Task 7: Local browser and responsive verification

**Files:**
- Modify only if verification exposes a defect in the files already listed.

- [ ] **Step 1: Start the production preview**

Run: `npm run build` then `npm exec vite preview -- --host 127.0.0.1 --port 4173` from `frontend`.  
Expected: preview serves HTTP 200.

- [ ] **Step 2: Verify guarded entry**

With no browser session, click `Open SALAR`. Expected: the existing auth modal opens and the workspace never appears. Confirm no protected workspace request is sent with an empty token.

- [ ] **Step 3: Verify authenticated desktop workspace**

Complete the approved admin login. Expected: one backend exchange, successful `/api/auth/session`, focused conversation canvas, functional recent-conversation selection, tools drawer, profile menu, and sign-out.

- [ ] **Step 4: Verify responsive layouts**

Inspect widths `1440`, `1024`, `768`, and `390`. Expected: no horizontal overflow, drawers remain reachable, composer stays visible, and touch targets remain at least 44px on mobile.

- [ ] **Step 5: Verify Live phases**

Open Live mode and observe starting, listening, thinking, and speaking. Expected: the orb is absent from typed chat, motion transitions are smooth, speaking follows output audio, and closing releases microphone access.

- [ ] **Step 6: Run final local checks**

Run: `npm test -- --run && npm run build` in `frontend`.  
Run: `python -m pytest -q` in `backend`.  
Expected: every test and build passes.

### Task 8: Production readiness and deployment

**Files:**
- Build artifact only; no source modification unless verification finds a defect.

- [ ] **Step 1: Inspect Git and build scope**

Run: `git status --short` and review diffs only for files in this plan. Preserve unrelated user changes and do not package preview or temporary artifacts.

- [ ] **Step 2: Confirm Supabase and Render health**

Check Supabase project status and recent auth logs. Check Render service health, current deploy, and auth request logs. Expected: Supabase active, Render healthy, and no unexplained auth exchange failures.

- [ ] **Step 3: Request production-write confirmation**

State the exact Hostinger domain, build archive, and replacement operation. Do not deploy until the user confirms.

- [ ] **Step 4: Deploy the static build**

Create an archive with `index.html` at its root and deploy it to `salaar.cloud` through the Hostinger static-site deployment operation.

- [ ] **Step 5: Verify production**

Confirm `https://salaar.cloud` returns HTTP 200, serves the new asset hash, contains the new workspace code, and completes one authenticated admin smoke test. Recheck Supabase and Render logs for the successful handoff.

## Self-review

- Every approved spec requirement maps to Tasks 1–8.
- Existing Supabase providers, landing page, payment entry points, and backend token model remain intact.
- The only admin address is explicit and tested.
- All behavior changes begin with focused failing tests or, for the existing admin rule, a regression test that documents already-correct behavior.
- Production deployment remains separately confirmed because it replaces live hosted files.
