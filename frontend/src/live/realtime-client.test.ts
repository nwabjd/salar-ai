import { describe, expect, it } from 'vitest'
import { pcm16ToBase64, realtimeWebSocketUrl, shouldReportUnexpectedClose } from './realtime-client'

describe('Realtime client helpers', () => {
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
})
