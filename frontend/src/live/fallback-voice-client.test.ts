import { describe, expect, it, vi } from 'vitest'
import { FallbackVoiceClient, shouldStopFallbackRecording } from './fallback-voice-client'

describe('FallbackVoiceClient', () => {
  it('waits for real speech before silence can end a recording', () => {
    expect(shouldStopFallbackRecording(false, 1_500)).toBe(false)
    expect(shouldStopFallbackRecording(true, 899)).toBe(false)
    expect(shouldStopFallbackRecording(true, 900)).toBe(true)
  })

  it('transcribes, streams, then speaks the complete answer before listening again', async () => {
    const events: Array<Record<string, unknown>> = []
    const tts = vi.fn(async () => new Blob(['voice']))
    const playback = vi.fn(async () => undefined)
    const client = new FallbackVoiceClient({
      token: 'token',
      onEvent: (event) => events.push(event),
      api: {
        createConversation: vi.fn(async () => ({ id: 'conversation-1' })),
        stt: vi.fn(async () => 'What is SALAR?'),
        tts,
        chatStream: (_id, _text, onToken, onDone) => {
          onToken('SALAR is ')
          onToken('your private AI.')
          onDone('message-1', 'now')
        },
      },
      playback,
    })

    await client.acceptRecordedTurn(new Blob(['recorded speech'.repeat(100)]))

    expect(tts).toHaveBeenCalledWith('SALAR is your private AI.', false)
    expect(playback).toHaveBeenCalledOnce()
    expect(events).toContainEqual({ type: 'input_transcript_completed', text: 'What is SALAR?' })
    expect(events).toContainEqual({ type: 'output_transcript_completed', text: 'SALAR is your private AI.' })
    expect(events.slice(-2)).toEqual([{ type: 'response_done' }, { type: 'playback_drained' }])
  })

  it('uses Gemini-quality speech services instead of fast legacy mode', async () => {
    const stt = vi.fn(async () => 'Hello')
    const tts = vi.fn(async () => new Blob(['voice']))
    const client = new FallbackVoiceClient({
      token: 'token',
      onEvent: vi.fn(),
      api: {
        createConversation: vi.fn(async () => ({ id: 'conversation-1' })),
        stt,
        tts,
        chatStream: (_id, _text, onToken, onDone) => { onToken('Hi.'); onDone('1', 'now') },
      },
      playback: vi.fn(async () => undefined),
    })

    await client.acceptRecordedTurn(new Blob(['recorded speech'.repeat(100)]))

    expect(stt).toHaveBeenCalledWith(expect.any(Blob), false)
    expect(tts).toHaveBeenCalledWith('Hi.', false)
  })
})
