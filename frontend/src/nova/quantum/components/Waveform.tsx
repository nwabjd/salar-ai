import React, { useEffect, useState } from 'react';

export const Waveform: React.FC<{ active: boolean; barCount?: number; height?: number; color?: string }> = ({
  active,
  barCount = 20,
  height = 24,
  color = 'var(--quantum-gold)',
}) => {
  const [bars, setBars] = useState<number[]>(Array(barCount).fill(0.3));

  useEffect(() => {
    if (!active) {
      setBars(Array(barCount).fill(0.2));
      return;
    }
    const interval = setInterval(() => {
      setBars(
        Array.from({ length: barCount }, () => {
          const base = 0.3;
          const random = Math.random() * 0.7;
          const wave = Math.sin(Date.now() * 0.01) * 0.15;
          return Math.max(0.15, Math.min(1, base + random + wave));
        })
      );
    }, 80);
    return () => clearInterval(interval);
  }, [active, barCount]);

  return (
    <div className="flex items-center justify-center gap-[2px]" style={{ height }}>
      {bars.map((bar, i) => (
        <div
          key={i}
          className="rounded-full"
          style={{
            width: 2,
            height: `${bar * 100}%`,
            background: active
              ? `linear-gradient(180deg, var(--gold-highlight), ${color})`
              : 'rgba(140, 130, 120, 0.3)',
            transition: 'height 0.08s ease',
            boxShadow: active ? `0 0 4px ${color}` : 'none',
          }}
        />
      ))}
    </div>
  );
};
