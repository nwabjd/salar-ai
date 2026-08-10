# SALAR Chat, Landing, and Realtime Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore SALAR's original authenticated chat, replace the public particle renderer with a tuned full-page LiquidEther background, and deliver authenticated OpenAI Realtime speech-to-speech Live mode.

**Architecture:** Keep the existing guarded Supabase-to-backend session handoff unchanged. Restore the pre-Ambient chat JSX/CSS while preserving later auth and Live work. Put Realtime protocol translation in the FastAPI backend, keep the OpenAI secret in Render, and isolate browser audio/WebSocket behavior in a focused frontend client plus a pure state reducer.

**Tech Stack:** React 19, TypeScript, Vitest, Three.js ReactBits LiquidEther, Web Audio AudioWorklet, FastAPI, PyJWT, websockets, pytest, OpenAI Realtime WebSocket API, Hostinger, Render.

---

## File map

- `frontend/src/main.tsx`: restored App/Chat UI and the Live component shell.
- `frontend/src/styles.css`: restored pre-Ambient chat rules and final Live layout.
- `frontend/src/components/SalaarLanding.tsx`: full-page tuned LiquidEther mount.
- `frontend/src/cosmic-landing.css`: landing LiquidEther positioning and removal of particle overlays.
- `frontend/src/workspace-contract.test.ts`: regression contract for the original authenticated chat.
- `frontend/src/landing-performance.test.ts`: contract proving particles/core are unmounted and the tuned preset is used.
- `frontend/src/live/realtime-state.ts`: pure Live phase/transcript/playback state reducer.
- `frontend/src/live/realtime-state.test.ts`: reducer behavior tests.
- `frontend/src/live/realtime-client.ts`: authenticated WebSocket and AudioWorklet controller.
- `frontend/src/live/realtime-client.test.ts`: protocol mapping and cleanup tests with local fakes.
- `frontend/public/audio-processor.js`: 24 kHz PCM capture/playback and playback-drained reporting.
- `frontend/src/live-mode-contract.test.ts`: integration contract for the realtime Live component.
- `backend/app/config.py`: server-only OpenAI settings.
- `backend/app/security.py`: reusable backend-token decoder for WebSockets.
- `backend/app/api/live.py`: authenticated OpenAI Realtime proxy.
- `backend/tests/test_live.py`: authentication, session config, protocol translation, and sanitized error tests.

### Task 1: Restore the authenticated chat contract

**Files:**
- Modify: `frontend/src/workspace-contract.test.ts`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write the failing restoration test**

Assert the original structure and reject Ambient-only elements:

```ts
expect(main).toContain('<StatusRail/>')
expect(main).toContain("What shall we accomplish?")
expect(main).toContain('className="usage-chip"')
expect(main).not.toContain('conversation-rail')
expect(main).not.toContain('tools-drawer')
expect(styles).not.toContain('.app-shell .liquid-stage{opacity:.2')
```

- [ ] **Step 2: Run the test to verify RED**

Run: `npm test -- --run src/workspace-contract.test.ts`

Expected: FAIL because the Ambient rail/drawer/profile layout is still present.

- [ ] **Step 3: Restore the pre-Ambient App and Chat JSX**

Use `git show c5239b3^:frontend/src/main.tsx` as the reference for only `App`, `Chat`, and `StatusRail`. Preserve `sessionCoordinator`, guarded `enterApp`, later Live code, and the sole-admin backend work.

- [ ] **Step 4: Remove only the Ambient override block**

Delete the CSS beginning at `/* Ambient Companion workspace */` through its mobile rules. Preserve later `/* Live voice presence */` rules. This restores the original LiquidEther saturation, original top bar, composer, and permanent status rail.

- [ ] **Step 5: Verify GREEN and commit**

Run: `npm test -- --run src/workspace-contract.test.ts && npm run build`

Commit:

```bash
git add frontend/src/main.tsx frontend/src/styles.css frontend/src/workspace-contract.test.ts
git commit -m "fix(chat): restore original SALAR workspace"
```

