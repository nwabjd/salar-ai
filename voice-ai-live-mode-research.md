# Real-Time Voice AI Assistant "Live Mode" — Comprehensive Research (July 2026)

---

## 1. Real-Time STT (Speech-to-Text) APIs

### Deepgram — Nova-3 & Flux

**Best-in-class for real-time voice AI.** Purpose-built for streaming from the ground up.

| Metric | Nova-3 Streaming | Flux English | Flux Multilingual |
|---|---|---|---|
| Latency | < 300ms (often ~200ms) | Sub-300ms | Sub-300ms |
| WER (streaming) | 6.84% median | Optimized for conversational | Optimized for conversational |
| Pricing (PAYG) | $0.0048/min mono, $0.0058/min multi | $0.0065/min | $0.0078/min |
| Pricing (Growth) | $0.0042/min, $0.0050/min | $0.0057/min | $0.0068/min |
| Languages | 36+ | English | Multi |
| Billing | Per second, no rounding | Per second | Per second |

**Key differentiators:**
- Flux has **built-in turn detection** (EndOfTurn + EagerEndOfTurn events) — eliminates need for separate VAD
- Flux reduces agent response latency by **200–600ms** vs traditional STT+VAD approaches
- Sub-300ms transcription latency consistently
- **54% lower WER** vs competitors for streaming
- Self-hosted option available (rare)
- $200 free credits on signup

**Flux EOT latency:** 100–500ms from speech end to EndOfTurn event

**Voice Agent API:** $0.05–$0.163/min depending on tier (STT+LLM+TTS managed)

---

### AssemblyAI — Universal-3.5 Pro Realtime

| Metric | Universal-3.5 Pro RT | Universal-Streaming EN | Universal-Streaming Multi |
|---|---|---|---|
| Latency | Fastest (sub-300ms) | Fast | Fast |
| Pricing | $0.45/hr (~$0.0075/min) | $0.15/hr (~$0.0025/min) | $0.15/hr |
| Languages | 18 (code-switching) | EN only | EN/ES/DE/FR/PT/IT |
| Billing | **Session duration** (not audio!) | Session duration | Session duration |

**Key differentiators:**
- Voice Agent API: **$4.50/hr flat** (STT+LLM+TTS in one WebSocket, PCI-certified)
- ~1s end-to-end latency via Voice Agent API
- Real-time inline diarization (+$0.12/hr)
- Keyterms prompting (+$0.05/hr)
- **Warning:** Billed on WebSocket session time, not audio. Idle connections cost money.
- $50 free credits

---

### Google Cloud Speech-to-Text V2

| Metric | Standard Streaming | Medical |
|---|---|---|
| Latency | 350–600ms | 350–600ms |
| Pricing | $0.016/min (0–500K min) | $0.078/min |
| Languages | 125+ | Limited |
| Billing | Per second, rounded up | Per second |

- Cheapest for batch: $0.003/min with Dynamic Batch
- 60 min/month free tier
- Not as fast as Deepgram or AssemblyAI for real-time
- More suited for enterprise GCP shops

---

### OpenAI Whisper (Real-time / Streaming)

- **Batch only for most use cases** — not designed for real-time streaming
- OpenAI Realtime API uses Whisper for input transcription ($0.017/min via `gpt-realtime-whisper`)
- Deepgram's Whisper Cloud is 3x faster and 7.4% fewer errors than OpenAI's Whisper API
- Latency: 500ms+ for API calls (not competitive for real-time)

---

### ElevenLabs Scribe (STT)

- $0.22/hr batch, $0.39/hr realtime
- Good accuracy, entity detection
- Not the primary use case — ElevenLabs is TTS-first

---

### STT Ranking for Voice AI (2026)

| Rank | Provider | Why |
|---|---|---|
| 1 | **Deepgram Nova-3/Flux** | Lowest latency, best turn detection, best price |
| 2 | **AssemblyAI U3.5 Pro RT** | Highest accuracy, great for complex audio |
| 3 | **Cartesia Ink-2** | Good if using Cartesia TTS (same WebSocket) |
| 4 | **Google Cloud STT** | Good for GCP shops, higher latency |
| 5 | **ElevenLabs Scribe** | Better for batch, not streaming-first |

