import React, { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Mic2, Plus, Send, Sparkles } from 'lucide-react'

/* ============================================================
   UNIVERSAL COMMAND BAR — text/voice/mission entry point.
   Expands into a floating surface when focused.
   ============================================================ */

interface CommandBarProps {
  placeholder?: string
  onSend?: (text: string) => void
  onVoice?: () => void
  onAttach?: () => void
  disabled?: boolean
}

export default function CommandBar({
  placeholder = 'Ask Salaar anything or give it a mission…',
  onSend,
  onVoice,
  onAttach,
  disabled,
}: CommandBarProps) {
  const [focused, setFocused] = useState(false)
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)

  const submit = () => {
    if (!value.trim() || disabled) return
    onSend?.(value.trim())
    setValue('')
  }

  return (
    <motion.div
      className="nova-command-bar"
      animate={{ scale: focused ? 1.02 : 1 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      style={{
        width: 'min(640px, 88vw)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 10px 10px 14px',
        borderRadius: 18,
        background: focused
          ? 'var(--nova-intel-glass)'
          : 'var(--nova-glass)',
        WebkitBackdropFilter: 'blur(28px) saturate(150%)',
        backdropFilter: 'blur(28px) saturate(150%)',
        border: focused ? '1px solid var(--nova-line-cyan)' : '1px solid var(--nova-line)',
        boxShadow: focused ? 'var(--nova-glow-cyan)' : '0 16px 40px rgba(0,0,0,.3)',
        transition: 'background .25s, border-color .25s, box-shadow .35s',
      }}
    >
      <button
        onClick={onAttach}
        aria-label="Add attachment"
        style={iconBtn}
      >
        <Plus size={18} strokeWidth={1.8}/>
      </button>

      <input
        ref={inputRef}
        value={value}
        onChange={e => setValue(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onKeyDown={e => { if (e.key === 'Enter') submit() }}
        placeholder={placeholder}
        disabled={disabled}
        aria-label="Command"
        style={{
          flex: 1,
          background: 'transparent',
          border: 'none',
          outline: 'none',
          color: 'var(--nova-white)',
          fontSize: 15,
          letterSpacing: '.01em',
        }}
      />

      <motion.button
        onClick={onVoice}
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.94 }}
        aria-label="Voice"
        style={{ ...iconBtn, color: 'var(--nova-cyan)' }}
      >
        <Mic2 size={18} strokeWidth={1.8}/>
      </motion.button>

      {value.trim() && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          onClick={submit}
          whileTap={{ scale: 0.92 }}
          aria-label="Send"
          style={{
            ...iconBtn,
            background: 'linear-gradient(135deg, rgba(96,239,255,.2), rgba(168,121,255,.2))',
            border: '1px solid var(--nova-line-cyan)',
            color: 'var(--nova-white)',
          }}
        >
          <Send size={16} strokeWidth={1.8}/>
        </motion.button>
      )}
    </motion.div>
  )
}

const iconBtn: React.CSSProperties = {
  display: 'grid',
  placeItems: 'center',
  width: 36,
  height: 36,
  borderRadius: 12,
  background: 'transparent',
  border: '1px solid var(--nova-line)',
  color: 'var(--nova-lunar)',
  cursor: 'pointer',
  flexShrink: 0,
}