### Task 2: Replace landing particles with tuned LiquidEther

**Files:**
- Create: `frontend/src/landing-performance.test.ts`
- Modify: `frontend/src/components/SalaarLanding.tsx`
- Modify: `frontend/src/cosmic-landing.css`
- Add to version control: `frontend/src/cosmic-landing.css`

- [ ] **Step 1: Write the failing landing performance contract**

```ts
expect(landing).toContain('import LiquidEther')
expect(landing).toContain('className="landing-liquid-stage"')
expect(landing).not.toContain('CosmicIntelligence')
expect(landing).not.toContain('cosmic-grain')
expect(landing).toContain('resolution={0.28}')
expect(landing).toContain('iterationsPoisson={12}')
expect(landing).toContain('BFECC={false}')
```

- [ ] **Step 2: Run the test to verify RED**

Run: `npm test -- --run src/landing-performance.test.ts`

Expected: FAIL because the particle renderer is still mounted.

- [ ] **Step 3: Mount one fixed tuned LiquidEther**

Replace the particle component with:

```tsx
<div className="landing-liquid-stage" aria-hidden="true">
  <LiquidEther
    colors={['#5227FF', '#FF9FFC', '#B497CF']}
    mouseForce={8}
    cursorSize={72}
    isViscous={false}
    iterationsViscous={8}
    iterationsPoisson={12}
    resolution={0.28}
    BFECC={false}
    autoDemo
    autoSpeed={0.22}
    autoIntensity={1.15}
    autoResumeDelay={4000}
  />
</div>
```

Keep the vignette. Remove the grain node. Position the stage fixed at `inset: 0`, keep it behind content, disable pointer events, and add a dark translucent color wash for text contrast.

- [ ] **Step 4: Verify GREEN and commit**

Run: `npm test -- --run src/landing-performance.test.ts && npm run build`

Commit:

```bash
git add frontend/src/components/SalaarLanding.tsx frontend/src/cosmic-landing.css frontend/src/landing-performance.test.ts
git commit -m "fix(landing): replace particles with tuned LiquidEther"
```

### Task 3: Build authenticated OpenAI Realtime backend configuration

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/security.py`
- Modify: `backend/app/api/live.py`
- Create: `backend/tests/test_live.py`

- [ ] **Step 1: Write failing auth and session-config tests**

Test pure helpers with a real signed SALAR token:

```py
def test_realtime_setup_uses_audio_transcription_and_semantic_vad():
    setup = build_openai_session("marin")
    assert setup["session"]["model"] == "gpt-realtime"
    assert setup["session"]["audio"]["input"]["transcription"]["model"] == "gpt-4o-mini-transcribe"
    assert setup["session"]["audio"]["input"]["turn_detection"]["type"] == "semantic_vad"
    assert setup["session"]["audio"]["input"]["turn_detection"]["eagerness"] == "low"

