import { useEffect, useRef, useState } from 'react'
import { Mic, MicOff, X, Loader } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
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
  const inputRef = useRef<HTMLInputElement>(null)

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

  const bars = 48

  return (
    <div className="lv-wrap">
      <div className="lv-container">
        <button className="lv-close" onClick={onClose}><X size={18} /></button>

        {/* Mic button */}
        <button className={`lv-mic-btn${isActive ? ' active' : ''}${isThinking ? ' thinking' : ''}`} onClick={onToggleMic}>
          <AnimatePresence mode="wait">
            {isThinking ? (
              <motion.div key="loader" initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.5 }}>
                <Loader size={28} className="lv-spin" />
              </motion.div>
            ) : isActive ? (
              <motion.div key="stop" initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.5 }}>
                <MicOff size={28} />
              </motion.div>
            ) : (
              <motion.div key="mic" initial={{ opacity: 0, scale: 0.5 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.5 }}>
                <Mic size={28} />
              </motion.div>
            )}
          </AnimatePresence>
        </button>

        {/* Timer */}
        <span className={`lv-timer${isActive ? ' active' : ''}`}>
          {formatTime(elapsed)}
        </span>

        {/* Waveform bars */}
        <div className="lv-waveform">
          {Array.from({ length: bars }).map((_, i) => {
            const h = isActive ? 20 + Math.random() * 80 : 8
            return (
              <div
                key={i}
                className={`lv-bar${isActive ? ' active' : ''}`}
                style={isActive ? {
                  height: `${h}%`,
                  animationDelay: `${i * 0.05}s`,
                } : undefined}
              />
            )
          })}
        </div>

        {/* Status text */}
        <p className="lv-status">
          {isListening ? 'Listening…' : isSpeaking ? 'Speaking…' : isThinking ? 'Thinking…' : isListening ? 'Listening…' : 'Tap to speak'}
        </p>

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
            ref={inputRef}
            className="lv-text-input"
            placeholder="Type a message…"
            value={textInput}
            onChange={(e) => onTextInput(e.target.value)}
          />
          <button type="submit" className="lv-text-send" disabled={!textInput.trim() || isThinking || isSpeaking}>
            <Mic size={16} />
          </button>
        </form>
      </div>
    </div>
  )
}
