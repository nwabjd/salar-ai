import React, { useEffect, useState, useRef } from 'react';
import { motion } from 'framer-motion';

export const LiveMetric: React.FC<{
  label: string;
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  format?: (v: number) => string;
  trend?: number;
  icon?: React.ElementType;
  dark?: boolean;
}> = ({
  label,
  value,
  prefix = '',
  suffix = '',
  decimals = 1,
  format,
  trend,
  icon: Icon,
  dark = false,
}) => {
  const [displayValue, setDisplayValue] = useState(value);
  const prevRef = useRef(value);

  useEffect(() => {
    const start = prevRef.current;
    const duration = 800;
    const startTime = Date.now();
    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (value - start) * eased;
      setDisplayValue(current);
      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        prevRef.current = value;
      }
    };
    animate();
  }, [value]);

  const displayText = format ? format(displayValue) : displayValue.toFixed(decimals);

  return (
    <motion.div
      className={`p-4 rounded-xl relative overflow-hidden ${dark ? 'bg-white/5' : 'bg-white/60'}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{
        scale: 1.02,
        transition: { duration: 0.2 },
      }}
    >
      {/* Shimmer on hover */}
      <motion.div
        className="absolute inset-0 opacity-0 hover:opacity-100 transition-opacity"
        style={{
          background: 'linear-gradient(135deg, rgba(201, 165, 110, 0.05) 0%, rgba(217, 192, 154, 0.08) 100%)',
        }}
      />
      <div className="flex items-center justify-between mb-2 relative z-10">
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${dark ? 'text-white/60' : 'text-gray-500'}`}>
          {label}
        </span>
        {Icon && (
          <motion.div
            animate={{ rotate: [0, 5, 0] }}
            transition={{ duration: 3, repeat: Infinity }}
          >
            <Icon className={`w-3.5 h-3.5 ${dark ? 'text-white/40' : 'text-gray-400'}`} />
          </motion.div>
        )}
      </div>
      <div className="flex items-end justify-between relative z-10">
        <motion.div
          className="text-xl font-bold"
          style={{ color: dark ? '#F5F2EC' : '#151515' }}
          key={displayText}
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          {prefix}{displayText}{suffix}
        </motion.div>
        {trend !== undefined && (
          <motion.span
            className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-md ${
              trend >= 0 ? 'bg-green-500/15 text-green-600' : 'bg-red-500/15 text-red-600'
            }`}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.2 }}
          >
            {trend >= 0 ? '▲' : '▼'} {Math.abs(trend)}%
          </motion.span>
        )}
      </div>
      {/* Bottom accent line */}
      <motion.div
        className="absolute bottom-0 left-0 h-[2px] w-full"
        style={{
          background: 'linear-gradient(90deg, transparent, var(--quantum-gold), transparent)',
        }}
        animate={{ opacity: [0, 0.5, 0] }}
        transition={{ duration: 2, repeat: Infinity }}
      />
    </motion.div>
  );
};

// Typing indicator for command console
export const TypingIndicator: React.FC<{ text: string; onComplete?: () => void }> = ({ text, onComplete }) => {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    setDisplayed('');
    setDone(false);
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(interval);
        setDone(true);
        onComplete?.();
      }
    }, 30 + Math.random() * 20);
    return () => clearInterval(interval);
  }, [text, onComplete]);

  return (
    <span>
      {displayed}
      {!done && <span className="blinking-cursor" />}
    </span>
  );
};
