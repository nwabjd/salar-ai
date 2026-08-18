import React from 'react'

type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking'

interface LiveOrbProps {
  size?: number
  state?: OrbState
  micVolume?: number
  aiVolume?: number
  className?: string
  onClick?: () => void
}

export function LiveOrb({
  size = 200,
  state = 'idle',
  micVolume = 0,
  aiVolume = 0,
  className = '',
  onClick,
}: LiveOrbProps) {
  const totalVolume = Math.max(micVolume, aiVolume)
  const isActive = state !== 'idle'
  const isSpeaking = state === 'speaking'
  const isListening = state === 'listening'
  const isThinking = state === 'thinking'

  const filterIntensity = isActive
    ? `drop-shadow(0 0 ${8 + totalVolume * 20}px #ff3e1c${isListening ? 'cc' : '55'}) drop-shadow(0 0 ${8 + totalVolume * 20}px #1c8cff${isSpeaking ? 'cc' : '55'})`
    : 'drop-shadow(0 0 6px #ff3e1c88) drop-shadow(0 0 6px #1c8cff88)'

  const animDuration = isSpeaking ? '3s' : isThinking ? '4s' : '6s'

  return (
    <div
      className={`orb-container ${className}`}
      style={{
        width: size,
        height: size,
        filter: filterIntensity,
        animationDuration: animDuration,
      }}
      onClick={onClick}
      role="button"
      aria-label={isActive ? 'Stop live voice' : 'Start live voice'}
    >
      <div
        className="orb"
        style={{
          width: isActive ? 220 : 200,
          animation: isActive ? `rotate ${animDuration} infinite` : 'none',
        }}
      >
        <div
          className="orb-inner"
          style={{
            animationDuration: animDuration,
            background: isListening ? '#00e5a0' : isSpeaking ? '#a855f7' : isThinking ? '#f59e0b' : '#ff3e1c',
          }}
        />
        <div
          className="orb-inner orb-inner-blue"
          style={{
            animationDuration: isSpeaking ? '4s' : '8s',
            background: isSpeaking ? '#c084fc' : '#1c8cff',
          }}
        />
      </div>

    </div>
  )
}
