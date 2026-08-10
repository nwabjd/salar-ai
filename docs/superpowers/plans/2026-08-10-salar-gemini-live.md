# SALAR Gemini Live Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace OpenAI Realtime with native Gemini Live, preserve SALAR's current Live interface, and automatically retain voice functionality through the existing Gemini STT/chat/TTS fallback.

**Architecture:** The browser keeps one stable SALAR Live event contract and sends authenticated 16kHz PCM to `/ws/live`. The backend owns the Gemini key, connects to Gemini's server-to-server Live WebSocket, translates Gemini messages into SALAR events, and retains resumption handles across bounded reconnects. A browser-side hybrid controller activates the extracted legacy Gemini pipeline only when the native session reports a retryable provider failure.

**Tech Stack:** React 19, TypeScript, AudioWorklet, Vitest, FastAPI, Python 3.9, `websockets` 12, pytest, Gemini Live raw WebSocket API, existing Gemini REST/STT/TTS services.

---

## File Structure

- Create `backend/app/services/gemini_live.py`: Gemini WebSocket URL, setup/input builders, server-event translation, and retry classification. This file contains no FastAPI or database logic.
- Modify `backend/app/config.py`: add the dedicated Gemini Live model setting and remove Live's dependency on the OpenAI settings.
- Modify `backend/app/api/live.py`: retain SALAR authentication, replace the OpenAI proxy with a reconnectable Gemini proxy, and keep provider errors sanitized.
- Create `backend/tests/test_gemini_live.py`: focused protocol and classification tests.
- Modify `backend/tests/test_live.py`: authenticated endpoint and provider-boundary regression tests.
- Modify `frontend/public/audio-processor.js`: capture 16kHz frames, play 24kHz output, and expose deterministic constants for source-level tests.
- Rename `frontend/src/live/realtime-client.ts` to `frontend/src/live/gemini-live-client.ts`: preserve the browser WebSocket boundary while adopting Gemini-compatible audio semantics.
- Rename `frontend/src/live/realtime-client.test.ts` to `frontend/src/live/gemini-live-client.test.ts`: focused native-client helper tests.
- Create `frontend/src/live/fallback-voice-client.ts`: move the non-visual STT/chat/TTS behavior out of `LegacyLive` behind the stable event interface.
- Create `frontend/src/live/fallback-voice-client.test.ts`: fallback activation, response speech, and cleanup tests.
- Create `frontend/src/live/hybrid-voice-client.ts`: select native first and fallback after one bounded retryable failure.
- Create `frontend/src/live/hybrid-voice-client.test.ts`: provider transition and duplicate-error tests.
- Modify `frontend/src/live/realtime-state.ts`: add `reconnecting` without changing visible steady-state phases.
- Modify `frontend/src/live/realtime-state.test.ts`: state-transition regressions.
- Modify `frontend/src/main.tsx`: use the hybrid controller and delete the obsolete `LegacyLive` component while preserving the current `Live` JSX.
- Modify `frontend/src/live-mode-contract.test.ts`: lock the provider and visual contracts.

### Task 1: Gemini Live protocol unit

**Files:**
- Create: `backend/app/services/gemini_live.py`
- Create: `backend/tests/test_gemini_live.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Write failing protocol tests**

Create `backend/tests/test_gemini_live.py` with tests for the exact setup, audio/text inputs, multi-part server events, interruption, completion, resumption, GoAway, and retry classification:

```python
from app.services.gemini_live import (
    build_audio_input,
    build_setup,
    build_text_input,
    classify_gemini_error,
    translate_server_message,
)