---

## 2. Real-Time TTS (Text-to-Speech) APIs

### ElevenLabs — Flash v2.5 / Turbo v2.5

| Metric | Flash v2.5 | Turbo v2.5 | Multilingual v2 |
|---|---|---|---|
| Latency (TTFB) | **~75ms** | 250–300ms | 400–700ms |
| Quality | Good | High | Highest |
| Pricing | $0.05/1K chars (~$0.05/min) | $0.05/1K chars | $0.10/1K chars |
| Languages | 32 | 32 | 32 |
| Max chars | 40,000 | 40,000 | 10,000 |

**Key differentiators:**
- **Flash v2.5 is the gold standard for real-time voice AI TTS in 2026**
- TTFB from North America: 100–150ms
- WebSocket support for bidirectional streaming
- `auto_mode` handles generation triggers automatically
- `flush: true` for forcing immediate output at conversation turns
- Voice library is industry-leading
- `optimize_streaming_latency` parameter can cut 50–75ms

**Latency from India (Jan 2026 test):** 478ms best-case (Streaming REST + PCM) — geography matters a lot

---

### Cartesia — Sonic 3.5

| Metric | Sonic 3.5 | Sonic 3.5 Turbo |
|---|---|---|
| Latency | **~90ms** claimed, 188ms p50 real-world | **~40ms** TTFA |
| Quality | #1 ranked naturalness | Slightly lower |
| Pricing | ~1 credit/char ($37–50/1M chars) | Same |
| Languages | 42 | 42 |

**Key differentiators:**
- **Fastest commercial TTS available** — 40ms with Turbo
- Socket-first design: multiplexes dozens of concurrent generations on one WebSocket
- Instant voice cloning from ~3–10 seconds of audio
- Same API for STT (Ink-2) and TTS — full voice loop on one socket
- Plans: Free ($0), Pro ($5), Startup ($49), Scale ($299)
- **~$0.03/min equivalent at scale**
- Supports barge-in cleanly (stops mid-sentence)

---

### OpenAI TTS

| Model | Latency | Pricing |
|---|---|---|
| tts-1 | ~300ms | $15/1M chars |
| tts-1-hd | ~400ms | $30/1M chars |

- Simple implementation
- Not as low-latency as Cartesia or ElevenLabs Flash
- Best if already in OpenAI ecosystem
- Available via Realtime API as part of speech-to-speech

---

### Google Cloud TTS

| Model | Latency | Pricing |
|---|---|---|
| Chirp 3 HD | ~150–250ms (regional) | $30/1M chars |
| Gemini 2.5 Flash TTS | ~250ms | Token-based |
| WaveNet | ~300ms | $4/1M chars |
| Neural2 | ~300ms | $16/1M chars |

- Regional endpoints give **150–250ms TTFB** from nearby locations
- 60 min/month free
- Best for GCP shops
- Bidirectional streaming support

---

### Azure Neural TTS

- $16–$24/1M chars
- 140+ languages
- Enterprise compliance (HIPAA, SOC 2)
- Good quality, not the fastest
- Regional endpoints available

---

### TTS Ranking for Voice AI (2026)

| Rank | Provider | Why |
|---|---|---|
| 1 | **Cartesia Sonic 3.5 Turbo** | Fastest (40ms), best for voice agents |
| 2 | **ElevenLabs Flash v2.5** | Best balance of speed + voice library (75ms) |
| 3 | **Deepgram Aura-2** | Good if using Deepgram STT (same ecosystem) |
| 4 | **OpenAI TTS** | Simple, integrated with Realtime API |
| 5 | **Google Cloud TTS** | Good for GCP shops, regional low latency |
| 6 | **Azure Neural TTS** | Enterprise compliance, broader than quality |

---

## 3. Full-Duplex Voice Conversation APIs

### OpenAI Realtime API (GPT-Realtime-2.1)

**The most complete speech-to-speech solution with reasoning.**

