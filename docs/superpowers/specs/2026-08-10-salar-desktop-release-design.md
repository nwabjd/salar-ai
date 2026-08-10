# SALAR Desktop Release and WhatsApp Polish Design

## Release outcome

Ship one coherent SALAR release across the public website and Windows desktop: the same React interface and Gemini Live behavior, a downloadable Windows installer, clear future-platform availability, and a professional WhatsApp assistant identity.

## Desktop architecture

Keep Tauri 2 as the Windows shell and bundle the production frontend directly into it. This preserves feature parity automatically: authentication, chat, Liquid Ether, Gemini Live, pricing, and future frontend changes use the same source as salaar.cloud. The installer remains per-user NSIS so users do not need administrator access.

The release script builds and tests the shared frontend, builds the Tauri installer, places a stable copy at `website/downloads/SALAR-Setup.exe`, and writes the same artifact to `dist/installer`. The website can therefore use a permanent download URL even when the versioned Tauri filename changes.

## Website experience

Add `Get SALAR` to the main navigation and a dedicated cross-platform section before pricing. Windows is the active card with a direct installer download and a concise compatibility note. macOS, iOS, and Android remain visible with non-interactive `Coming soon` badges. On narrow screens the cards stack without changing the landing page's visual language or Liquid Ether performance profile.

## WhatsApp behavior

SALAR identifies itself as `JD's assistant`, answers concrete queries directly when it has reliable information, and asks a focused follow-up when the sender has not provided enough detail. It never pretends to be JD, never fabricates, and does not respond with blunt refusal language. Requests to pass something to JD continue through the existing audited pass-message mechanism.

## Verification

Focused frontend tests cover the download URL, platform badges, and shared desktop source contract. Backend tests cover the WhatsApp prompt contract. The full frontend suite/build, backend suite, Rust tests, and Tauri release build must pass before deployment.