def test_decode_backend_token_rejects_expired_token(app):
    with pytest.raises(HTTPException):
        decode_backend_token("expired", app.state.settings.jwt_secret)
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_live.py -q`

Expected: FAIL because the OpenAI helpers do not exist.

- [ ] **Step 3: Add server-only settings and token decoder**

Add:

```py
openai_api_key: Optional[str] = None
openai_realtime_model: str = "gpt-realtime"
```

Extract `decode_backend_token(token, secret)` in `security.py`; use the same HS256 validation as HTTP authentication without requiring a `Request` dependency.

- [ ] **Step 4: Implement the OpenAI session message**

Build a `session.update` event with 24 kHz PCM input/output, `far_field` noise reduction, `gpt-4o-mini-transcribe`, semantic VAD at low eagerness, interruption enabled, output modality `audio`, and the SALAR system instructions. Do not include the API key in this structure.

- [ ] **Step 5: Verify focused tests and commit**

Run: `python -m pytest tests/test_live.py tests/test_auth.py -q`

Commit:

```bash
git add backend/app/config.py backend/app/security.py backend/app/api/live.py backend/tests/test_live.py
git commit -m "feat(live): authenticate OpenAI realtime sessions"
```

### Task 4: Implement and test the backend protocol proxy

**Files:**
- Modify: `backend/app/api/live.py`
- Modify: `backend/tests/test_live.py`

- [ ] **Step 1: Add failing event-translation tests**

Cover these translations:

```py
assert client_audio_to_openai("abc")["type"] == "input_audio_buffer.append"
assert openai_event_to_client({"type": "input_audio_buffer.speech_started"}) == {"type": "speech_started"}
assert openai_event_to_client({"type": "response.audio.delta", "delta": "abc"}) == {"type": "audio", "data": "abc"}
assert openai_event_to_client({"type": "response.audio_transcript.delta", "delta": "Hi"}) == {"type": "output_transcript_delta", "text": "Hi"}
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_live.py -q`

- [ ] **Step 3: Implement bidirectional forwarding**

Connect to `wss://api.openai.com/v1/realtime?model=<configured model>` with `Authorization: Bearer <server key>` and `OpenAI-Beta: realtime=v1`. Require the first browser message to be `{type:"setup", token, voice}` and validate before connecting. Forward browser audio as `input_audio_buffer.append`; translate ready, speech, transcription, audio, response completion, interruption, and sanitized error events back to the browser.

- [ ] **Step 4: Verify proxy tests and commit**

Run: `python -m pytest tests/test_live.py -q`

Commit:

```bash
git add backend/app/api/live.py backend/tests/test_live.py
git commit -m "feat(live): proxy OpenAI realtime audio"
```

### Task 5: Create the frontend Live reducer and realtime client

**Files:**
- Create: `frontend/src/live/realtime-state.ts`
- Create: `frontend/src/live/realtime-state.test.ts`
- Create: `frontend/src/live/realtime-client.ts`
- Create: `frontend/src/live/realtime-client.test.ts`

- [ ] **Step 1: Write failing reducer tests**

```ts
expect(reduce(initial, {type:'ready'}).phase).toBe('listening')
expect(reduce(listening, {type:'speech_stopped'}).phase).toBe('thinking')
expect(reduce(thinking, {type:'audio_delta'}).phase).toBe('speaking')
expect(reduce(speaking, {type:'response_done'}).phase).toBe('speaking')
expect(reduce(speakingNetworkDone, {type:'playback_drained'}).phase).toBe('listening')
expect(reduce(speaking, {type:'speech_started'}).clearPlayback).toBe(true)
```

- [ ] **Step 2: Run tests to verify RED**

Run: `npm test -- --run src/live/realtime-state.test.ts`

- [ ] **Step 3: Implement the reducer**

Export `LivePhase`, `LiveState`, `LiveEvent`, `initialLiveState`, and `reduceLiveState`. Keep network completion and playback completion as separate booleans so Listening cannot resume early.

- [ ] **Step 4: Write failing client protocol tests**

Use fake WebSocket, AudioContext, worklet node, and MediaStream objects. Assert setup sends the backend token, capture posts `audio`, audio deltas post playback to the worklet, interruption posts `stop`, and `close()` stops tracks and closes the socket/context.

- [ ] **Step 5: Implement `RealtimeVoiceClient` and verify**

Expose:

```ts
new RealtimeVoiceClient({ apiBase, token, voice, onEvent })
await client.connect()
client.sendText(text)
client.close()
```