| Metric | Value |
|---|---|
| Architecture | Single model, audio in/audio out |
| Latency | ~800ms end-to-end achievable (WebRTC), 1.5–2s typical |
| Context window | 128K tokens |
| Pricing | $32/1M audio input, $64/1M audio output, $0.40 cached |
| Per-minute cost | ~$0.30–$0.45 typical |
| Transport | WebRTC, WebSocket, SIP |
| Interruptions | Native full-duplex, built-in |
| Tool calling | Parallel + narration |

**Models:**
- `gpt-realtime-2.1` — Full reasoning ($32/$64 per 1M)
- `gpt-realtime-2.1-mini` — Cheaper ($10/$20 per 1M)
- `gpt-realtime-translate` — $0.034/min
- `gpt-realtime-whisper` — $0.017/min

**Latency budget (achieving 800ms):**
| Stage | Target |
|---|---|
| Mic capture + encode | 20–40ms |
| Network client→agent | 30–80ms |
| Agent→OpenAI WS | 10–60ms |
| VAD + turn detection | 200–400ms |
| Model TTFB | ~500ms |
| Audio→client + render | 50–100ms |

**Key considerations:**
- 25% p95 latency improvement in 2.1 via caching
- Long sessions drift (2s+ after 20 turns) — need session rotation
- Prompt caching is critical (80× discount on cached input)
- **Not cheapest** — but fewest moving parts
- SIP support for telephony (100–300ms added)
- WebRTC recommended for browser/mobile

---

### Gemini Live API (Gemini 3.1 Flash Live)

**Native audio-in/audio-out with vision support.**

| Metric | Value |
|---|---|
| Architecture | Native multimodal (audio + video + text) |
| Input | Raw 16-bit PCM, 16kHz |
| Output | Raw 16-bit PCM, 24kHz |
| Transport | WebSocket (WSS) |
| VAD | Built-in, configurable |
| Barge-in | Native |
| Languages | 70–90+ |
| Session limit | 15 min (audio), 2 min (audio+video) without compression |

**Key features:**
- **Affective dialogue** — adapts tone/emotion to user
- **Proactive audio** — model decides when to respond vs stay quiet
- Function calling + Google Search grounding
- Live translation in 70+ languages
- Context window compression for unlimited sessions
- Ephemeral tokens for secure client-to-server

**Pricing:** Token-based (audio tokens at ~25 tokens/sec)

**Strengths:** Vision + voice simultaneously, barge-in, emotion detection
**Weaknesses:** Not as mature ecosystem, WebSocket-only (no WebRTC native yet)

---

### LiveKit Agents Framework

**The orchestration layer powering ChatGPT's voice.**

| Metric | Value |
|---|---|
| Architecture | Plugin-based pipeline (STT→LLM→TTS or native S2S) |
| Transport | WebRTC (native), WebSocket, telephony |
| Turn detection | Semantic turn detection model |
| Interruption | Adaptive interruption for realtime models |
| Open source | Yes (Apache 2.0) |
| Languages | Python + Node.js |
| Stars | 11,483 |

**Key differentiators:**
- **OpenAI built ChatGPT's Advanced Voice on LiveKit Cloud**
- Supports: OpenAI Realtime, Gemini Live, Deepgram, ElevenLabs, Cartesia, and 30+ providers
- Semantic turn detection built-in (distinguishes backchannel from barge-in)
- MCP support (one line)
- Multi-agent handoff
- Telephony integration (SIP, Twilio, etc.)
- Agent Builder for no-code prototyping
- LiveKit Cloud for managed deployment
- Free agent session minutes

**Latency:** Depends on stack, but WebRTC transport minimizes client-side latency

**Best for:** Teams that want full control over the pipeline with production infrastructure

---

### Vapi.ai

| Metric | Value |
|---|---|
| Platform fee | $0.05/min |
| All-in cost | $0.07–$0.15/min (BYOK) |
| Latency (p50) | 500–700ms (tuned), 850ms default |
| LLM support | Any (OpenAI, Anthropic, Google, custom) |
| TTS support | ElevenLabs, OpenAI, PlayHT, Cartesia |
| Telephony | Twilio, Telnyx, Vonage |

