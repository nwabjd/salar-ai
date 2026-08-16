import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

type CoreState = 'idle' | 'listening' | 'thinking' | 'planning' | 'acting' | 'verifying' | 'complete' | 'warning' | 'error';

const CoreConfig: Record<CoreState, { primary: string; secondary: string; speed: number; energy: number }> = {
  idle: { primary: '#C9A56E', secondary: '#D9C09A', speed: 1, energy: 0.5 },
  listening: { primary: '#78A891', secondary: '#2F6E59', speed: 1.5, energy: 0.8 },
  thinking: { primary: '#C9A56E', secondary: '#E7D6B7', speed: 2.5, energy: 1.2 },
  planning: { primary: '#D9C09A', secondary: '#F2E5CC', speed: 2, energy: 1 },
  acting: { primary: '#2F6E59', secondary: '#78A891', speed: 3, energy: 1.5 },
  verifying: { primary: '#E7D6B7', secondary: '#C9A56E', speed: 2, energy: 0.9 },
  complete: { primary: '#2F6E59', secondary: '#78A891', speed: 0.6, energy: 0.4 },
  warning: { primary: '#C58A42', secondary: '#E7D6B7', speed: 2, energy: 1.2 },
  error: { primary: '#B95750', secondary: '#D98B82', speed: 3, energy: 1.5 },
};

