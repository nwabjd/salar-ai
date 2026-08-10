import { describe, expect, it, vi } from 'vitest'
import { HybridVoiceClient } from './hybrid-voice-client'

function fakeClient() {
  return { start: vi.fn(async () => undefined), sendText: vi.fn(), stop: vi.fn() }
}

describe('HybridVoiceClient', () => {
  it('starts in native Gemini Live mode', async () => {
    const native = fakeClient()
    const fallback = fakeClient()
    const client = new HybridVoiceClient(native, fallback)
    await client.start()
    client.sendText('hello')
    expect(native.start).toHaveBeenCalledOnce()
    expect(native.sendText).toHaveBeenCalledWith('hello')
    expect(fallback.start).not.toHaveBeenCalled()
  })

  it('switches once to fallback when Gemini asks for it', async () => {
    const native = fakeClient()
    const fallback = fakeClient()
    const client = new HybridVoiceClient(native, fallback)
    await client.start()
    await client.activateFallback()
    await client.activateFallback()
    client.sendText('continue')
    expect(native.stop).toHaveBeenCalledOnce()
    expect(fallback.start).toHaveBeenCalledOnce()
    expect(fallback.sendText).toHaveBeenCalledWith('continue')
  })

  it('falls back automatically when native startup fails', async () => {
    const native = fakeClient()
    native.start.mockRejectedValueOnce(new Error('provider unavailable'))
    const fallback = fakeClient()
    const client = new HybridVoiceClient(native, fallback)
    await client.start()
    expect(native.stop).toHaveBeenCalledOnce()
    expect(fallback.start).toHaveBeenCalledOnce()
  })
})