**Strengths:** Maximum flexibility, any LLM/TTS/STT, deep API control
**Weaknesses:** BYOK means you manage 5 vendor invoices, no built-in analytics
**HIPAA:** Enterprise add-on ($1K/month)
**Best for:** Engineering teams that want full stack control

---

### Retell.ai

| Metric | Value |
|---|---|
| All-in cost | $0.07–$0.18/min |
| Latency (p50) | **~600ms** (lowest managed platform) |
| LLM support | OpenAI, Anthropic, custom |
| Voice quality | 9.4/10 (best in class for managed) |
| Setup time | 2–6 weeks |
| HIPAA | Included on standard tier |

**Strengths:** Lowest latency managed platform, built-in analytics, SOC 2 Type II
**Weaknesses:** Less flexible than Vapi, bundled pricing gets expensive at scale
**Best for:** Non-technical teams, regulated industries, fastest time-to-production

---

### Bland.ai

| Metric | Value |
|---|---|
| Pricing | $0.08–$0.09/min (all-inclusive) |
| Latency (p50) | ~800–900ms |
| Concurrent calls | 1–unlimited (by plan) |
| Focus | Outbound call campaigns |

**Strengths:** Simplest pricing, batch calling at scale, CRM integrations
**Weaknesses:** Lowest voice quality, locked into Bland's LLM stack
**Best for:** High-volume outbound calling campaigns

---

### Full-Duplex Voice Platform Comparison

| Platform | Latency (p50) | All-in Cost | Flexibility | Best For |
|---|---|---|---|---|
| **OpenAI Realtime** | 800ms | $0.30–$0.45/min | Medium | Reasoning-heavy agents |
| **Gemini Live** | ~600–800ms | Token-based | Medium | Vision+voice, multilingual |
| **LiveKit Agents** | Depends on stack | Variable | **Full** | Custom pipelines |
| **Vapi** | 500–700ms | $0.07–$0.15/min | **Full** | BYOK developers |
| **Retell** | **600ms** | $0.07–$0.18/min | Medium | Managed inbound |
| **Bland** | 850ms | $0.08–$0.09/min | Low | Outbound campaigns |
| **Pipecat (self-host)** | 500–800ms | ~$0.15/min | **Full** | Custom, multi-vendor |

---

## 4. UX Patterns for Smooth Live Mode

### How ChatGPT Handles Voice Interruptions

**GPT-Live (July 2026)** introduced true full-duplex:
- Model processes incoming audio **while generating output**
- Makes interaction decisions **many times per second** (speak, listen, pause, interrupt)
- No silence gate — turn-taking is a **behavior**, not a threshold
- Backchannels ("uh-huh", "mm-hmm") handled naturally
- Model delegates complex reasoning to GPT-5.5 in background

**Previous approach (Advanced Voice Mode):**
- Cascaded pipeline with VAD silence threshold
- User had to fill thinking pauses with "um" or "hmm" to avoid premature cut-off
- GPT-Live fixes this by continuously monitoring intent

---

### How Gemini Live Handles Audio Streaming

- **Barge-in:** User can interrupt at any time; server sends `"interrupted": true`
- Client must **immediately discard audio buffer** when interrupted
- Automatic VAD with configurable parameters:
  - `start_of_speech_sensitivity`
  - `end_of_speech_sensitivity`  
  - `prefix_padding_ms`
  - `silence_duration_ms`
- Proactive audio mode: model decides when NOT to respond
- Affective dialogue: adapts tone to user's emotional state

---

### Buffering/Streaming Techniques to Minimize Latency

1. **Send small audio chunks (20–40ms)** — don't buffer 1 second before sending
2. **Stream TTS output** — start playback before full generation completes
3. **Use WebRTC over WebSocket** — 200–400ms faster in browsers (native jitter buffering)
4. **Overlap pipeline stages** — start LLM on partial transcripts, start TTS on partial LLM output
5. **Pre-generate cached phrases** — greetings, hold messages, sign-offs as raw PCM
6. **Connection pooling** — reuse WebSocket connections to avoid repeated handshakes
7. **Co-locate services** — deploy near API endpoints (e.g., US-East for OpenAI)
8. **Prompt caching** — 80× cost savings and lower latency on repeated context

