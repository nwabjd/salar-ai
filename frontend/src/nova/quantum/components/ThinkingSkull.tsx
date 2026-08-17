import React, { useMemo } from 'react';
import { motion } from 'framer-motion';

export type SkullState = 'idle' | 'typing' | 'generating';

const EQUATIONS = [
  'E=mc²', '∑xᵢ', '∫f(x)dx', '∇·F', 'λ=h/p',
  'P(A|B)', '∂ψ/∂t', 'ΔxΔp≥ℏ', 'ψ=eⁱᵏˣ', 'F=ma',
  'S=k·lnW', 'iℏ∂ψ', '∮B·dl', '∂²u/∂t²', '∇×E',
  'Rμν−½gμνR', 'σ=√Var', 'dx/dt', 'Σpᵢvᵢ', 'log₂N',
  '0xFF', '{}', '[]', '=>', '::', '⊥', '◊', '∞',
];

const PARTICLE_COUNT = 8;

function makeParticle(i: number) {
  const angle = (i / PARTICLE_COUNT) * Math.PI * 2;
  return { angle, size: 1 + Math.random() * 1.5, speed: 8 + Math.random() * 6 };
}

interface ThinkingSkullProps {
  state: SkullState;
  size?: number;
  className?: string;
}

export const ThinkingSkull: React.FC<ThinkingSkullProps> = ({ state, size = 48, className = '' }) => {
  const active = state !== 'idle';

  const orbitingEqs = useMemo(() => {
    const shuffled = [...EQUATIONS].sort(() => Math.random() - 0.5);
    return shuffled.slice(0, active ? 8 : 0);
  }, [state === 'generating']);

  const particles = useMemo(() =>
    Array.from({ length: PARTICLE_COUNT }, (_, i) => makeParticle(i)),
  []);

  const glowColor = state === 'generating' ? '#C9A56E' : state === 'typing' ? '#D9C09A' : '#88818f';
  const glowIntensity = state === 'generating' ? 18 : state === 'typing' ? 10 : 0;

  return (
    <div className={`relative flex-shrink-0 ${className}`} style={{ width: size, height: size }}>
      {/* Glow backdrop */}
      <motion.div
        className="absolute rounded-full"
        style={{
          inset: -glowIntensity * 0.6,
          background: `radial-gradient(circle, ${glowColor}30 0%, transparent 70%)`,
        }}
        animate={{
          opacity: active ? [0.5, 1, 0.5] : 0,
          scale: active ? [0.95, 1.1, 0.95] : 0.8,
        }}
        transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Skull SVG */}
      <motion.svg
        viewBox="0 0 100 100"
        width={size}
        height={size}
        className="relative z-10"
        style={{ filter: `drop-shadow(0 0 ${glowIntensity}px ${glowColor}90)` }}
      >
        <defs>
          <linearGradient id="skullGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#C9A56E" />
            <stop offset="100%" stopColor="#D9C09A" />
          </linearGradient>
          <filter id="skullGlow">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Cranium */}
        <motion.path
          d="M50 8 C24 8 12 28 12 48 C12 62 20 72 30 76 L30 82 C30 88 36 94 50 94 C64 94 70 88 70 82 L70 76 C80 72 88 62 88 48 C88 28 76 8 50 8 Z"
          fill="none"
          stroke="url(#skullGrad)"
          strokeWidth="2.2"
          filter="url(#skullGlow)"
          animate={active ? { strokeWidth: [2.2, 2.8, 2.2] } : {}}
          transition={{ duration: 2, repeat: Infinity }}
        />

        {/* Brow ridge */}
        <path d="M28 36 Q38 30 50 33 Q62 30 72 36" fill="none" stroke="#C9A56E" strokeWidth="1.2" opacity="0.5" />

        {/* Left eye socket */}
        <motion.ellipse
          cx="37" cy="44" rx="10" ry="9"
          fill="none"
          stroke="url(#skullGrad)"
          strokeWidth="1.8"
          filter="url(#skullGlow)"
          animate={active ? { ry: [9, 10, 9] } : {}}
          transition={{ duration: 1.5, repeat: Infinity }}
        />
        {/* Left pupil */}
        <motion.circle
          cx="37" cy="44" r="3"
          fill="#C9A56E"
          animate={active
            ? { opacity: [0.6, 1, 0.6], scale: [1, 1.3, 1] }
            : { opacity: 0.3 }}
          transition={{ duration: 1.2, repeat: Infinity }}
        />

        {/* Right eye socket */}
        <motion.ellipse
          cx="63" cy="44" rx="10" ry="9"
          fill="none"
          stroke="url(#skullGrad)"
          strokeWidth="1.8"
          filter="url(#skullGlow)"
          animate={active ? { ry: [9, 10, 9] } : {}}
          transition={{ duration: 1.5, repeat: Infinity, delay: 0.2 }}
        />
        {/* Right pupil */}
        <motion.circle
          cx="63" cy="44" r="3"
          fill="#C9A56E"
          animate={active
            ? { opacity: [0.6, 1, 0.6], scale: [1, 1.3, 1] }
            : { opacity: 0.3 }}
          transition={{ duration: 1.2, repeat: Infinity, delay: 0.3 }}
        />

        {/* Nasal cavity */}
        <path d="M46 56 L50 64 L54 56" fill="none" stroke="#C9A56E" strokeWidth="1.4" strokeLinecap="round" />

        {/* Cheekbones */}
        <path d="M22 50 Q26 58 32 56" fill="none" stroke="#D9C09A" strokeWidth="0.8" opacity="0.4" />
        <path d="M78 50 Q74 58 68 56" fill="none" stroke="#D9C09A" strokeWidth="0.8" opacity="0.4" />

        {/* Jaw line */}
        <path d="M30 76 Q30 86 50 88 Q70 86 70 76" fill="none" stroke="#C9A56E" strokeWidth="1" opacity="0.5" />

        {/* Teeth */}
        {[38, 44, 50, 56, 62].map((x, i) => (
          <motion.line
            key={i}
            x1={x} y1="76" x2={x} y2={i === 2 ? 84 : 82}
            stroke="#D9C09A"
            strokeWidth="1.2"
            strokeLinecap="round"
            animate={active && state === 'generating' ? { y2: [i === 2 ? 84 : 82, i === 2 ? 86 : 84, i === 2 ? 84 : 82] } : {}}
            transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.1 }}
          />
        ))}

        {/* Temporal lines */}
        <path d="M18 38 Q16 48 18 58" fill="none" stroke="#D9C09A" strokeWidth="0.6" opacity="0.3" />
        <path d="M82 38 Q84 48 82 58" fill="none" stroke="#D9C09A" strokeWidth="0.6" opacity="0.3" />
      </motion.svg>

      {/* Floating equations */}
      {active && orbitingEqs.map((eq, i) => {
        const total = orbitingEqs.length;
        const baseAngle = (i / total) * Math.PI * 2;
        const radius = size * 0.75;
        const duration = state === 'generating' ? 3 : 5;
        const isEven = i % 2 === 0;

        return (
          <motion.span
            key={`${eq}-${i}`}
            className="absolute pointer-events-none select-none whitespace-nowrap"
            style={{
              fontSize: '7px',
              fontFamily: 'monospace',
              fontWeight: 700,
              color: i % 3 === 0 ? '#C9A56E' : i % 3 === 1 ? '#D9C09A' : '#78A891',
              left: '50%',
              top: '50%',
              textShadow: `0 0 6px ${i % 3 === 0 ? '#C9A56E' : '#D9C09A'}40`,
            }}
            initial={{ x: 0, y: 0, opacity: 0, scale: 0.5 }}
            animate={{
              x: [
                Math.cos(baseAngle) * radius * 0.3,
                Math.cos(baseAngle + (isEven ? 1.2 : -1.2)) * radius,
                Math.cos(baseAngle + (isEven ? 2.4 : -2.4)) * radius * 0.3,
              ],
              y: [
                Math.sin(baseAngle) * radius * 0.3,
                Math.sin(baseAngle + (isEven ? 1.2 : -1.2)) * radius,
                Math.sin(baseAngle + (isEven ? 2.4 : -2.4)) * radius * 0.3,
              ],
              opacity: [0, 0.85, 0],
              scale: [0.5, 1, 0.5],
            }}
            transition={{
              duration,
              repeat: Infinity,
              delay: i * (duration / total),
              ease: 'easeInOut',
            }}
          >
            {eq}
          </motion.span>
        );
      })}

      {/* Orbiting particles */}
      {active && particles.map((p, i) => {
        const r = size * 0.6;
        const dur = p.speed;
        return (
          <motion.span
            className="absolute rounded-full"
            style={{
              width: p.size,
              height: p.size,
              background: i % 2 === 0 ? '#C9A56E' : '#78A891',
              left: '50%',
              top: '50%',
              marginLeft: -p.size / 2,
              marginTop: -p.size / 2,
            }}
            animate={{
              x: [Math.cos(p.angle) * r * 0.4, Math.cos(p.angle + Math.PI) * r, Math.cos(p.angle + Math.PI * 2) * r * 0.4],
              y: [Math.sin(p.angle) * r * 0.4, Math.sin(p.angle + Math.PI) * r, Math.sin(p.angle + Math.PI * 2) * r * 0.4],
              opacity: [0, 0.9, 0],
            }}
            transition={{ duration: dur, repeat: Infinity, delay: i * 0.4, ease: 'linear' }}
          />
        );
      })}
    </div>
  );
};
