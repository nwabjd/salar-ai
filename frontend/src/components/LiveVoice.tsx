import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { LiveOrb } from './LiveOrb'
import { type LiveState } from '../live/realtime-state'

interface LiveVoiceProps {
  state: LiveState
  volume: number
  textInput: string
  onTextInput: (v: string) => void
  onTextSubmit: () => void
  onToggleMic: () => void
  onClose: () => void
}

export default function LiveVoice({ state, volume, textInput, onTextInput, onTextSubmit, onToggleMic, onClose }: LiveVoiceProps) {
  const [elapsed, setElapsed] = useState(0)

  const isActive = state.phase === 'listening' || state.phase === 'speaking'
  const isThinking = state.phase === 'thinking'
  const isListening = state.phase === 'listening'
  const isSpeaking = state.phase === 'speaking'

  useEffect(() => {
    let id: ReturnType<typeof setInterval>
    if (isActive) {
      id = setInterval(() => setElapsed((t) => t + 1), 1000)
    } else {
      setElapsed(0)
    }
    return () => clearInterval(id)
  }, [isActive])

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
  }

  const orbState = isThinking ? 'thinking' : isSpeaking ? 'speaking' : isListening ? 'listening' : 'idle'

  return (
    <div className="lv-wrap">
      <button className="lv-close" onClick={onClose}><X size={18} /></button>

      {/* Timer */}
      <span className={`lv-timer${isActive ? ' active' : ''}`}>
        {formatTime(elapsed)}
      </span>

      {/* Orb */}
      <LiveOrb
        size={320}
        state={orbState}
        onClick={onToggleMic}
      />

      {/* Transcript */}
      {state.history.length > 0 && (
        <div className="lv-transcript">
          {state.history.map((turn, i) => (
            <p key={i} className={`lv-turn lv-turn-${turn.role}`}>{turn.text}</p>
          ))}
          {state.inputTranscript && <p className="lv-turn lv-turn-user">{state.inputTranscript}</p>}
        </div>
      )}

      {/* Text input */}
      <form className="lv-text-form" onSubmit={(e) => { e.preventDefault(); onTextSubmit() }}>
        <input
          className="lv-text-input"
          placeholder="Type a message…"
          value={textInput}
          onChange={(e) => onTextInput(e.target.value)}
        />
        <button type="submit" className="lv-text-send" disabled={!textInput.trim() || isThinking || isSpeaking}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </form>

      {/* Error */}
      {state.error && <p className="lv-error">{state.error}</p>}
    </div>
  )
}
