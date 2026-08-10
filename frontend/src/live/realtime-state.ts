export type LivePhase = 'connecting' | 'reconnecting' | 'listening' | 'thinking' | 'speaking' | 'error'
export type LiveHistoryItem = { role: 'user' | 'salar'; text: string }

export type LiveState = {
  phase: LivePhase
  inputTranscript: string
  outputTranscript: string
  history: LiveHistoryItem[]
  responseDone: boolean
  playbackPending: boolean
  error: string
}

export type LiveEvent =
  | { type: 'ready' | 'reconnecting' | 'speech_started' | 'speech_stopped' | 'audio' | 'response_done' | 'playback_drained' }
  | { type: 'input_transcript_delta' | 'input_transcript_completed' | 'output_transcript_delta' | 'output_transcript_completed'; text: string }
  | { type: 'error'; error: string }

export const initialLiveState: LiveState = {
  phase: 'connecting',
  inputTranscript: '',
  outputTranscript: '',
  history: [],
  responseDone: false,
  playbackPending: false,
  error: '',
}

function addHistory(state: LiveState, role: LiveHistoryItem['role'], text: string): LiveHistoryItem[] {
  const clean = text.trim()
  if (!clean) return state.history
  const last = state.history[state.history.length - 1]
  if (last?.role === role && last.text === clean) return state.history
  return [...state.history, { role, text: clean }]
}

export function liveReducer(state: LiveState, event: LiveEvent): LiveState {
  switch (event.type) {
    case 'ready':
      return { ...state, phase: 'listening', error: '' }
    case 'reconnecting':
      return { ...state, phase: 'reconnecting', error: '' }
    case 'speech_started':
      return { ...state, phase: 'listening', outputTranscript: '', responseDone: false, playbackPending: false }
    case 'speech_stopped':
      return { ...state, phase: 'thinking', inputTranscript: '', responseDone: false, playbackPending: false }
    case 'audio':
      return { ...state, phase: 'speaking', playbackPending: true }
    case 'response_done':
      return { ...state, responseDone: true, phase: state.playbackPending ? 'speaking' : 'listening' }
    case 'playback_drained':
      return { ...state, playbackPending: false, phase: state.responseDone ? 'listening' : state.phase }
    case 'input_transcript_delta':
      return { ...state, inputTranscript: state.inputTranscript + event.text }
    case 'input_transcript_completed':
      return { ...state, inputTranscript: event.text, history: addHistory(state, 'user', event.text) }
    case 'output_transcript_delta':
      return { ...state, outputTranscript: state.outputTranscript + event.text }
    case 'output_transcript_completed':
      return { ...state, outputTranscript: event.text, history: addHistory(state, 'salar', event.text) }
    case 'error':
      return { ...state, phase: 'error', error: event.error }
  }
}
