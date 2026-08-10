import { describe, expect, it } from 'vitest'
import { pcm16ToBase64, realtimeWebSocketUrl } from './realtime-client'

describe('Realtime client helpers', () => {
  it('derives secure and local websocket URLs', () => {
    expect(realtimeWebSocketUrl('https://salar.example.com')).toBe('wss://salar.example.com/ws/live')
    expect(realtimeWebSocketUrl('http://127.0.0.1:8000/')).toBe('ws://127.0.0.1:8000/ws/live')
  })

  it('encodes raw PCM16 bytes without changing byte order', () => {
    expect(pcm16ToBase64(new Int16Array([0, 32767, -32768]))).toBe('AAD/fwCA')
  })
})
