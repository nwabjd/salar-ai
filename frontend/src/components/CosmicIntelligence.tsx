import { useEffect, useRef, type RefObject } from "react";
import { getParticleBudget } from "./cosmic-state";

export type CosmicIntelligenceProps = {
  scrollRoot: RefObject<HTMLDivElement | null>;
};

type Particle = {
  theta: number;
  phi: number;
  seed: number;
  size: number;
  lane: number;
  color: string;
};

const PALETTE = ["#f65cff", "#9f55ff", "#6de8ff", "#ffbd70", "#ffffff"];

const lerp = (from: number, to: number, amount: number) => from + (to - from) * amount;
const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
const smooth = (value: number) => {
  const t = clamp01(value);
  return t * t * (3 - 2 * t);
};

function seeded(index: number, salt: number) {
  const value = Math.sin(index * 127.1 + salt * 311.7) * 43758.5453;
  return value - Math.floor(value);
}

function createParticles(count: number): Particle[] {
  return Array.from({ length: count }, (_, index) => ({
    theta: seeded(index, 1) * Math.PI * 2,
    phi: Math.acos(1 - 2 * seeded(index, 2)),
    seed: seeded(index, 3),
    size: 0.55 + seeded(index, 4) * 1.8,
    lane: Math.floor(seeded(index, 5) * 5),
    color: PALETTE[Math.floor(seeded(index, 6) * PALETTE.length)],
  }));
}

