# SALAR Chat Restoration, Landing Performance, and Realtime Voice Design

Date: 2026-08-10
Status: Approved

## Goal

Restore the authenticated SALAR chat presentation that existed immediately before the Ambient Companion redesign, replace the public landing's CPU-heavy particle renderer with a restrained full-page LiquidEther layer, and replace Live mode's chunked record/transcribe/TTS loop with an authenticated OpenAI Realtime speech-to-speech session.

## Scope

This change affects three isolated surfaces:

1. The authenticated chat layout and its background treatment.
2. The decorative renderer behind the public landing page.
3. The Live voice transport, turn detection, transcription, audio playback, and phase state.

It does not change Supabase login or signup providers, the guarded session handoff, URL credential cleanup, billing behavior, the sole administrator rule, or the public landing's content and pricing.

## Authenticated Chat Restoration

The authenticated application returns to the structure that existed before commit `c5239b3`:

- the original glass top bar;
- the centered plan and usage control;
- separate Live and Sign Out actions;
- the original conversation presentation and composer;
- the permanent API-backed status rail;
- the original LiquidEther palette at full opacity and saturation.

The conversation rail, Tools drawer, profile popover, muted LiquidEther override, and Ambient-specific layout rules are removed. Session recovery and all later Live improvements remain.

## Landing Renderer

The `CosmicIntelligence` particle canvas and its central core are no longer mounted. The landing instead mounts one fixed, viewport-sized `LiquidEther` layer behind every section.

The landing preset uses the same purple, pink, and lavender palette as authenticated chat while lowering simulation cost through reduced render resolution, fewer pressure iterations, slower automatic motion, lower interaction force, and no unnecessary viscosity pass. The static vignette remains to preserve text contrast. The grain and particle-like overlays are removed.

LiquidEther remains decorative, does not intercept content interactions, pauses when not visible through its existing lifecycle behavior, and honors reduced-motion preferences through a quiet fallback treatment.

## Realtime Voice Architecture

### Transport and security

The browser opens an authenticated WebSocket to SALAR's `/ws/live` endpoint. Its first setup message contains the existing SALAR backend session token. The backend validates that token before opening any upstream connection.

The backend connects server-to-server to OpenAI Realtime using an environment-only `SALAR_OPENAI_API_KEY`. The credential is never returned to the browser, placed in source code, written to local project files, logged, or committed.

### Session configuration

The backend configures an OpenAI Realtime session with:

- model `gpt-realtime`;
- audio output with a high-quality built-in voice;
- 24 kHz mono PCM input and output;
- far-field input noise reduction for typical laptop microphones;
- `gpt-4o-mini-transcribe` input transcription;
- low-eagerness semantic voice activity detection;
- automatic response creation;
- automatic interruption when the user starts speaking;
- concise SALAR voice instructions.

### Browser audio

The existing AudioWorklet becomes the only microphone capture and playback mechanism. It resamples microphone input to 24 kHz mono PCM16 and emits approximately 100 ms chunks. Received OpenAI audio deltas are decoded to PCM16 and queued directly in the worklet.

The worklet reports playback-started and playback-drained events. Live mode does not return to Listening merely because the network response is complete; it waits until the final queued audio sample has played.

### State and transcripts

Live uses an explicit state machine:

- `connecting`: WebSocket, microphone, and worklet initialization;
- `listening`: authenticated stream ready and accepting user audio;
- `thinking`: a committed user turn is awaiting model output;
- `speaking`: response audio is arriving or remains queued for playback;
- `error`: a recoverable connection or permission failure is shown clearly.

Input transcription events update the user's visible transcript. Output transcript deltas update SALAR's visible response. Completed turns are appended to the local Live history. Starting user speech during Speaking clears queued output immediately and returns visual control to Listening.

The orb remains exclusive to Live mode and receives microphone energy during Listening and output playback energy during Speaking.

## Failure Handling

- Invalid or missing SALAR session tokens close the Live socket with an authentication error.
- A missing OpenAI server credential returns a configuration error without exposing environment details.
- Microphone denial leaves Live open with a clear retryable message and typed fallback.
- WebSocket closure stops capture and playback, releases media tracks and the audio context, and presents reconnect guidance.
- No silent fallback to the old chunked voice pipeline is used; this prevents the premature-listening bug from returning unnoticed.

## Testing

Frontend tests will prove:

- the original authenticated chat contract is restored;
- the landing mounts LiquidEther and no particle canvas/core;
- the tuned landing preset remains lower cost than the chat preset;
- the Live state machine does not return to Listening until playback drains;
- input/output transcript events update the correct visible turn;
- interruption clears playback;
- cleanup closes the socket, worklet, audio context, and microphone tracks.

Backend tests will prove:

- Live rejects invalid backend sessions;
- the OpenAI credential stays server-side;
- the expected Realtime session configuration is sent;
- audio and transcription events are translated correctly in both directions;
- upstream failures are sanitized for the browser.

The final gate includes all frontend tests, the production frontend build, all backend tests, browser checks on desktop and mobile breakpoints, Render deployment health, and live content verification on `salaar.cloud`.

## Deployment

After verification, the OpenAI key is added to the Render service as `SALAR_OPENAI_API_KEY` through the connected Render environment manager. Source commits are pushed to `main` to trigger Render's automatic deployment. The static frontend build is deployed to the existing Hostinger website for `salaar.cloud`, its cache is cleared, and both services are checked for real content and healthy responses.

Because the initial OpenAI key was shared in conversation, it should be rotated after deployment and the Render environment value replaced with the rotated key.
