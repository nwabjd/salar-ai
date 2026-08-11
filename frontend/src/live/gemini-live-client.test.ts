import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import * as liveClient from './gemini-live-client'
import {
  pcm16ToBase64,
  realtimeWebSocketUrl,
  shouldReportUnexpectedClose,
  translateGeminiSocketMessage,
} from './gemini-live-client'

describe('Realtime client helpers', () => {
  it('enables speaker echo protection only for installed iOS web apps', () => {
    const detector = (liveClient as unknown as { isIOSStandaloneWebApp?: (agent: string, standalone: boolean) => boolean }).isIOSStandaloneWebApp
    expect(detector).toBeTypeOf('function')
    if (!detector) return
    expect(detector('Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X)', true)).toBe(true)
    expect(detector('Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X)', false)).toBe(false)
    expect(detector('Mozilla/5.0 (Windows NT 10.0; Win64; x64)', true)).toBe(false)
  })

  it('loads the AudioWorklet through Vite fingerprinting for installed iOS web apps', () => {
    const clientSource = readFileSync('src/live/gemini-live-client.ts', 'utf8')
    expect(clientSource).toContain("new URL('./audio-processor.js', import.meta.url).href")
    expect(clientSource).not.toContain("addModule('/audio-processor.js')")
  })

  it('derives secure and local websocket URLs', () => {
    expect(realtimeWebSocketUrl('https://salar.example.com')).toBe('wss://salar.example.com/ws/live')
    expect(realtimeWebSocketUrl('http://127.0.0.1:8000/')).toBe('ws://127.0.0.1:8000/ws/live')
  })

  it('encodes raw PCM16 bytes without changing byte order', () => {
    expect(pcm16ToBase64(new Int16Array([0, 32767, -32768]))).toBe('AAD/fwCA')
  })

  it('does not replace a specific server error with a duplicate disconnect error', () => {
    expect(shouldReportUnexpectedClose(false, true)).toBe(false)
    expect(shouldReportUnexpectedClose(false, false)).toBe(true)
    expect(shouldReportUnexpectedClose(true, false)).toBe(false)
  })

  it('maps interruption to immediate playback cancellation', () => {
    expect(translateGeminiSocketMessage({ type: 'interrupted' })).toEqual({ kind: 'interrupted' })
  })

  it('maps provider retry and fallback without treating them as terminal errors', () => {
    expect(translateGeminiSocketMessage({ type: 'provider_retry' })).toEqual({ kind: 'reconnecting' })
    expect(translateGeminiSocketMessage({ type: 'fallback_required' })).toEqual({ kind: 'fallback' })
  })

  it('preserves stable SALAR events', () => {
    expect(translateGeminiSocketMessage({ type: 'response_done' })).toEqual({
      kind: 'event',
      event: { type: 'response_done', text: '' },
    })
  })
})
