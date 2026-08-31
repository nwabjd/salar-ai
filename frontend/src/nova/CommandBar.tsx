import React, { useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic2, Send, Sparkles, Paperclip, PenLine, FileText, X } from 'lucide-react'

/* ============================================================
   UNIVERSAL COMMAND BAR — text/voice/mission entry point.
   Expanded with:
     • File & document attachments (paperclip) + chips
     • Signature / sign icon (PenLine) for signing documents
   ============================================================ */

interface CommandBarProps {
  placeholder?: string
  onSend?: (text: string, files?: File[]) => void
  onVoice?: () => void
  onAttach?: (files: File[]) => void
  onSign?: () => void
  disabled?: boolean
}

const MAX_ATTACHMENTS = 6

export default function CommandBar({
  placeholder = 'Ask Salaar anything or give it a mission…',
  onSend,
  onVoice,
  onAttach,
  onSign,
  disabled,
}: CommandBarProps) {
  const [focused, setFocused] = useState(false)
  const [value, setValue] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const inputRef = useRef<HTMLInputElement | null>(null)
  const fileRef = useRef<HTMLInputElement | null>(null)

  const submit = () => {
    if ((!value.trim() && files.length === 0) || disabled) return
    onSend?.(value.trim(), files)
    setValue('')
    setFiles([])
  }

  const pickFiles = (list: FileList | null) => {
    if (!list) return
    const picked = Array.from(list).slice(0, MAX_ATTACHMENTS - files.length)
    const next = [...files, ...picked]
    setFiles(next)
    onAttach?.(picked)
  }

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const iconBtn: React.CSSProperties = {
    width: 38,
    height: 38,
    borderRadius: 12,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'transparent',
    border: '1px solid transparent',
    color: 'var(--nova-white)',
    cursor: 'pointer',
    flexShrink: 0,
    transition: 'background .2s, border-color .2s, color .2s',
  }

  return (
    <div style={{ width: 'min(640px, 88vw)', display: 'flex', flexDirection: 'column', gap: 6 }}>
      <AnimatePresence>
        {files.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 8, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -6, height: 0 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 6,
              overflow: 'hidden',
            }}
          >
            {files.map((f, i) => (
              <motion.div
                key={`${f.name}-${i}`}
                layout
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '5px 6px 5px 10px',
                  borderRadius: 10,
                  background: 'var(--nova-intel-glass)',
                  border: '1px solid var(--nova-line-cyan)',
                  boxShadow: 'var(--nova-glow-cyan)',
                  color: 'var(--nova-white)',
                  fontSize: 12.5,
                  maxWidth: 220,
                }}
              >
                <FileText size={13} style={{ color: 'var(--nova-cyan)', flexShrink: 0 }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.name}
                </span>
                <button
                  onClick={() => removeFile(i)}
                  aria-label={`Remove ${f.name}`}
                  style={{
                    background: 'transparent', border: 'none', cursor: 'pointer',
                    color: 'var(--nova-white)', opacity: 0.7, display: 'flex', padding: 2,
                  }}
                >
                  <X size={12} />
                </button>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        className="nova-command-bar"
        animate={{ scale: focused ? 1.02 : 1 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '10px 10px 10px 12px',
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
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".pdf,.doc,.docx,.txt,.md,.png,.jpg,.jpeg,.webp,.xlsx,.csv,.ppt,.pptx"
          style={{ display: 'none' }}
          onChange={e => { pickFiles(e.target.files); e.target.value = '' }}
        />

        {/* Paperclip — attach files & documents */}
        <motion.button
          onClick={() => fileRef.current?.click()}
          whileHover={{ scale: 1.08, rotate: 8 }}
          whileTap={{ scale: 0.9 }}
          aria-label="Attach files"
          title="Attach files or documents"
          style={iconBtn}
        >
          <Paperclip size={17} strokeWidth={1.8} />
        </motion.button>

        {/* Signature icon — sign documents */}
        <motion.button
          onClick={onSign}
          whileHover={{ scale: 1.08, rotate: -6 }}
          whileTap={{ scale: 0.9 }}
          aria-label="Sign document"
          title="Sign a document"
          style={iconBtn}
        >
          <PenLine size={17} strokeWidth={1.8} />
        </motion.button>

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
          whileTap={{ scale: 0.92 }}
          aria-label="Voice input"
          title="Voice"
          style={iconBtn}
        >
          <Mic2 size={17} strokeWidth={1.8} />
        </motion.button>

        <motion.button
          onClick={submit}
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.9 }}
          disabled={disabled || (!value.trim() && files.length === 0)}
          aria-label="Send"
          title="Send"
          style={{
            width: 40,
            height: 40,
            borderRadius: 13,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: 'none',
            cursor: 'pointer',
            flexShrink: 0,
            background: !value.trim() && files.length === 0 ? 'var(--nova-line)' : 'linear-gradient(135deg, var(--nova-cyan), #6a7bff)',
            color: '#051018',
            boxShadow: '0 6px 18px rgba(0,0,0,.28)',
          }}
        >
          <Send size={16} strokeWidth={2} />
        </motion.button>
      </motion.div>
    </div>
  )
}