export default function CosmicIntelligence({ scrollRoot }: CosmicIntelligenceProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const root = scrollRoot.current;
    if (!canvas || !root) return;

    const context = canvas.getContext("2d", { alpha: true });
    if (!context) {
      canvas.classList.add("is-fallback");
      return;
    }

    let width = 1;
    let height = 1;
    let pixelRatio = 1;
    let particles: Particle[] = [];
    let animationFrame = 0;
    let progress = 0;
    let pointerX = 0;
    let pointerY = 0;
    let visible = !document.hidden;
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reducedMotion = motionQuery.matches;

    const updateScroll = () => {
      const range = Math.max(1, root.scrollHeight - root.clientHeight);
      progress = clamp01(root.scrollTop / range);
      if (reducedMotion) draw(performance.now());
    };

    const updatePointer = (event: PointerEvent) => {
      pointerX = event.clientX / Math.max(1, window.innerWidth) - 0.5;
      pointerY = event.clientY / Math.max(1, window.innerHeight) - 0.5;
    };

    const resize = () => {
      width = Math.max(1, window.innerWidth);
      height = Math.max(1, window.innerHeight);
      pixelRatio = Math.min(2.25, Math.max(1, window.devicePixelRatio || 1));
      canvas.width = Math.floor(width * pixelRatio);
      canvas.height = Math.floor(height * pixelRatio);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      particles = createParticles(getParticleBudget({ width, height, dpr: pixelRatio }));
      if (reducedMotion) draw(performance.now());
    };

    const drawCore = (centerX: number, centerY: number, radius: number, time: number) => {
      const breath = reducedMotion ? 1 : 1 + Math.sin(time * 0.0012) * 0.045;
      const glow = context.createRadialGradient(centerX, centerY, 0, centerX, centerY, radius * 1.55 * breath);
      glow.addColorStop(0, "rgba(255,255,255,.96)");
      glow.addColorStop(0.05, "rgba(255,120,255,.88)");
      glow.addColorStop(0.2, "rgba(152,63,255,.38)");
      glow.addColorStop(0.55, "rgba(65,221,255,.12)");
      glow.addColorStop(1, "rgba(5,3,8,0)");
      context.fillStyle = glow;
      context.beginPath();
      context.arc(centerX, centerY, radius * 1.55 * breath, 0, Math.PI * 2);
      context.fill();

      context.strokeStyle = "rgba(255,255,255,.28)";
      context.lineWidth = 0.7;
      for (let ring = 0; ring < 4; ring += 1) {
        context.beginPath();
        context.ellipse(centerX, centerY, radius * (0.55 + ring * 0.24), radius * (0.17 + ring * 0.06), time * 0.00008 + ring * 0.45, 0, Math.PI * 2);
        context.stroke();
      }
    };

    const draw = (time: number) => {
      context.clearRect(0, 0, width, height);
      if (!visible) return;

      const firstMorph = smooth((progress - 0.18) / 0.22);
      const secondMorph = smooth((progress - 0.5) / 0.24);
      const compact = width < 760;
      const centerX = compact ? width * 0.5 : lerp(width * 0.68, width * 0.54, smooth(progress * 1.8));
      const centerY = compact ? height * 0.2 : height * 0.5;
      const scale = Math.min(width, height) * (compact ? 0.26 : 0.39);
      const rotation = reducedMotion ? 0.4 : time * 0.000075;

      context.save();
      context.globalCompositeOperation = "lighter";
      drawCore(centerX, centerY, scale * lerp(0.13, 0.08, secondMorph), time);

      for (let index = 0; index < particles.length; index += 1) {
        const particle = particles[index];
        const theta = particle.theta + rotation * (0.45 + particle.seed);
        const sphereRadius = 0.45 + particle.seed * 0.58;
        const sphereX = Math.cos(theta) * Math.sin(particle.phi) * sphereRadius;
        const sphereY = Math.cos(particle.phi) * sphereRadius;
        const sphereZ = Math.sin(theta) * Math.sin(particle.phi) * sphereRadius;

        const waveX = (particle.seed * 2 - 1) * 1.55;
        const waveEnvelope = 0.22 + Math.pow(Math.cos(waveX * 1.25), 2) * 0.34;
        const waveY = Math.sin(waveX * 9 + particle.theta + (reducedMotion ? 0 : time * 0.0022)) * waveEnvelope;
        const waveZ = Math.cos(waveX * 5 + particle.phi) * 0.36;

        const laneRadius = 0.38 + particle.lane * 0.17;
        const commandAngle = particle.theta * 1.35 + particle.lane * 0.72 + rotation * 0.8;
        const commandX = Math.cos(commandAngle) * laneRadius * 1.22;
        const commandY = Math.sin(commandAngle) * laneRadius * 0.62;
        const commandZ = Math.sin(commandAngle * 1.8 + particle.phi) * 0.42;

        const xToVoice = lerp(sphereX, waveX, firstMorph);
        const yToVoice = lerp(sphereY, waveY, firstMorph);
        const zToVoice = lerp(sphereZ, waveZ, firstMorph);
        const x = lerp(xToVoice, commandX, secondMorph);
        const y = lerp(yToVoice, commandY, secondMorph);
        const z = lerp(zToVoice, commandZ, secondMorph);

        const depth = 2.8 / (2.8 + z);
        const screenX = centerX + (x + pointerX * (0.11 + particle.seed * 0.08)) * scale * depth;
        const screenY = centerY + (y + pointerY * (0.08 + particle.seed * 0.06)) * scale * depth;
        const pointSize = particle.size * depth * (compact ? 0.85 : 1);
        const alpha = 0.32 + (1 - clamp01((z + 1) / 2)) * 0.68;

        context.globalAlpha = alpha;
        context.fillStyle = particle.color;
        context.shadowColor = particle.color;
        context.shadowBlur = pointSize > 1.5 ? 9 : 4;
        context.beginPath();
        context.arc(screenX, screenY, pointSize, 0, Math.PI * 2);
        context.fill();

        if (secondMorph > 0.25 && index % 29 === 0) {
          context.globalAlpha = secondMorph * 0.17;
          context.shadowBlur = 0;
          context.strokeStyle = particle.color;
          context.lineWidth = 0.5;
          context.beginPath();
          context.moveTo(centerX, centerY);
          context.lineTo(screenX, screenY);
          context.stroke();
        }
      }

      context.restore();
      context.globalAlpha = 1;
      context.shadowBlur = 0;
    };

    const tick = (time: number) => {
      draw(time);
      animationFrame = window.requestAnimationFrame(tick);
    };

    const updateMotion = () => {
      reducedMotion = motionQuery.matches;
      window.cancelAnimationFrame(animationFrame);
      if (reducedMotion) draw(performance.now());
      else animationFrame = window.requestAnimationFrame(tick);
    };

    const updateVisibility = () => {
      visible = !document.hidden;
      if (visible && reducedMotion) draw(performance.now());
    };

    resize();
    updateScroll();
    if (reducedMotion) draw(performance.now());
    else animationFrame = window.requestAnimationFrame(tick);

    root.addEventListener("scroll", updateScroll, { passive: true });
    window.addEventListener("pointermove", updatePointer, { passive: true });
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", updateVisibility);
    motionQuery.addEventListener("change", updateMotion);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      root.removeEventListener("scroll", updateScroll);
      window.removeEventListener("pointermove", updatePointer);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", updateVisibility);
      motionQuery.removeEventListener("change", updateMotion);
    };
  }, [scrollRoot]);

  return (
    <div className="cosmic-visual-layer" aria-hidden="true">
      <canvas ref={canvasRef} className="cosmic-intelligence" />
      <div className="cosmic-fallback" />
    </div>
  );
}
