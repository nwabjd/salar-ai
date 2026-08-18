import type { LiveEvent } from './realtime-state'

const SPEECH_THRESHOLD = 14
const SILENCE_TO_STOP_MS = 900
const MAX_TURN_MS = 12_000
const MIN_AUDIO_BYTES = 800

export function shouldStopFallbackRecording(heardSpeech: boolean, silenceMs: number): boolean {
  return heardSpeech && silenceMs >= SILENCE_TO_STOP_MS
}

type FallbackApi = {
  createConversation(title?: string): Promise<{ id: string }>
  stt(blob: Blob, fast?: boolean): Promise<string>
  tts(text: string, fast?: boolean): Promise<Blob>
  chatStream(
    conversationId: string,
    content: string,
    onToken: (token: string) => void,
    onDone: (messageId: string, createdAt: string) => void,
    onError?: (error: Error) => void,
    onTool?: (toolName: string, args: Record<string, unknown>) => void,
    onToolResult?: (toolName: string, result: Record<string, unknown>) => void,
    fast?: boolean,
  ): unknown
}

type FallbackOptions = {
  token: string
  onEvent: (event: LiveEvent) => void
  onMicVolume?: (volume: number) => void
  onPlaybackVolume?: (volume: number) => void
  api: FallbackApi
  playback?: (blob: Blob, onVolume?: (volume: number) => void) => Promise<void>
}

export class FallbackVoiceClient {
  private readonly api: FallbackApi
  private readonly playback: (blob: Blob, onVolume?: (volume: number) => void) => Promise<void>
  private conversationId = ''
  private stream: MediaStream | null = null
  private audioContext: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private recorder: MediaRecorder | null = null
  private monitor: ReturnType<typeof setInterval> | null = null
  private maxTurn: ReturnType<typeof setTimeout> | null = null
  private chunks: Blob[] = []
  private stopped = false
  private busy = false
  private heardSpeech = false
  private lastSpeechAt = 0

  constructor(private readonly options: FallbackOptions) {
    this.api = options.api
    this.playback = options.playback || this.playBlob.bind(this)
  }

