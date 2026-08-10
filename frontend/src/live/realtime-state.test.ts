import { describe, expect, it } from 'vitest'
import { initialLiveState, liveReducer } from './realtime-state'

describe('Live Realtime state', () => {
  it('waits for both response completion and drained playback before listening again', () => {
    let state = liveReducer(initialLiveState, { type: 'ready' })
    state = liveReducer(state, { type: 'speech_stopped' })
    state = liveReducer(state, { type: 'audio' })
    expect(state.phase).toBe('speaking')

    state = liveReducer(state, { type: 'response_done' })
    expect(state.phase).toBe('speaking')

    state = liveReducer(state, { type: 'playback_drained' })
    expect(state.phase).toBe('listening')
  })

  it('records completed user and SALAR transcripts', () => {
    let state = liveReducer(initialLiveState, { type: 'input_transcript_completed', text: 'Hello SALAR' })
    state = liveReducer(state, { type: 'output_transcript_delta', text: 'Hello ' })
    state = liveReducer(state, { type: 'output_transcript_completed', text: 'Hello there' })
    expect(state.history).toEqual([
      { role: 'user', text: 'Hello SALAR' },
      { role: 'salar', text: 'Hello there' },
    ])
  })
})
