import React from 'react'

interface SwirlingProps {
  size?: number
  className?: string
}

export function Swirling({ size = 32, className = '' }: SwirlingProps) {
  const r = size / 2 - 2
  const cx = size / 2
  const cy = size / 2

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={`swirling ${className}`}
      style={{ animation: 'swirl-spin 1.2s linear infinite' }}
    >
      <defs>
        <linearGradient id="swirlGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#a78bfa" stopOpacity="1" />
          <stop offset="50%" stopColor="#7c3aed" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#c084fc" stopOpacity="0.4" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((i) => {
        const offset = i * 0.25
        return (
          <circle
            key={i}
            cx={cx}
            cy={cy}
            r={r * (0.3 + i * 0.18)}
            fill="none"
            stroke="url(#swirlGrad)"
            strokeWidth={1.5 - i * 0.2}
            strokeDasharray={`${Math.PI * r * (0.3 + i * 0.18) * 0.6} ${Math.PI * r * (0.3 + i * 0.18) * 1.4}`}
            strokeLinecap="round"
            opacity={1 - i * 0.2}
            style={{
              transformOrigin: 'center',
              animation: `swirl-orbit ${0.8 + i * 0.3}s ease-in-out infinite`,
              animationDirection: i % 2 === 0 ? 'normal' : 'reverse',
            }}
          />
        )
      })}
      <style>{`
        @keyframes swirl-spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
        @keyframes swirl-orbit{0%,100%{stroke-dashoffset:0;opacity:.6}50%{stroke-dashoffset:40;opacity:1}}
      `}</style>
    </svg>
  )
}
