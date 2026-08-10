# SALAR Authentication and Ambient Workspace Design

**Date:** 2026-08-10  
**Status:** Approved design  
**Scope:** Web frontend authentication, authenticated workspace, Live voice presentation, focused backend admin verification, and production validation

## Objective

Repair the live authentication failure without changing SALAR's configured Supabase login and signup providers. Replace the current authenticated command-center presentation with a focused, ChatGPT-familiar conversation experience that remains distinctly SALAR. Upgrade the existing `MagicRings` WebGL effect into a state-morphing Live voice presence.

The public cosmic landing page remains unchanged.

## Confirmed constraints

- Supabase remains the source of user identity and provider authentication.
- The SALAR backend continues issuing its own short-lived application token after validating a Supabase access token.
- `nwabjd@gmail.com` is the only admin email.
- Existing Google, GitHub, Azure, wallet, email OTP, onboarding, and payment entry points remain available.
- The animated orb appears only in Live voice mode, never in normal typed chat.
- Production deployment happens only after frontend, backend, build, responsive, and live integration checks pass.

## Current failure and root cause

The live `Open SALAR` action calls `onEnterApp` directly, which changes the application state to connected without proving that a valid SALAR backend session exists. Protected workspace requests then use a missing or expired token and display `Authentication expired — please log in again` inside the workspace.

Supabase and Render evidence also showed:

- A stale browser refresh token produced `refresh_token_not_found`.
- A subsequent Google login for the admin user succeeded in Supabase.
- The Supabase-to-SALAR exchange returned HTTP 200 on Render.
- Multiple auth events can start overlapping backend exchanges, creating a short stale-token race.

The repair must guard workspace entry and serialize backend session exchange.

## Authentication architecture

### Session coordinator

Introduce one frontend session coordinator responsible for all Supabase-to-SALAR handoff behavior. It owns a single in-flight exchange promise so `SIGNED_IN`, `TOKEN_REFRESHED`, initial boot, and manual app entry cannot create parallel exchanges.

The coordinator exposes clear outcomes:

- `connected`: the SALAR backend token was validated.
- `signed-out`: no valid Supabase identity is available.
- `recoverable-error`: the identity is valid but the backend is temporarily unavailable.

### Boot flow

1. Load the stored SALAR backend token.
2. If present, validate it through `/api/auth/session`.
3. If validation succeeds, enter the workspace.
4. If validation returns an authentication failure, obtain the current Supabase session and perform one serialized backend exchange.
5. Validate the newly issued SALAR token before entering the workspace.
6. If Supabase reports a stale or missing refresh token, clear stale local auth state and show the landing-page sign-in flow.
7. Never render the authenticated workspace before validation succeeds.

### Manual `Open SALAR` flow

`Open SALAR` becomes a guarded action:

- With a valid SALAR token, enter the workspace.
- With a valid Supabase identity, exchange and validate a SALAR token, then enter.
- Without a valid identity, open the existing authentication modal.
- While checking, show a localized progress state and prevent repeated clicks.

### Auth event flow

Register the Supabase auth listener early and route relevant events through the coordinator. `SIGNED_IN` and `TOKEN_REFRESHED` may request a handoff, but share the same in-flight promise. `SIGNED_OUT` clears both Supabase and SALAR application state. Transient events cannot bypass validation or force the workspace open.

### URL cleanup

Keep the existing redirect cleanup contract:

- Preserve the successful Supabase session handoff.
- Remove auth tokens, codes, and transient auth errors from query strings and hashes.
- Preserve unrelated query parameters and hash values.
- Perform at most one history replacement per cleanup.

### Admin rule

The backend continues deriving admin status from the normalized authenticated email. Only `nwabjd@gmail.com` is an admin. Existing users are synchronized to that rule during successful Supabase exchange. Tests must prove the approved address is promoted and all other addresses are non-admin.

## Authenticated workspace

### Direction

Use the approved Ambient Companion direction with ChatGPT-familiar interaction hierarchy. Familiarity comes from focus, conversation structure, and predictable controls—not copied OpenAI branding.

### Layout

