# SALAR Native Gemini Live Design

**Status:** Approved for implementation planning  
**Date:** 2026-08-10

## Objective

Replace SALAR's OpenAI Realtime dependency with native Gemini Live while preserving the current Live interface. Live mode must feel responsive and conversational, speak every completed response, support interruption, display accurate transcripts, and degrade gracefully instead of presenting repeated generic errors.

## Scope

This change covers the authenticated Live voice transport, Gemini session configuration, browser audio streaming and playback, Live state translation, automatic fallback, error handling, tests, and production deployment. The existing Live visual interface—including MagicRings, transcript history, typed input, close control, and Listening, Thinking, and Speaking labels—must remain visually unchanged.

The ordinary text chat interface, landing page, Supabase authentication, billing, WhatsApp, and other SALAR tools are outside this change except where the existing chat endpoint is reused by the fallback path.

## Chosen Approach

Use native Gemini Live as the primary voice engine and retain the existing Gemini STT → streamed chat → Gemini TTS pipeline as an automatic fallback.

Native-only operation was rejected because a preview-model outage or session reset would leave Live unusable. The legacy pipeline alone was rejected because its record-then-process cycle has higher latency and less natural interruption behavior. The hybrid approach provides native speech-to-speech quality during normal operation and a functional voice experience during recoverable Live API failures.

## Architecture

### Browser

The current `Live` React component remains the visible interface. A provider-neutral voice client will preserve the existing event contract used by the Live reducer: ready, speech started, speech stopped, audio, input transcript, output transcript, response done, playback drained, reconnecting, and error.

The browser will:

- capture mono microphone audio through the existing AudioWorklet;
- resample microphone input to raw signed 16-bit little-endian PCM at 16kHz;
- send short audio chunks through SALAR's authenticated WebSocket;
- receive raw signed 16-bit PCM output at 24kHz;
- queue output without gaps and stop queued playback immediately when interrupted;
- keep typed Live messages available through the same session;
- expose playback and microphone volume to the existing rings;
- stop all tracks, worklets, timers, sockets, and queued audio when Live closes.

The browser never receives or stores the Gemini API key.

### SALAR backend

SALAR keeps the existing `/ws/live` boundary. The first browser message must contain the current SALAR application token, and the backend must validate it before opening any upstream connection.

After authentication, the backend opens a server-to-server Gemini Live session using the configured Gemini API key and `gemini-3.1-flash-live-preview`. The session configuration will request native audio output, input and output transcription, the Kore voice, low-latency thinking, automatic activity detection, context-window compression, and session resumption.

The backend translates Gemini protocol messages into SALAR's stable browser event contract. Gemini-specific message shapes must not leak into React components.

## Data Flow

1. The user opens Live mode and grants microphone access.
2. The browser opens `/ws/live` and sends the SALAR session token.
3. The backend validates the user and opens Gemini Live.
4. When Gemini confirms setup, SALAR emits `ready` and the UI enters Listening.
5. The worklet streams 16kHz PCM microphone chunks continuously.
6. Gemini's activity detection drives speech-started and speech-stopped state changes.
7. Input transcription updates what SALAR heard.
8. Gemini streams native 24kHz audio and output transcription; the browser enters Speaking and plays audio immediately.
9. A user interruption clears pending playback as soon as Gemini reports interruption.
10. Generation completion and playback drain are tracked separately so Listening resumes only after SALAR has finished speaking.

Typed messages use Gemini's real-time text input within the same Live session and follow the same response and playback path.

## Automatic Fallback

The fallback activates only when native Gemini Live cannot establish or maintain a usable session after a bounded reconnect attempt. Authentication failures and microphone denial do not trigger fallback because the legacy path cannot correct them.

During fallback:

- the current Live UI remains mounted;
- the label briefly shows `Reconnecting…` rather than an error stack;
- microphone turns are recorded with conservative silence detection;
- `/api/stt` uses Gemini transcription with the existing local Whisper fallback;
- the existing authenticated streaming chat endpoint produces the response;
- `/api/tts` generates Gemini speech, retaining the existing speech fallback where available;
- transcript history and phase events continue through the same reducer contract.

A later Live entry starts with native Gemini Live again. The initial implementation will not switch from fallback back to native mode during an active response, avoiding duplicated speech and split conversation state.

## Responsiveness and Audio Behavior

- Send microphone chunks in the 20–40ms range.
- Use 16kHz PCM input and 24kHz PCM output.
- Begin playback as soon as the first valid output chunk arrives.
- Maintain a small ordered playback queue rather than waiting for a complete response.
- Keep automatic gain control, echo cancellation, and browser noise suppression enabled.
- Tune activity detection to avoid triggering on brief background noise while preserving natural pauses.
- Cancel queued playback immediately on interruption.
- Use low Gemini thinking depth for conversational latency.
- Apply context compression and retain resumption handles for long-running sessions.

## Error Handling

Errors are classified at the backend boundary and converted to stable user-facing states:

- microphone denied: show a clear retryable microphone message and keep typed Live input available;
- authentication expired: ask the user to sign in again;
- Gemini configuration missing: show `Live voice is not configured`;
- temporary upstream failure or planned session reset: show `Reconnecting…`, attempt bounded reconnection, then activate fallback;
- fallback STT, chat, or TTS failure: preserve the transcript and offer retry or typed input without looping;
- explicit user close: close silently without emitting a disconnected error.

One underlying failure must produce at most one visible status. Generic `Realtime service error`, `Live voice disconnected`, and `Live unavailable` messages must not overwrite a more specific cause.

Logs may include provider error type, status, and safe error code. They must never include API keys, SALAR tokens, raw audio, or complete private transcripts.

## Configuration

Add a dedicated server-side Gemini Live model setting with `gemini-3.1-flash-live-preview` as the default. Continue using the existing server-side Gemini API key. The OpenAI key is no longer required for Live mode and must not be referenced by the Live connection path.

## Testing

Backend tests will cover:

- authentication before upstream connection;
- Gemini setup configuration and model selection;
- 16kHz input message translation;
- audio, transcript, activity, interruption, completion, GoAway, and resumption event translation;
- sanitized provider errors;
- bounded reconnect and fallback activation;
- explicit close without duplicate errors.

Frontend tests will cover:

- 16kHz capture and 24kHz playback contracts;
- the existing Live reducer phases;
- transcript accumulation and conversation history;
- immediate playback cancellation on interruption;
- native-to-fallback transition through `Reconnecting…`;
- suppression of duplicate disconnect errors;
- cleanup of microphone, socket, worklet, and audio resources;
- preservation of the existing Live visual contract.

Verification requires the focused Live tests, the full backend suite, the full frontend suite, and a production frontend build. Production verification must confirm the Render backend deployment, Hostinger asset deployment, authenticated WebSocket setup, visible transcripts, spoken audio, interruption, and successful fallback behavior.

## Deployment

Deploy the backend first so the authenticated `/ws/live` endpoint supports Gemini before the frontend switches providers. After Render is live and healthy, deploy the static frontend build to `salaar.cloud`, verify the exact new asset hashes and real page content, then test an authenticated Live session in production.

Hostinger writes require the normal explicit confirmation immediately before upload. Render and browser logs must be checked after the production voice test for provider or playback errors.

## Success Criteria

- Live mode uses Gemini rather than OpenAI.
- The existing Live interface is visually unchanged.
- The user can speak naturally and see an accurate input transcript.
- SALAR streams and audibly speaks its response.
- The user can interrupt SALAR without stale audio continuing.
- Listening resumes only after response generation and playback both finish.
- Temporary Gemini Live failures transition through Reconnecting and then the functional fallback path.
- A single failure never produces stacked or contradictory error messages.
- API keys remain server-side.
- All relevant tests and builds pass before deployment.