export const EnhancedQuantumCore: React.FC<{ state: CoreState }> = ({ state }) => {
  const [rotation, setRotation] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setRotation(r => (r + 0.5 * CoreConfig[state].speed) % 360);
    }, 30);
    return () => clearInterval(interval);
  }, [state]);

  const config = CoreConfig[state];

  return (
    <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
      <svg viewBox="0 0 400 400" className="w-full h-full">
        <defs>
          <radialGradient id="coreGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={config.primary} stopOpacity="0.4" />
            <stop offset="50%" stopColor={config.primary} stopOpacity="0.15" />
            <stop offset="100%" stopColor={config.primary} stopOpacity="0" />
          </radialGradient>
          <radialGradient id="innerGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={config.secondary} stopOpacity="0.8" />
            <stop offset="100%" stopColor={config.primary} stopOpacity="0.2" />
          </radialGradient>
          <linearGradient id="energyLine" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={config.primary} stopOpacity="0" />
            <stop offset="50%" stopColor={config.secondary} stopOpacity="1" />
            <stop offset="100%" stopColor={config.primary} stopOpacity="0" />
          </linearGradient>
          <filter id="softGlow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="strongGlow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Ambient glow */}
        <motion.circle
          cx="200"
          cy="200"
          r="160"
          fill="url(#coreGlow)"
          animate={{
            scale: [1, 1.05 + config.energy * 0.05, 1],
            opacity: [0.6, 1, 0.6],
          }}
          transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        />

        {/* Outer orbital rings — multiple layers */}
        <g style={{ transformOrigin: '200px 200px' }}>
          <motion.circle
            cx="200" cy="200" r="180"
            fill="none"
            stroke={config.primary}
            strokeWidth="0.5"
            opacity="0.3"
            strokeDasharray="4 8"
            animate={{ rotate: 360 }}
            transition={{ duration: 40, repeat: Infinity, ease: 'linear' }}
            style={{ transformOrigin: '200px 200px' }}
          />
        </g>
        <g>
          <motion.circle
            cx="200" cy="200" r="165"
            fill="none"
            stroke={config.secondary}
            strokeWidth="0.8"
            opacity="0.25"
            strokeDasharray="2 12"
            animate={{ rotate: -360 }}
            transition={{ duration: 55, repeat: Infinity, ease: 'linear' }}
            style={{ transformOrigin: '200px 200px' }}
          />
        </g>
        <g>
          <motion.circle
            cx="200" cy="200" r="150"
            fill="none"
            stroke={config.primary}
            strokeWidth="1.2"
            opacity="0.35"
            strokeDasharray="1 6"
            animate={{ rotate: 360 }}
            transition={{ duration: 25, repeat: Infinity, ease: 'linear' }}
            style={{ transformOrigin: '200px 200px' }}
          />
        </g>
        <g>
          <motion.circle
            cx="200" cy="200" r="135"
            fill="none"
            stroke={config.secondary}
            strokeWidth="0.5"
            opacity="0.2"
            animate={{ rotate: -360 }}
            transition={{ duration: 35, repeat: Infinity, ease: 'linear' }}
            style={{ transformOrigin: '200px 200px' }}
          />
        </g>

        {/* Orbital node paths (elliptical) */}
        {[0, 120, 240].map((offset, idx) => (
          <motion.ellipse
            key={idx}
            cx="200" cy="200"
            rx={120} ry={50}
            fill="none"
            stroke={config.primary}
            strokeWidth="0.8"
            opacity="0.25"
            animate={{ rotate: 360 + offset }}
            transition={{ duration: 15 + idx * 3, repeat: Infinity, ease: 'linear' }}
            style={{ transformOrigin: '200px 200px' }}
          />
        ))}

        {/* Orbital particles */}
        {Array.from({ length: 12 }).map((_, i) => {
          const angle = ((i * 30) + rotation) * (Math.PI / 180);
          const radius = 150 + (i % 3) * 12;
          const x = 200 + radius * Math.cos(angle);
          const y = 200 + radius * Math.sin(angle);
          const size = 1.5 + (i % 3) * 0.8;
          return (
            <motion.circle
              key={i}
              cx={x}
              cy={y}
              r={size}
              fill={config.primary}
              filter="url(#softGlow)"
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.1 }}
            />
          );
        })}

        {/* Energy streams flowing outward */}
        {[0, 90, 180, 270].map((angle, i) => {
          const rad = (angle + rotation * 0.5) * (Math.PI / 180);
          const x1 = 200 + 30 * Math.cos(rad);
          const y1 = 200 + 30 * Math.sin(rad);
          const x2 = 200 + 70 * Math.cos(rad);
          const y2 = 200 + 70 * Math.sin(rad);
          return (
            <motion.line
              key={`stream-${i}`}
              x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="url(#energyLine)"
              strokeWidth="1.5"
              opacity="0.6"
              filter="url(#softGlow)"
              animate={{
                strokeDashoffset: [20, 0],
              }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
              strokeDasharray="4 4"
            />
          );
        })}

        {/* Inner rotating ring */}
        <g>
          <motion.circle
            cx="200" cy="200" r="80"
            fill="none"
            stroke={config.primary}
            strokeWidth="1.5"
            opacity="0.4"
            strokeDasharray="8 4"
            animate={{ rotate: -360 }}
            transition={{ duration: 12, repeat: Infinity, ease: 'linear' }}
            style={{ transformOrigin: '200px 200px' }}
          />
        </g>

        {/* Quantum lattice */}
        <g>
          {[0, 60, 120].map((angle, i) => (
            <motion.line
              key={`lattice-${i}`}
              x1="200" y1="200"
              x2={200 + 70 * Math.cos((angle + rotation) * Math.PI / 180)}
              y2={200 + 70 * Math.sin((angle + rotation) * Math.PI / 180)}
              stroke={config.secondary}
              strokeWidth="0.8"
              opacity="0.3"
              style={{ transformOrigin: '200px 200px' }}
            />
          ))}
        </g>

        {/* Concentric pulse rings */}
        {[0, 1, 2].map(i => (
          <motion.circle
            key={`pulse-${i}`}
            cx="200" cy="200"
            r="50"
            fill="none"
            stroke={config.primary}
            strokeWidth="1"
            opacity="0.5"
            initial={{ scale: 1, opacity: 0.5 }}
            animate={{ scale: 1.8, opacity: 0 }}
            transition={{
              duration: 3,
              repeat: Infinity,
              delay: i * 1,
              ease: 'easeOut',
            }}
          />
        ))}

        {/* Central core — multiple layers */}
        <motion.circle
          cx="200" cy="200" r="45"
          fill="none"
          stroke={config.primary}
          strokeWidth="2"
          opacity="0.7"
          filter="url(#strongGlow)"
          animate={{
            scale: [1, 1.03 + config.energy * 0.02, 1],
          }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          style={{ transformOrigin: '200px 200px' }}
        />

        <motion.circle
          cx="200" cy="200" r="35"
          fill="none"
          stroke={config.secondary}
          strokeWidth="1.5"
          opacity="0.5"
          strokeDasharray="6 3"
          animate={{ rotate: 360 }}
          transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
          style={{ transformOrigin: '200px 200px' }}
        />

        {/* Inner energy core */}
        <motion.circle
          cx="200" cy="200" r="22"
          fill="url(#innerGlow)"
          filter="url(#strongGlow)"
          animate={{
            scale: [1, 1.08, 1],
          }}
          transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
          style={{ transformOrigin: '200px 200px' }}
        />

        {/* Absolute center */}
        <motion.circle
          cx="200" cy="200" r="8"
          fill={config.secondary}
          filter="url(#strongGlow)"
          animate={{
            opacity: [0.8, 1, 0.8],
          }}
          transition={{ duration: 0.8, repeat: Infinity }}
        />

        {/* Data packets orbiting */}
        {Array.from({ length: 6 }).map((_, i) => {
          const angle = ((i * 60) + rotation * 2) * (Math.PI / 180);
          const orbitRadius = 60 + (i % 2) * 15;
          const x = 200 + orbitRadius * Math.cos(angle);
          const y = 200 + orbitRadius * Math.sin(angle);
          return (
            <motion.circle
              key={`packet-${i}`}
              cx={x} cy={y} r="2"
              fill={config.secondary}
              filter="url(#softGlow)"
              animate={{ opacity: [0.4, 1, 0.4] }}
              transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
            />
          );
        })}
      </svg>

      {/* State badge overlay */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2">
        <motion.div
          className="flex items-center gap-2 px-4 py-1.5 rounded-full backdrop-blur-md"
          style={{
            background: 'rgba(20, 20, 20, 0.6)',
            border: `1px solid ${config.primary}40`,
          }}
          animate={{ opacity: [0.85, 1, 0.85] }}
          transition={{ duration: 2, repeat: Infinity }}
        >
          <motion.span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: config.primary }}
            animate={{ scale: [1, 1.6, 1], opacity: [1, 0.6, 1] }}
            transition={{ duration: 1.2, repeat: Infinity }}
          />
          <span
            className="text-[10px] font-semibold uppercase tracking-[0.15em]"
            style={{ color: config.secondary }}
          >
            {state}
          </span>
        </motion.div>
      </div>
    </div>
  );
};