- A collapsible history rail contains new conversation, recent conversations, and navigation.
- The main region is a generous conversation canvas with a constrained readable width.
- The composer remains anchored at the bottom and supports typing, Live mode, attachments where currently supported, and send.
- Usage, billing, account, and sign-out move into a compact profile menu.
- Memory, knowledge, calendar, devices, and existing tools remain available through a compact tools drawer.
- The current right-hand status-card rail is removed from the default conversation view.

### Empty and conversation states

New conversations show a restrained SALAR greeting and contextual starter prompts. Once messages exist, the greeting yields to a clean message stream. User and assistant messages use readable spacing, strong type hierarchy, and clear streaming/tool states without excessive card chrome.

### Responsive behavior

Desktop uses a collapsible side rail. Mobile and narrow tablet layouts use slide-over history and tools panels, a full-width composer with safe-area spacing, and the same information hierarchy. Touch targets, focus states, keyboard navigation, and reduced-motion behavior remain first-class.

## Live voice mode

### Visibility

The `MagicRings` orb is mounted only while Live voice mode is open. Typed chat remains visually quiet.

### State-morph motion grammar

- **Idle/starting:** a restrained core establishes presence while microphone setup completes.
- **Listening:** rings breathe slowly and respond to measured microphone volume without jitter.
- **Thinking:** rings contract slightly, counter-rotate, and accelerate with controlled noise.
- **Speaking:** rings expand in warm, audio-shaped pulses tied to SALAR playback rather than microphone input.

State values interpolate over time so transitions do not snap. The existing React component lifecycle remains stable; the WebGL renderer is not recreated when state or volume changes.

### Live interface

The orb remains central, with the current phase, transcript, tool activity, voice selection, text fallback, and close control composed around it. Text remains readable and does not overlap the animation at desktop or mobile breakpoints.

### Lifecycle and accessibility

Closing Live mode stops recording, playback, media tracks, audio contexts, timers, and scheduled callbacks. Reduced-motion mode replaces continuous rotation and strong pulses with subtle opacity and scale changes. Mobile lowers visual complexity and device pixel ratio where needed to protect frame rate and battery.

## Error handling

- Authentication failures are handled at the access boundary, not displayed inside an unauthorized workspace.
- A stale refresh token becomes a clear sign-in prompt.
- Temporary backend unavailability retains the valid Supabase identity and offers retry without falsely signing the user out.
- Repeated retry loops are prohibited; one recovery attempt occurs per failed protected-session check.
- Live microphone, speech-to-text, text-to-speech, and stream errors show direct recovery actions and leave resources in a clean state.

## Testing strategy

### Frontend authentication

Add focused tests covering:

- `Open SALAR` cannot bypass authentication.
- A valid stored SALAR token enters only after backend validation.
- An expired SALAR token is renewed through a valid Supabase session.
- A stale Supabase refresh token clears auth state and returns to sign-in.
- Concurrent Supabase auth events produce one backend exchange.
- Backend exchange failure is recoverable and does not destroy a valid Supabase identity.
- Successful handoff preserves existing URL cleanup behavior.

### Backend authentication

Keep token verification coverage for HS256 and asymmetric Supabase tokens. Confirm `nwabjd@gmail.com` is the only admin identity and all other emails are non-admin.

### Workspace and Live mode

Add focused component or state tests for:

- Empty conversation and populated conversation rendering.
- History and tools drawer behavior.
- Live orb visibility only in Live mode.
- Listening, thinking, and speaking state propagation.
- Live teardown of media and timers.
- Reduced-motion behavior.

### Verification

Before production deployment:

1. Run the complete frontend test suite.
2. Run the production frontend build.
3. Run the complete backend test suite.
4. Inspect desktop and mobile layouts in a browser.
5. Verify login and session renewal against Supabase and Render logs.
6. Confirm the production bundle contains the intended authenticated workspace changes.
7. Deploy to Hostinger only after an explicit production-write confirmation.
8. Verify `salaar.cloud` returns HTTP 200 and complete a live authenticated smoke test.

## Out of scope

- Changing Supabase providers or redirect domains unless verification proves a configuration defect.
- Adding more admin users.
- Replacing the existing voice pipeline or backend token model.
- Redesigning the public cosmic landing page.
- Changing payment pricing or payment-provider behavior.
