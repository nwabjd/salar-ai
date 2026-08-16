import React, { useEffect, useRef } from 'react';

export const AmbientBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    let particles: {
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      alpha: number;
      pulse: number;
    }[] = [];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // Initialize particles
    const particleCount = 40;
    particles = Array.from({ length: particleCount }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.15,
      vy: (Math.random() - 0.5) * 0.15,
      size: Math.random() * 2 + 1,
      alpha: Math.random() * 0.4 + 0.1,
      pulse: Math.random() * Math.PI * 2,
    }));

    const animate = () => {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw connection lines between nearby particles
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const p1 = particles[i];
          const p2 = particles[j];
          const dx = p1.x - p2.x;
          const dy = p1.y - p2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < 220) {
            const alpha = (1 - dist / 220) * 0.12;
            ctx.beginPath();
            ctx.strokeStyle = `rgba(201, 165, 110, ${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }

      // Update and draw particles
      particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        p.pulse += 0.02;

        // Mouse interaction — subtle repulsion
        const dx = p.x - mouseRef.current.x;
        const dy = p.y - mouseRef.current.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150 && dist > 0) {
          p.vx += (dx / dist) * 0.02;
          p.vy += (dy / dist) * 0.02;
        }

        // Damping
        p.vx *= 0.99;
        p.vy *= 0.99;

        // Wrap
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        const pulseAlpha = p.alpha * (0.7 + Math.sin(p.pulse) * 0.3);
        const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 4);
        gradient.addColorStop(0, `rgba(201, 165, 110, ${pulseAlpha})`);
        gradient.addColorStop(1, 'rgba(201, 165, 110, 0)');

        ctx.beginPath();
        ctx.fillStyle = gradient;
        ctx.arc(p.x, p.y, p.size * 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.beginPath();
        ctx.fillStyle = `rgba(242, 229, 204, ${pulseAlpha * 1.5})`;
        ctx.arc(p.x, p.y, p.size * 0.6, 0, Math.PI * 2);
        ctx.fill();
      });

      animationId = requestAnimationFrame(animate);
    };

    animate();

    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current = { x: e.clientX, y: e.clientY };
    };
    window.addEventListener('mousemove', handleMouseMove);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <div className="fixed inset-0 pointer-events-none" style={{ zIndex: 0 }}>
      <canvas ref={canvasRef} className="w-full h-full opacity-60" />
      {/* Atmospheric radial glows */}
      <div
        className="absolute top-[-20%] left-[-10%] w-[70%] h-[70%] rounded-full glow-breathe"
        style={{
          background: 'radial-gradient(circle, rgba(201, 165, 110, 0.08) 0%, transparent 70%)',
          filter: 'blur(40px)',
        }}
      />
      <div
        className="absolute bottom-[-20%] right-[-10%] w-[70%] h-[70%] rounded-full glow-breathe"
        style={{
          background: 'radial-gradient(circle, rgba(217, 192, 154, 0.06) 0%, transparent 70%)',
          filter: 'blur(40px)',
          animationDelay: '1.5s',
        }}
      />
      <div
        className="absolute top-[40%] right-[20%] w-[40%] h-[40%] rounded-full glow-breathe"
        style={{
          background: 'radial-gradient(circle, rgba(120, 168, 145, 0.04) 0%, transparent 70%)',
          filter: 'blur(30px)',
          animationDelay: '0.7s',
        }}
      />
      {/* Subtle topographic rings */}
      <svg className="absolute inset-0 w-full h-full opacity-[0.035]" viewBox="0 0 1200 800">
        {[0, 1, 2, 3, 4].map(i => (
          <ellipse
            key={i}
            cx="600"
            cy="400"
            rx={200 + i * 120}
            ry={150 + i * 90}
            fill="none"
            stroke="var(--quantum-gold)"
            strokeWidth="1"
            strokeDasharray="2 4"
          />
        ))}
      </svg>
    </div>
  );
};