---

### Barge-In Implementation (Production 2026)

**The barge-in chain (must complete in < 200–300ms):**

```
1. VAD detects speech on incoming audio (while agent is speaking)
2. Classify: backchannel vs genuine interruption
3. Stop TTS playout (< 60ms)
4. Cancel LLM generation (< 40ms)
5. Flush audio buffer
6. Re-enter listening mode
7. Stash interrupted utterance in conversation state
```

**Classification decisions:**
| Type | Action |
|---|---|
| Backchannel ("mm-hmm", "yeah") | Duck audio, continue speaking |
| Correction ("no, actually") | Pause and listen |
| Cancellation ("stop") | Stop and reset |
| Impatience ("skip ahead") | Summarize quickly |

**Key metrics to track:**
- TTS flush time (target: < 60ms)
- False barge-in rate (target: < 2%)
- Turn-taking gap (target: 200–400ms)
- Ignored interruption rate
- Repeat rate (user says same thing again)
- Dead-air p95

**Framework implementations:**
- LiveKit: Adaptive interruption model (acoustic backchannel detection)
- Pipecat: SmartTurnAnalyzer
- Vapi: Endpointing controls

---

### Audio Format Considerations

| Format | Use Case | Notes |
|---|---|---|
| **PCM 16-bit** | Lowest latency processing | Gemini Live API default (16kHz in, 24kHz out) |
| **Opus** | WebRTC transport | Good compression, low latency |
| **PCM 24kHz** | ElevenLabs lowest latency | Raw PCM for direct processing |
| **µ-law 8kHz** | Telephony/Twilio | Telephony standard |
| **MP3** | Direct playback | Higher latency due to encoding |
| **PCM 22050Hz** | ElevenLabs best TTFB | Streaming REST optimal |

**Recommendation:** Use PCM for server-side processing, Opus for WebRTC transport, µ-law for telephony.

---

## 5. Open Source Frameworks

### Pipecat (by Daily)

**Most popular voice AI framework.**

| Metric | Value |
|---|---|
| Stars | 13,662 |
| Language | Python (98.3%) |
| License | BSD-2-Clause |
| Latest | v1.6.0 (July 2026) |
| Releases | 115 |

**Supported providers:**
- **STT:** Deepgram, AssemblyAI, Google, Azure, Gladia, Groq, Mistral, Moonshine, NVIDIA, OpenAI Whisper
- **TTS:** ElevenLabs, Cartesia, Deepgram, Azure, Google, OpenAI, PlayHT, Rime, Fish Audio, Hume, Speechify
- **LLM:** OpenAI, Anthropic, Google, Groq, NVIDIA
- **S2S:** AWS Nova Sonic, Gemini Multimodal Live, Grok Voice, OpenAI Realtime, Ultravox
- **Transport:** Daily (WebRTC), FastAPI WebSocket, LiveKit, SmallWebRTC, Vonage, WhatsApp, Local

**Key features:**
- Composable pipelines (modular processors)
- Multi-agent systems (handoff, fan-out, sidecar workers)
- Pipecat CLI for scaffolding (`pipecat init`)
- Flows for structured conversations
- Deploy to Pipecat Cloud or self-host
- 1,000+ teams building on Pipecat Cloud

**Pipecat Cloud:** Managed deployment with Daily's global WebRTC infrastructure. GA since Jan 2026.

---

### LiveKit Agents Framework

| Metric | Value |
|---|---|
| Stars | 11,483 |
| Languages | Python + Node.js |
| License | Apache 2.0 |
| Latest | v1.6.7 (July 2026) |

**Key features:**
- Plugin ecosystem for every major AI provider
- Semantic turn detection (custom transformer model)
- Adaptive interruption handling
- MCP support
- Multi-agent handoff
- Built-in test framework
- Agent Builder (no-code prototyping)
- LiveKit Cloud for managed deployment
- Telephony via SIP integration

**LiveKit Cloud:** Free tier includes 1,000 agent session minutes/month.