  async start(): Promise<void> {
    this.stopped = false
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    })
    this.audioContext = new AudioContext({ latencyHint: 'interactive' })
    if (this.audioContext.state === 'suspended') await this.audioContext.resume()
    const source = this.audioContext.createMediaStreamSource(this.stream)
    this.analyser = this.audioContext.createAnalyser()
    this.analyser.fftSize = 512
    source.connect(this.analyser)
    this.options.onEvent({ type: 'ready' })
    this.startRecording()
  }

  sendText(text: string): void {
    const clean = text.trim()
    if (!clean || this.busy || this.stopped) return
    void this.processText(clean, false)
  }

  stop(): void {
    this.stopped = true
    this.clearTimers()
    if (this.recorder?.state === 'recording') {
      this.recorder.onstop = null
      try { this.recorder.stop() } catch {}
    }
    this.recorder = null
    this.stream?.getTracks().forEach((track) => track.stop())
    this.stream = null
    this.audioContext?.close().catch(() => undefined)
    this.audioContext = null
    this.options.onMicVolume?.(0)
    this.options.onPlaybackVolume?.(0)
  }

  async acceptRecordedTurn(blob: Blob): Promise<void> {
    if (this.stopped || this.busy || blob.size < MIN_AUDIO_BYTES) return
    this.busy = true
    this.options.onEvent({ type: 'speech_stopped' })
    try {
      const text = (await this.api.stt(blob, false)).trim()
      if (!text) return
      this.options.onEvent({ type: 'input_transcript_completed', text })
      await this.processText(text, true)
    } catch (reason) {
      this.options.onEvent({ type: 'error', error: reason instanceof Error ? reason.message : 'Fallback voice failed' })
    } finally {
      this.busy = false
      if (!this.stopped) this.startRecording()
    }
  }

  private async processText(text: string, alreadyBusy: boolean): Promise<void> {
    if (!alreadyBusy) this.busy = true
    try {
      if (!this.conversationId) {
        this.conversationId = (await this.api.createConversation('Live session')).id
      }
      let answer = ''
      await new Promise<void>((resolve, reject) => {
        this.api.chatStream(
          this.conversationId,
          text,
          (token) => {
            answer += token
            this.options.onEvent({ type: 'output_transcript_delta', text: token })
          },
          () => resolve(),
          reject,
          undefined,
          undefined,
          false,
        )
      })
      const complete = answer.trim()
      if (!complete || this.stopped) return
      this.options.onEvent({ type: 'output_transcript_completed', text: complete })
      const voice = await this.api.tts(complete, false)
      if (this.stopped) return
      this.options.onEvent({ type: 'audio' })
      await this.playback(voice, this.options.onPlaybackVolume)
      this.options.onEvent({ type: 'response_done' })
      this.options.onEvent({ type: 'playback_drained' })
    } catch (reason) {
      this.options.onEvent({ type: 'error', error: reason instanceof Error ? reason.message : 'Fallback response failed' })
    } finally {
      if (!alreadyBusy) {
        this.busy = false
        if (!this.stopped) this.startRecording()
      }
    }
  }

  private startRecording(): void {
    if (this.stopped || this.busy || !this.stream || !this.analyser || this.recorder?.state === 'recording') return
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm'
    const recorder = new MediaRecorder(this.stream, { mimeType })
    this.recorder = recorder
    this.chunks = []
    this.heardSpeech = false
    this.lastSpeechAt = 0
    recorder.ondataavailable = (event) => { if (event.data.size) this.chunks.push(event.data) }
    recorder.onstop = () => {
      this.clearTimers()
      this.recorder = null
      const blob = new Blob(this.chunks, { type: mimeType })
      this.chunks = []
      if (!this.stopped && this.heardSpeech) void this.acceptRecordedTurn(blob)
      else if (!this.stopped) setTimeout(() => this.startRecording(), 150)
    }
    recorder.start(250)
    const samples = new Uint8Array(this.analyser.frequencyBinCount)
    this.monitor = setInterval(() => {
      if (!this.analyser || recorder.state !== 'recording') return
      this.analyser.getByteFrequencyData(samples)
      const average = samples.reduce((sum, value) => sum + value, 0) / samples.length
      this.options.onMicVolume?.(average)
      const now = Date.now()
      if (average >= SPEECH_THRESHOLD) {
        this.heardSpeech = true
        this.lastSpeechAt = now
        this.options.onEvent({ type: 'speech_started' })
      } else if (shouldStopFallbackRecording(this.heardSpeech, now - this.lastSpeechAt)) {
        recorder.stop()
      }
    }, 80)
    this.maxTurn = setTimeout(() => {
      if (recorder.state === 'recording') recorder.stop()
    }, MAX_TURN_MS)
  }

  private clearTimers(): void {
    if (this.monitor) clearInterval(this.monitor)
    if (this.maxTurn) clearTimeout(this.maxTurn)
    this.monitor = null
    this.maxTurn = null
  }

  private async playBlob(blob: Blob, onVolume?: (volume: number) => void): Promise<void> {
    const context = this.audioContext || new AudioContext({ latencyHint: 'interactive' })
    this.audioContext = context
    if (context.state === 'suspended') await context.resume()
    const buffer = await context.decodeAudioData(await blob.arrayBuffer())
    const source = context.createBufferSource()
    const analyser = context.createAnalyser()
    analyser.fftSize = 256
    source.buffer = buffer
    source.connect(analyser)
    analyser.connect(context.destination)
    const values = new Uint8Array(analyser.frequencyBinCount)
    let frame = 0
    const sample = () => {
      analyser.getByteFrequencyData(values)
      onVolume?.(values.reduce((sum, value) => sum + value, 0) / values.length)
      frame = requestAnimationFrame(sample)
    }
    await new Promise<void>((resolve) => {
      source.onended = () => resolve()
      source.start()
      frame = requestAnimationFrame(sample)
    })
    cancelAnimationFrame(frame)
    onVolume?.(0)
  }
}
