import React, { useRef, useEffect } from 'react'

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
  size = 320,
  state = 'idle',
  micVolume = 0,
  aiVolume = 0,
  className = '',
  onClick,
}: LiveOrbProps) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    videoRef.current?.play().catch(() => {})
  }, [])

  const orbClass = `orb-wrap ${state === 'thinking' ? 'dim-low' : state === 'speaking' ? 'dim-mid' : 'dim-full'}`

  return (
    <div
      className={`orb-container ${className}`}
      style={{ width: size, height: size }}
      onClick={onClick}
      role="button"
      aria-label={state !== 'idle' ? 'Stop live voice' : 'Start live voice'}
    >
      <div className={orbClass}>
        <video ref={videoRef} autoPlay loop muted playsInline preload="auto">
          <source src="/assets/orb.mp4" type="video/mp4" />
        </video>
      </div>
    </div>
  )
}