Run: `npm test -- --run src/live/realtime-state.test.ts src/live/realtime-client.test.ts`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/live
git commit -m "feat(live): add realtime browser client"
```

### Task 6: Upgrade the AudioWorklet to 24 kHz duplex playback

**Files:**
- Modify and add to version control: `frontend/public/audio-processor.js`
- Modify: `frontend/src/live/realtime-client.test.ts`

- [ ] **Step 1: Add a failing source contract**

Assert the worklet target rate is 24,000 Hz, capture chunks represent about 100 ms, playback emits `playback-started`, and an empty queue emits `playback-drained` exactly once.

- [ ] **Step 2: Run to verify RED**

Run: `npm test -- --run src/live/realtime-client.test.ts`

- [ ] **Step 3: Implement worklet playback state events**

Change target rate and capture size to 24 kHz / 2,400 samples. Keep PCM16 little-endian conversion. Emit playback-started when the first chunk begins and playback-drained when the final resampled sample leaves the queue. Reset state on `stop`.

- [ ] **Step 4: Verify and commit**

Run: `npm test -- --run src/live/realtime-client.test.ts`

```bash
git add frontend/public/audio-processor.js frontend/src/live/realtime-client.test.ts
git commit -m "feat(live): stream duplex 24khz audio"
```

### Task 7: Replace the old Live component pipeline

**Files:**
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/live-mode-contract.test.ts`

- [ ] **Step 1: Rewrite the failing Live contract**

Assert `RealtimeVoiceClient` is used and the old `MediaRecorder`, `api.stt`, `api.tts`, fixed-record timer, and 600 ms silence cutoff are absent from the Live component.

- [ ] **Step 2: Run to verify RED**

Run: `npm test -- --run src/live-mode-contract.test.ts`

- [ ] **Step 3: Integrate the reducer/client**

On mount, instantiate the client with `api.token`, subscribe to events, and connect. Render input transcript and output transcript separately. Feed the state phase and measured input/output energy to `MagicRings`. Text fallback sends a Realtime conversation item rather than the REST chat/TTS loop.

- [ ] **Step 4: Complete cleanup and visual behavior**

Close the client once on unmount/Close. Keep the central orb and approved Live layout. Display Connecting, Listening, Thinking, Speaking, and recoverable Error labels. Ensure speech-started during output clears playback and visible assistant partial output.

- [ ] **Step 5: Verify and commit**

Run: `npm test -- --run src/live-mode-contract.test.ts src/live/realtime-state.test.ts src/live/realtime-client.test.ts src/effects/magic-rings-motion.test.ts`

```bash
git add frontend/src/main.tsx frontend/src/styles.css frontend/src/live-mode-contract.test.ts
git commit -m "feat(live): deliver realtime speech conversation"
```

### Task 8: Full verification and production deployment

**Files:**
- No source changes unless verification finds a scoped defect.

- [ ] **Step 1: Run all local checks**

```bash
cd frontend && npm test -- --run && npm run build
cd ../backend && python -m pytest -q
cd .. && git diff --check
```

Expected: all frontend and backend tests pass; build exits 0; diff check is clean.

- [ ] **Step 2: Add the secret to Render without exposing it**

Use the connected Render environment manager to merge `SALAR_OPENAI_API_KEY` into service `srv-d9jhfn58nd3s73be73gg`. Do not echo, inspect, or persist the value locally.

- [ ] **Step 3: Push and wait for Render**

Push `main`, verify the deploy for the new commit reaches `live`, and confirm `/api/health` is 200. Inspect sanitized Live connection logs only; never print environment values or request headers.

- [ ] **Step 4: Deploy the static frontend**

Build an archive with `frontend/dist/index.html` at the archive root, deploy it to Hostinger website `salaar.cloud` on account `u247630134`, clear cache, and verify the served bundle contains restored chat, tuned landing, and Realtime Live markers.

- [ ] **Step 5: Browser verification**

In Chrome, verify desktop and mobile landing scroll performance, original chat layout/colors after authentication, Live microphone permission, visible input transcript, audible response, correct Speaking duration, return to Listening after playback drains, and barge-in behavior. Leave the final production tab open for the user.

- [ ] **Step 6: Rotate the exposed key**

Report that the shared key must be revoked in the OpenAI dashboard. After the user supplies a replacement through an approved secret path, update only the Render environment variable and redeploy; never request that it be committed.
