# SALAR visual and access correction

## Objective

Restore the last user-approved visual system exactly and remove the blocking email/password experience from the installed desktop application without weakening the public backend.

## Confirmed visual system

### Loading

- Use only the approved Strands loading treatment.
- Preserve the original Strands colors: `#F97316`, `#7C3AED`, and `#06B6D4`.
- Do not add rings, spheres, warm overlays, or dashboard effects to loading.

### Main dashboard

- Base canvas: near-black `#050308`.
- Mount the original React Bits `LiquidEther` component across the complete viewport.
- Preserve the exact component colors: `#5227FF`, `#FF9FFC`, and `#B497CF`.
- Preserve the accepted behavior: `mouseForce=20`, `cursorSize=100`, `resolution=0.5`, `autoDemo=true`, `autoSpeed=0.5`, and `autoIntensity=2.2`.
- Do not apply peach, orange, umber, cream, purple theme filters, blend modes, color remapping, warm glass, clouds, particles, spheres, or legacy ring artwork.
- Application chrome uses neutral smoke glass only. The animation is the sole chromatic source.
- Keep the interface minimal: floating top navigation, focused command composer, contextual conversation surface, and progressive secondary workspaces.

### Live Mode

- Base canvas: near-black `#03030A`.
- Mount only the original React Bits `MagicRings` component.
- Preserve exact colors `#FC42FF` and `#42FCFF` and the approved six-ring configuration.
- Do not display Liquid Ether, a sphere, a second ring system, a warm tint, or dashboard decoration while Live Mode is active.
- Display the live transcript and SALAR response as restrained neutral typography over the effect.

## Access model

### Desktop

- SALAR Desktop never opens to an email/password form.
- It enters the dashboard immediately after loading.
- A previously provisioned machine credential is restored from native application storage.
- When no credential exists, the dashboard remains usable as a shell and shows a non-blocking connection state. Provisioning lives in Settings rather than blocking launch.
- Once provisioned, the desktop maintains its authenticated backend session and continues device command polling.

### Web and iPhone PWA

- An unpaired browser sees a minimal six-digit pairing screen instead of email/password fields.
- A signed-in desktop creates a single-use pairing code.
- Pairing codes expire after five minutes and can be redeemed only once.
- Successful redemption issues a revocable device session and returns the browser directly to SALAR.
- The session persists on that device until it is revoked or explicitly disconnected.

### Backend and security

- Add device-session and pairing-code records with hashed secrets; raw secrets are returned only once.
- Pairing creation requires an authenticated owner or desktop device session.
- Pairing redemption is rate-limited and audited.
- Existing owner records, conversations, memories, documents, and legacy tokens remain valid during migration.
- Email/password authentication remains available as a recovery API but is removed from the normal client interface.
- Public deployments continue to require HTTPS. Ollama remains private behind FastAPI.

## Client state flow

1. Show approved Strands loader.
2. Detect Tauri desktop versus browser/PWA.
3. Desktop: restore machine credential if available, then open the dashboard regardless of connection state.
4. Browser/PWA: restore a device session; if absent, show pairing.
5. After pairing or provisioning, validate the session against `/api/auth/session`.
6. On expiry or revocation, desktop returns to the non-blocking disconnected state; web/PWA returns to pairing.

## Error handling

- Backend offline: dashboard remains visible with a compact offline status and retry action.
- Invalid or expired pairing code: keep the entered code visible and explain the failure inline.
- Revoked device: clear the device session and return to the correct platform-specific connection state.
- Microphone denied: Live Mode remains open and explains how to grant permission.
- Animation initialization failure: preserve the black canvas and functional interface without substituting a legacy animation.

## Verification

- Visual regression checks assert the exact background and component color constants and the absence of warm-theme overlays.
- Client tests cover desktop launch without credentials, browser pairing, persisted sessions, expiry, revocation, and backend-offline behavior.
- Backend tests cover one-time pairing, expiry, hashed storage, replay rejection, authorization, and device revocation.
- Existing backend, frontend, Rust safety, PWA, and installer builds must remain green.
- Rebuild both `dist/website` and `dist/installer/SALAR_1.0.0_x64-setup.exe` and inspect the packaged client, not only the development server.

## Out of scope

- Multi-user account administration.
- Third-party identity providers.
- Replacing the approved React Bits component sources.
- Changes to the SALAR application icon.
