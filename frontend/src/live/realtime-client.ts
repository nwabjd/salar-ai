import type { LiveEvent } from './realtime-state'

const DEFAULT_REALTIME_API = (import.meta.env.VITE_API_URL || 'https://salar-backend.onrender.com').replace(/\/$/, '')

export function realtimeWebSocketUrl(baseUrl = DEFAULT_REALTIME_API): string {
  const url = new URL(baseUrl)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = `${url.pathname.replace(/\/$/, '')}/ws/live`
  url.search = ''
  url.hash = ''
  return url.toString().replace(/\/$/, '')
}

export function pcm16ToBase64(samples: Int16Array): string {
  const bytes = new Uint8Array(samples.buffer, samples.byteOffset, samples.byteLength)
  let binary = ''
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000))
  }
  return btoa(binary)
}

export function shouldReportUnexpectedClose(closed: boolean, receivedServerError: boolean): boolean {
  return !closed && !receivedServerError
}

function base64ToPcm16(value: string): Int16Array {
  const binary = atob(value)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
  return new Int16Array(bytes.buffer)
}

type ClientOptions = {
  token: string
  voice?: 'marin' | 'cedar'
  onEvent: (event: LiveEvent) => void
  onVolume?: (volume: number) => void
}

export class RealtimeVoiceClient {
  private socket: WebSocket | null = null
  private stream: MediaStream | null = null
  private audioContext: AudioContext | null = null
  private worklet: AudioWorkletNode | null = null
  private closed = false
  private receivedServerError = false

  constructor(private readonly options: ClientOptions) {}

  async start(): Promise<void> {
    this.closed = false
    this.receivedServerError = false
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    })
    this.audioContext = new AudioContext({ latencyHint: 'interactive' })
    await this.audioContext.audioWorklet.addModule('/audio-processor.js')
    if (this.audioContext.state === 'suspended') await this.audioContext.resume()

    const source = this.audioContext.createMediaStreamSource(this.stream)
    this.worklet = new AudioWorkletNode(this.audioContext, 'salar-audio', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1] })
    source.connect(this.worklet)
    this.worklet.connect(this.audioContext.destination)
    this.worklet.port.onmessage = (message) => this.handleWorkletMessage(message.data)

    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(realtimeWebSocketUrl())
      this.socket = socket
      socket.onopen = () => {
        socket.send(JSON.stringify({ type: 'setup', token: this.options.token, voice: this.options.voice || 'marin' }))
        resolve()
      }
      socket.onerror = () => reject(new Error('Live voice connection failed'))
      socket.onclose = () => {
        if (shouldReportUnexpectedClose(this.closed, this.receivedServerError)) {
          this.options.onEvent({ type: 'error', error: 'Live voice disconnected' })
        }
      }
      socket.onmessage = (message) => this.handleSocketMessage(message.data)
    })
  }

  sendText(text: string): void {
    const clean = text.trim()
    if (clean && this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify({ type: 'text', text: clean }))
  }

  stop(): void {
    this.closed = true
    this.worklet?.port.postMessage({ type: 'stop' })
    this.socket?.close(1000, 'Live closed')
    this.socket = null
    this.worklet?.disconnect()
    this.worklet = null
    this.stream?.getTracks().forEach((track) => track.stop())
    this.stream = null
    this.audioContext?.close().catch(() => undefined)
    this.audioContext = null
  }

  private handleWorkletMessage(message: { type?: string; samples?: Int16Array; volume?: number }): void {
    if (message.type === 'capture' && message.samples && this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: 'audio', data: pcm16ToBase64(message.samples) }))
      this.options.onVolume?.(message.volume || 0)
    } else if (message.type === 'playback_drained') {
      this.options.onEvent({ type: 'playback_drained' })
      this.options.onVolume?.(0)
    } else if (message.type === 'playback_volume') {
      this.options.onVolume?.(message.volume || 0)
    }
  }

  private handleSocketMessage(raw: string): void {
    let message: Record<string, unknown>
    try { message = JSON.parse(raw) } catch { return }
    if (message.type === 'audio' && typeof message.data === 'string') {
      this.worklet?.port.postMessage({ type: 'playback', samples: base64ToPcm16(message.data) })
      this.options.onEvent({ type: 'audio' })
      return
    }
    if (message.type === 'speech_started') this.worklet?.port.postMessage({ type: 'stop' })
    if (message.type === 'error') {
      this.receivedServerError = true
      this.options.onEvent({ type: 'error', error: typeof message.error === 'string' ? message.error : 'Live voice error' })
      return
    }
    const eventTypes = new Set([
      'ready', 'speech_started', 'speech_stopped', 'response_done',
      'input_transcript_delta', 'input_transcript_completed',
      'output_transcript_delta', 'output_transcript_completed',
    ])
    if (typeof message.type === 'string' && eventTypes.has(message.type)) {
      this.options.onEvent({ type: message.type, text: typeof message.text === 'string' ? message.text : '' } as LiveEvent)
    }
  }
}