---

### OpenAI Realtime API SDK

- Official SDKs for Python and Node.js
- WebRTC for browsers, WebSocket for servers
- Ephemeral tokens for secure client access
- Agents SDK with tool calling support
- Not open-source (API-based)

---

### Other Open-Source Alternatives

| Framework | Notes |
|---|---|
| **Kyutai Moshi** | True full-duplex open-source LLM (~200ms in practice) |
| **Whisper.cpp** | Local Whisper inference, not real-time streaming |
| **SpeechBrain** | Research-oriented, not production-ready for real-time |
| **NVIDIA NeMo** | Enterprise-grade, not fully open |

---

## 6. Overall Recommendations

### Closest to ChatGPT/Gemini Quality

| Approach | Quality | Latency | Cost | Complexity |
|---|---|---|---|---|
| **OpenAI Realtime (GPT-Realtime-2.1)** | ★★★★★ | 800ms–2s | $0.30–0.45/min | Low (single API) |
| **Gemini Live API** | ★★★★☆ | 600–800ms | Token-based | Medium |
| **LiveKit + OpenAI Realtime** | ★★★★★ | 600–800ms | Variable | Medium-High |
| **Pipecat + Deepgram + Cartesia** | ★★★★☆ | 500–800ms | ~$0.15/min | Medium |
| **Vapi + ElevenLabs + GPT-4o** | ★★★★☆ | 500–700ms | $0.07–0.15/min | Low-Medium |

### Best Stacks by Use Case

**Lowest latency (competitive with ChatGPT):**
- Cartesia Sonic 3.5 (40ms TTS) + Deepgram Flux (200ms STT) + GPT-4o-mini (< 200ms LLM) on LiveKit
- Target: ~500ms end-to-end

**Cheapest production voice AI:**
- Deepgram Nova-3 ($0.0048/min) + OpenAI GPT-4o-mini text ($0.15/1M) + ElevenLabs Flash ($0.05/min)
- Total: ~$0.10–0.15/min

**Managed, fastest to ship:**
- Retell.ai (~600ms, $0.07–0.18/min) or Vapi.ai ($0.07–0.15/min)

**Full control, enterprise:**
- LiveKit Agents + your choice of STT/LLM/TTS, deployed on LiveKit Cloud or self-hosted

**True full-duplex (like ChatGPT Live):**
- Gemini Live API (available now) or OpenAI Realtime API
- Kyutai Moshi for self-hosted full-duplex

### Cost Comparison Summary

| Solution | Per-Minute Cost | Monthly at 10K min |
|---|---|---|
| Deepgram Flux + GPT-4o-mini + ElevenLabs Flash (self-host) | ~$0.12–0.15 | $1,200–1,500 |
| OpenAI Realtime (GPT-Realtime-2.1) | ~$0.30–0.45 | $3,000–4,500 |
| Retell.ai (managed) | ~$0.07–0.18 | $700–1,800 |
| Vapi.ai (BYOK) | ~$0.07–0.15 | $700–1,500 |
| Bland.ai (all-inclusive) | ~$0.08–0.09 | $800–900 |
| Pipecat self-host (chained) | ~$0.15 | $1,500 |
| Deepgram Voice Agent API (managed) | ~$0.05–0.16 | $500–1,600 |

---

## Sources

- Deepgram pricing page & documentation (deepgram.com, developers.deepgram.com) — May/July 2026
- ElevenLabs pricing, TTS API docs, latency optimization guide — 2026
- OpenAI Realtime API docs, pricing, GPT-Realtime-2 announcement — May/July 2026
- Google Gemini Live API documentation — June 2026
- AssemblyAI pricing & streaming docs — July 2026
- Cartesia docs, pricing, Sonic 3.5 announcement — May/June 2026
- LiveKit Agents documentation & GitHub — July 2026
- Pipecat documentation & GitHub — July 2026
- Vapi vs Retell vs Bland comparison articles — March–May 2026
- Voice AI barge-in and turn-taking guides — Feb/June/July 2026
- Independent latency tests (Sherlock Calls, VEXYL AI, TokenMix) — 2026
