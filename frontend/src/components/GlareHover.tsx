import React, { useRef, useCallback } from 'react';

interface GlareHoverProps {
  children: React.ReactNode;
  className?: string;
  glareColor?: string;
  glareOpacity?: number;
  duration?: number;
}

export function GlareHover({
  children,
  className = '',
  glareColor = '#fff',
  glareOpacity = 0.18,
  duration = 600,
}: GlareHoverProps) {
  const ref = useRef<HTMLDivElement>(null);
  const animRef = useRef<number | null>(null);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const el = ref.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      el.style.setProperty('--glare-x', `${x}px`);
      el.style.setProperty('--glare-y', `${y}px`);
      el.style.setProperty('--glare-opacity', `${glareOpacity}`);
      el.style.setProperty('--glare-duration', `${duration}ms`);
    },
    [glareOpacity, duration],
  );

  const handleMouseLeave = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    el.style.setProperty('--glare-opacity', '0');
  }, []);

  return (
    <div
      ref={ref}
      className={`glare-hover-wrap ${className}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {children}
    </div>
  );
}