def test_setup_requests_native_audio_transcripts_and_session_management():
    message = build_setup("gemini-3.1-flash-live-preview", "Kore")
    setup = message["setup"]
    assert setup["model"] == "models/gemini-3.1-flash-live-preview"
    assert setup["responseModalities"] == ["AUDIO"]
    assert setup["inputAudioTranscription"] == {}
    assert setup["outputAudioTranscription"] == {}
    assert setup["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Kore"
    assert setup["thinkingConfig"] == {"thinkingLevel": "low"}
    assert setup["contextWindowCompression"] == {"slidingWindow": {}}
    assert setup["sessionResumption"] == {}


def test_input_messages_use_realtime_pcm_and_text_shapes():
    assert build_audio_input("AAA=") == {
        "realtimeInput": {
            "audio": {"data": "AAA=", "mimeType": "audio/pcm;rate=16000"}
        }
    }
    assert build_text_input(" hello ") == {"realtimeInput": {"text": "hello"}}


def test_translator_processes_every_part_and_server_signal():
    message = {
        "serverContent": {
            "modelTurn": {"parts": [
                {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": "AAA="}},
                {"text": "ignored native text"},
            ]},
            "inputTranscription": {"text": "Hello"},
            "outputTranscription": {"text": "Hi there"},
            "generationComplete": True,
        },
        "sessionResumptionUpdate": {"resumable": True, "newHandle": "resume-1"},
    }
    assert translate_server_message(message) == [
        {"type": "audio", "data": "AAA="},
        {"type": "input_transcript_delta", "text": "Hello"},
        {"type": "output_transcript_delta", "text": "Hi there"},
        {"type": "response_done"},
        {"type": "resumption", "handle": "resume-1"},
    ]


def test_translator_reports_interruption_and_goaway_without_generic_error():
    assert translate_server_message({"serverContent": {"interrupted": True}}) == [
        {"type": "interrupted"}
    ]
    assert translate_server_message({"goAway": {"timeLeft": "5s"}}) == [
        {"type": "go_away", "time_left": "5s"}
    ]


def test_error_classification_only_falls_back_for_retryable_provider_failures():
    assert classify_gemini_error(503, "UNAVAILABLE") == "retryable"
    assert classify_gemini_error(429, "RESOURCE_EXHAUSTED") == "retryable"
    assert classify_gemini_error(401, "UNAUTHENTICATED") == "configuration"
    assert classify_gemini_error(400, "INVALID_ARGUMENT") == "configuration"
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
cd backend
python -m pytest tests/test_gemini_live.py -q
```

Expected: collection fails because `app.services.gemini_live` does not exist.

- [ ] **Step 3: Add the dedicated configuration setting**

Modify `backend/app/config.py`:

```python
gemini_api_key: Optional[str] = None
gemini_model: str = "gemini-3.1-flash-lite"
gemini_live_model: str = "gemini-3.1-flash-live-preview"
```

Leave the OpenAI settings temporarily for backward-compatible environment loading; Task 2 removes their use from Live.

- [ ] **Step 4: Implement the minimal pure protocol module**

Create `backend/app/services/gemini_live.py`:

```python
from typing import Dict, List
from urllib.parse import quote_plus

GEMINI_LIVE_ENDPOINT = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)

SYSTEM_PROMPT = (
    "You are SALAR, a warm, concise personal AI companion in a live voice conversation. "
    "Speak naturally. Usually answer in one to three sentences unless the user asks for detail. "
    "Never claim an action completed unless it actually completed. Never talk over the user."
)


def gemini_live_url(api_key: str) -> str:
    return f"{GEMINI_LIVE_ENDPOINT}?key={quote_plus(api_key)}"


def build_setup(model: str, voice: str = "Kore", handle: str = "") -> Dict:
    setup = {
        "model": f"models/{model}",
        "responseModalities": ["AUDIO"],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        "thinkingConfig": {"thinkingLevel": "low"},
        "contextWindowCompression": {"slidingWindow": {}},
        "sessionResumption": {**({"handle": handle} if handle else {})},
    }
    return {"setup": setup}


def build_audio_input(data: str) -> Dict:
    return {"realtimeInput": {"audio": {"data": data, "mimeType": "audio/pcm;rate=16000"}}}


def build_text_input(text: str) -> Dict:
    return {"realtimeInput": {"text": text.strip()}}


def translate_server_message(message: Dict) -> List[Dict]:
    events: List[Dict] = []
    content = message.get("serverContent") or {}
    for part in (content.get("modelTurn") or {}).get("parts") or []:
        inline = part.get("inlineData") or {}
        if inline.get("data"):
            events.append({"type": "audio", "data": inline["data"]})
    if (content.get("inputTranscription") or {}).get("text"):
        events.append({"type": "input_transcript_delta", "text": content["inputTranscription"]["text"]})
    if (content.get("outputTranscription") or {}).get("text"):
        events.append({"type": "output_transcript_delta", "text": content["outputTranscription"]["text"]})
    if content.get("interrupted"):
        events.append({"type": "interrupted"})
    if content.get("generationComplete") or content.get("turnComplete"):
        events.append({"type": "response_done"})
    resume = message.get("sessionResumptionUpdate") or {}
    if resume.get("resumable") and resume.get("newHandle"):
        events.append({"type": "resumption", "handle": resume["newHandle"]})
    if message.get("goAway") is not None:
        events.append({"type": "go_away", "time_left": (message["goAway"] or {}).get("timeLeft", "")})
    return events


def classify_gemini_error(status: int, code: str) -> str:
    if status in {429, 500, 502, 503, 504} or code in {"RESOURCE_EXHAUSTED", "UNAVAILABLE", "ABORTED"}:
        return "retryable"
    return "configuration"
```

- [ ] **Step 5: Run the protocol tests and verify GREEN**

Run `python -m pytest tests/test_gemini_live.py -q` from `backend`.

Expected: `5 passed`.

- [ ] **Step 6: Commit the protocol unit**

```powershell
git add backend/app/config.py backend/app/services/gemini_live.py backend/tests/test_gemini_live.py
git commit -m "feat(live): add Gemini Live protocol adapter"
```

### Task 2: Authenticated Gemini Live proxy and bounded reconnect

**Files:**
- Modify: `backend/app/api/live.py`
- Modify: `backend/tests/test_live.py`

- [ ] **Step 1: Replace OpenAI expectations with failing Gemini boundary tests**

Extend `backend/tests/test_live.py` and import `_translate_provider_event` from `app.api.live`:

```python
from app.services.gemini_live import build_setup


def test_live_setup_uses_configured_gemini_model():
    message = build_setup("gemini-3.1-flash-live-preview", "Kore")
    assert message["setup"]["model"] == "models/gemini-3.1-flash-live-preview"
    assert "OpenAI-Beta" not in str(message)


def test_gemini_error_is_sanitized_for_browser():
    assert _translate_provider_event({
        "error": {"code": 503, "status": "UNAVAILABLE", "message": "private upstream detail"}
    }) == [{"type": "provider_retry", "error": "Live voice is reconnecting"}]
```

Also change `test_realtime_settings_are_server_side` to assert `settings.gemini_live_model` and remove assertions that Live uses `openai_realtime_model`.

- [ ] **Step 2: Run the focused test and verify RED**

Run `python -m pytest tests/test_live.py -q` from `backend`.

Expected: FAIL because `_translate_provider_event` is absent and `live.py` still references OpenAI.

- [ ] **Step 3: Replace the upstream connection and translation path**

In `backend/app/api/live.py`:

- import the Task 1 helpers;
- change the missing-configuration check to `settings.gemini_api_key`;
- connect to `gemini_live_url(settings.gemini_api_key)` with no API key headers;
- send `build_setup(settings.gemini_live_model, "Kore", resume_handle)` first;
- wait for `setupComplete` before sending `{"type": "ready"}`;
- map browser audio with `build_audio_input` and text with `build_text_input`;
- forward all translated events, retaining `resumption` only on the server;
- on `interrupted`, send `{"type": "interrupted"}`;
- on `go_away`, reconnect once using the latest handle;
- on a retryable provider error, send one `provider_retry` event and reconnect once;
- after the retry fails, send one `fallback_required` event and close cleanly;
- on configuration/auth errors, send one specific sanitized error and do not fall back;
- cancel and await every sibling task with `asyncio.gather(..., return_exceptions=True)`.

Add the provider boundary as a small pure adapter inside `backend/app/api/live.py`:

```python
def _translate_provider_event(message: dict) -> list[dict]:
    error = message.get("error") or {}
    if error:
        status = int(error.get("code") or 0)
        code = str(error.get("status") or "UNKNOWN")
        if classify_gemini_error(status, code) == "retryable":
            return [{"type": "provider_retry", "error": "Live voice is reconnecting"}]
        return [{"type": "error", "error": "Live voice configuration failed", "code": "configuration"}]
    return translate_server_message(message)
```

Use these stable browser payloads:

```python
READY = {"type": "ready"}
RETRYING = {"type": "provider_retry", "error": "Live voice is reconnecting"}
FALLBACK = {"type": "fallback_required", "error": "Switching voice connection"}
NOT_CONFIGURED = {"type": "error", "error": "Live voice is not configured", "code": "not_configured"}
```

Do not log the Gemini URL because it contains the API key. Log only safe status/code pairs.

- [ ] **Step 4: Run backend Live tests and verify GREEN**

Run:

```powershell
cd backend
python -m pytest tests/test_gemini_live.py tests/test_live.py -q
```

Expected: all focused tests pass with no unhandled-task warnings.

- [ ] **Step 5: Commit the backend provider replacement**

```powershell
git add backend/app/api/live.py backend/tests/test_live.py
git commit -m "feat(live): proxy native Gemini audio sessions"
```

### Task 3: Correct browser audio rates and interruption behavior

**Files:**
- Modify: `frontend/public/audio-processor.js`
- Create: `frontend/src/live/audio-processor-contract.test.ts`

- [ ] **Step 1: Write a failing source contract test**

Create `frontend/src/live/audio-processor-contract.test.ts`:

```typescript
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

describe('SALAR Live audio worklet contract', () => {
  const source = readFileSync('public/audio-processor.js', 'utf8')

  it('captures 16kHz PCM in short chunks and plays 24kHz PCM', () => {
    expect(source).toContain('this.captureRate = 16000')
    expect(source).toContain('this.playbackRate = 24000')
    expect(source).toContain('this.captureFrameSize = 640')
    expect(source).toContain('this.resample(input, sampleRate, this.captureRate)')
    expect(source).toContain('this.resample(data.samples, this.playbackRate, sampleRate)')
  })

  it('clears queued playback on interruption', () => {
    expect(source).toContain("if (data.type === 'stop')")
    expect(source).toContain('this.playback = []')
  })
})
```

- [ ] **Step 2: Run the test and verify RED**

Run `npm test -- --run src/live/audio-processor-contract.test.ts` from `frontend`.

Expected: FAIL because the worklet still uses one 24kHz target rate and 2,400-sample capture frames.

- [ ] **Step 3: Implement separate capture and playback rates**

In `frontend/public/audio-processor.js`, replace `targetRate` with:

```javascript
this.captureRate = 16000
this.playbackRate = 24000
this.captureFrameSize = 640 // 40ms at 16kHz
```

Capture with `this.resample(input, sampleRate, this.captureRate)`, emit while the buffer has at least `captureFrameSize`, and resample playback with `this.resample(data.samples, this.playbackRate, sampleRate)`.

- [ ] **Step 4: Run the worklet test and verify GREEN**

Run `npm test -- --run src/live/audio-processor-contract.test.ts`.

Expected: `2 passed`.

- [ ] **Step 5: Commit the audio contract**

```powershell
git add frontend/public/audio-processor.js frontend/src/live/audio-processor-contract.test.ts
git commit -m "fix(live): stream Gemini-compatible PCM rates"
```

### Task 4: Native Gemini browser client

**Files:**
- Rename: `frontend/src/live/realtime-client.ts` → `frontend/src/live/gemini-live-client.ts`
- Rename: `frontend/src/live/realtime-client.test.ts` → `frontend/src/live/gemini-live-client.test.ts`

- [ ] **Step 1: Rename the files and add failing event-contract tests**

Rename the files with `Move-Item`. In the renamed test, import `GeminiLiveClient` and add assertions through a fake WebSocket that:

```typescript
it('stops playback immediately on interruption', () => {
  socket.message({ type: 'interrupted' })
  expect(workletMessages.at(-1)).toEqual({ type: 'stop' })
})

it('emits one fallback request without a later disconnect error', () => {
  socket.message({ type: 'fallback_required', error: 'Switching voice connection' })
  socket.close()
  expect(events).toEqual([{ type: 'fallback_required' }])
})

it('keeps a retry state non-terminal', () => {
  socket.message({ type: 'provider_retry', error: 'Live voice is reconnecting' })
  expect(events).toEqual([{ type: 'reconnecting' }])
})
```

The test helper must restore global `WebSocket`, `AudioContext`, and `navigator.mediaDevices` after each test.

- [ ] **Step 2: Run the renamed client test and verify RED**

Run `npm test -- --run src/live/gemini-live-client.test.ts`.

Expected: FAIL because `GeminiLiveClient` and the three events are not implemented.

- [ ] **Step 3: Implement the renamed native client**

Rename `RealtimeVoiceClient` to `GeminiLiveClient`. Preserve `realtimeWebSocketUrl`, PCM base64 helpers, setup token exchange, worklet playback, and cleanup. Add:

```typescript
if (message.type === 'interrupted') {
  this.worklet?.port.postMessage({ type: 'stop' })
  this.options.onEvent({ type: 'speech_started' })
  return
}
if (message.type === 'provider_retry') {
  this.receivedServerError = true
  this.options.onEvent({ type: 'reconnecting' })
  return
}
if (message.type === 'fallback_required') {
  this.receivedServerError = true
  this.options.onFallback()
  return
}
```

Extend `ClientOptions` with `onFallback: () => void`. A normal user close remains silent.

- [ ] **Step 4: Run the native-client test and verify GREEN**

Run `npm test -- --run src/live/gemini-live-client.test.ts`.

Expected: all helper and event tests pass.

- [ ] **Step 5: Commit the native client**

```powershell
git add frontend/src/live/realtime-client.ts frontend/src/live/realtime-client.test.ts frontend/src/live/gemini-live-client.ts frontend/src/live/gemini-live-client.test.ts
git commit -m "refactor(live): adapt browser client for Gemini"
```

### Task 5: Extract the existing Gemini fallback behind the Live event contract

**Files:**
- Create: `frontend/src/live/fallback-voice-client.ts`
- Create: `frontend/src/live/fallback-voice-client.test.ts`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Write failing fallback lifecycle tests**

Create `frontend/src/live/fallback-voice-client.test.ts` using injected `api`, recorder, and audio dependencies. Cover:

```typescript
it('transcribes a completed turn, streams chat, and speaks the complete answer', async () => {
  await client.acceptRecordedTurn(audioBlob)
  expect(api.stt).toHaveBeenCalledWith(audioBlob)
  expect(events).toContainEqual({ type: 'input_transcript_completed', text: 'Hello SALAR' })
  expect(api.chatStream).toHaveBeenCalled()
  expect(api.tts).toHaveBeenCalledWith('Hello. How can I help?', false)
  expect(events).toContainEqual({ type: 'output_transcript_completed', text: 'Hello. How can I help?' })
  expect(events).toContainEqual({ type: 'response_done' })
})

it('does not restart listening until generated speech playback drains', async () => {
  await client.acceptRecordedTurn(audioBlob)
  const doneIndex = events.findIndex((event) => event.type === 'response_done')
  const drainedIndex = events.findIndex((event) => event.type === 'playback_drained')
  expect(drainedIndex).toBeGreaterThan(doneIndex)
})

it('stops tracks, timers, recorder, requests, and audio on close', () => {
  client.stop()
  expect(track.stop).toHaveBeenCalled()
  expect(abort).toHaveBeenCalled()
  expect(audioSource.stop).toHaveBeenCalled()
})
```

- [ ] **Step 2: Run the fallback test and verify RED**

Run `npm test -- --run src/live/fallback-voice-client.test.ts`.

Expected: collection fails because the fallback client does not exist.

- [ ] **Step 3: Extract, do not redesign, the legacy pipeline**

Move microphone acquisition, MediaRecorder turn collection, conservative silence detection, `api.stt`, `api.chatStream`, complete-response `api.tts(text, false)`, audio playback, and teardown from `LegacyLive` into `FallbackVoiceClient`.

Expose this interface:

```typescript
export type VoiceClientOptions = {
  token: string
  conversationId: string
  onEvent: (event: LiveEvent) => void
  onVolume?: (volume: number) => void
}

export class FallbackVoiceClient {
  constructor(options: VoiceClientOptions, dependencies = browserVoiceDependencies) {}
  start(): Promise<void>
  sendText(text: string): void
  stop(): void
}
```

Dispatch only the stable Live events. Use a minimum speech duration and require sustained silence before ending a turn; ignore sub-threshold noise rather than sending it for transcription. Generate one TTS request for the complete response initially to prevent overlapping queue races.

- [ ] **Step 4: Delete the obsolete `LegacyLive` component**

After extraction, remove the entire `LegacyLive` function from `frontend/src/main.tsx`. Do not change the current `Live` JSX or styles.

- [ ] **Step 5: Run fallback and existing Live tests**

Run:

```powershell
cd frontend
npm test -- --run src/live/fallback-voice-client.test.ts src/live-mode-contract.test.ts
```

Expected: all tests pass after the contract test is updated in Task 6; if the old contract temporarily expects `LegacyLive`, keep this task uncommitted until Task 6.

- [ ] **Step 6: Commit the extracted fallback together with Task 6**

Do not create a broken intermediate commit. Stage these files only after Task 6 is green.

### Task 6: Hybrid controller and unchanged Live UI

**Files:**
- Create: `frontend/src/live/hybrid-voice-client.ts`
- Create: `frontend/src/live/hybrid-voice-client.test.ts`
- Modify: `frontend/src/live/realtime-state.ts`
- Modify: `frontend/src/live/realtime-state.test.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/live-mode-contract.test.ts`

- [ ] **Step 1: Write failing reducer and hybrid tests**

Add to `frontend/src/live/realtime-state.test.ts`:

```typescript
it('shows reconnecting without discarding transcripts or history', () => {
  const speaking = { ...initialLiveState, phase: 'speaking' as const, outputTranscript: 'Working', history: [{ role: 'user' as const, text: 'Hi' }] }
  expect(liveReducer(speaking, { type: 'reconnecting' })).toMatchObject({
    phase: 'reconnecting', outputTranscript: 'Working', history: speaking.history, error: ''
  })
})
```

Create `frontend/src/live/hybrid-voice-client.test.ts`:

```typescript
it('starts native first and activates fallback only once', async () => {
  await client.start()
  expect(native.start).toHaveBeenCalledTimes(1)
  native.triggerFallback()
  native.triggerFallback()
  expect(native.stop).toHaveBeenCalledTimes(1)
  expect(fallback.start).toHaveBeenCalledTimes(1)
})

it('routes text and stop to the active provider', async () => {
  await client.start()
  client.sendText('hello')
  expect(native.sendText).toHaveBeenCalledWith('hello')
  native.triggerFallback()
  client.sendText('again')
  expect(fallback.sendText).toHaveBeenCalledWith('again')
  client.stop()
  expect(fallback.stop).toHaveBeenCalled()
})
```

- [ ] **Step 2: Run the tests and verify RED**

Run `npm test -- --run src/live/realtime-state.test.ts src/live/hybrid-voice-client.test.ts`.

Expected: FAIL because `reconnecting` and `HybridVoiceClient` are absent.

- [ ] **Step 3: Add the reconnecting state**

In `frontend/src/live/realtime-state.ts`:

```typescript
export type LivePhase = 'connecting' | 'reconnecting' | 'listening' | 'thinking' | 'speaking' | 'error'

// In LiveEvent:
| { type: 'reconnecting' }

// In the reducer:
case 'reconnecting':
  return { ...state, phase: 'reconnecting', error: '' }
```

- [ ] **Step 4: Implement the hybrid controller**

Create `frontend/src/live/hybrid-voice-client.ts`:

```typescript
export class HybridVoiceClient {
  private active: VoiceClient
  private fallbackStarted = false

  constructor(
    private readonly native: VoiceClient,
    private readonly fallback: VoiceClient,
    private readonly onEvent: (event: LiveEvent) => void,
  ) {
    this.active = native
  }

  async start(): Promise<void> {
    await this.native.start()
  }

  async activateFallback(): Promise<void> {
    if (this.fallbackStarted) return
    this.fallbackStarted = true
    this.onEvent({ type: 'reconnecting' })
    this.native.stop()
    this.active = this.fallback
    await this.fallback.start()
  }

  sendText(text: string): void {
    this.active.sendText(text)
  }

  stop(): void {
    this.native.stop()
    this.fallback.stop()
  }
}
```

Define the small `VoiceClient` interface in `frontend/src/live/hybrid-voice-client.ts`; do not use class inheritance:

```typescript
export interface VoiceClient {
  start(): Promise<void>
  sendText(text: string): void
  stop(): void
}
```

- [ ] **Step 5: Wire the current Live component without changing its markup**

In `frontend/src/main.tsx`:

- replace `RealtimeVoiceClient` with `HybridVoiceClient`, `GeminiLiveClient`, and `FallbackVoiceClient`;
- obtain or create one conversation ID for the fallback before starting it;
- pass `dispatch` and `setVolume` to both providers;
- pass `activateFallback` as the native client's `onFallback` callback;
- keep `handleClose`, text submission, MagicRings props, history markup, and controls intact;
- label both `connecting` and `reconnecting` as `Reconnecting…` only after the first connection attempt.

- [ ] **Step 6: Lock the visible and provider contracts**

Update `frontend/src/live-mode-contract.test.ts` to assert:

```typescript
expect(live).toContain('<MagicRings')
expect(live).toContain('new HybridVoiceClient')
expect(live).toContain('new GeminiLiveClient')
expect(live).toContain('new FallbackVoiceClient')
expect(live).not.toContain('new RealtimeVoiceClient')
expect(main).not.toContain('function LegacyLive(')
for (const label of ['Listening', 'Thinking', 'Speaking', 'Reconnecting']) {
  expect(live).toContain(label)
}
```

- [ ] **Step 7: Run all focused frontend tests and verify GREEN**

Run:

```powershell
cd frontend
npm test -- --run src/live/audio-processor-contract.test.ts src/live/gemini-live-client.test.ts src/live/fallback-voice-client.test.ts src/live/hybrid-voice-client.test.ts src/live/realtime-state.test.ts src/live-mode-contract.test.ts
```

Expected: all focused tests pass with no unhandled promise rejections.

- [ ] **Step 8: Commit the fallback and hybrid integration**

```powershell
git add frontend/src/main.tsx frontend/src/live frontend/src/live-mode-contract.test.ts
git commit -m "feat(live): add resilient Gemini voice fallback"
```

### Task 7: Full verification and production deployment

**Files:**
- Modify only if a verification failure proves a defect in a file from Tasks 1–6.

- [ ] **Step 1: Run the complete backend suite**

Run `python -m pytest -q` from `backend`.

Expected: all tests pass; warnings may include the existing JWT test-key warnings, but there must be no task-exception or Live protocol warnings.

- [ ] **Step 2: Run the complete frontend suite**

Run `npm test` from `frontend`.

Expected: all tests pass.

- [ ] **Step 3: Build the production frontend**

Run `npm run build` from `frontend`.

Expected: TypeScript and Vite complete successfully. Record the generated JavaScript and CSS asset hashes.

- [ ] **Step 4: Inspect the final diff and commit any test-proven correction**

Run:

```powershell
git diff --check
git status --short
```

Only the intended Live files may be staged. Preserve all unrelated untracked workspace files.

- [ ] **Step 5: Push the tested branch and monitor Render**

Push `main` only after all checks pass. Confirm Render deploys the exact commit and reaches `live`. Verify `https://salar-backend.onrender.com/docs` returns `200`.

- [ ] **Step 6: Test the authenticated production WebSocket before frontend upload**

Using a valid SALAR session in the browser, enter Live once and confirm Render logs show Gemini setup completion rather than OpenAI access or quota errors. Verify the browser receives `ready`, input transcription, audio, output transcription, and response completion.

- [ ] **Step 7: Request the required Hostinger write confirmation**

Immediately before upload, ask exactly:

> Upload the verified Gemini Live frontend build to `salaar.cloud` on Hostinger account `u247630134` now?

Do not reuse an earlier deployment confirmation.

- [ ] **Step 8: Deploy and verify Hostinger**

After confirmation, archive only `frontend/dist/*` with `index.html` at the archive root and deploy it with `removeArchive: true`. Verify:

```powershell
curl.exe -sS -o NUL -w "%{http_code}" https://salaar.cloud/
curl.exe -sS https://salaar.cloud/
```

Expected: HTTP `200`, the SALAR title/headline, and the exact new JS/CSS asset hashes from Step 3.

- [ ] **Step 9: Perform the production voice acceptance test**

Confirm in Live mode:

1. the current interface is visually unchanged;
2. the label reaches Listening;
3. spoken input appears accurately;
4. SALAR begins audible output without waiting for the whole answer;
5. speaking over SALAR stops queued audio;
6. Listening resumes only after playback drains;
7. typed Live input receives spoken output;
8. a controlled retryable Gemini failure shows Reconnecting once and activates fallback without stacked errors.

- [ ] **Step 10: Review production logs**

Check Render logs for the test window. The acceptance result is valid only when there are no exposed keys, unhandled asyncio task errors, repeated disconnect loops, OpenAI Realtime requests, or Gemini protocol errors.
