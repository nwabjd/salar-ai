import React, { useCallback, useRef, useState } from 'react'
import { Paperclip, Send, X, ChevronDown, Sparkles, Zap, Brain, Mic2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAutoResizeTextarea } from '../hooks/use-auto-resize-textarea'
import { Swirling } from './Swirling'

interface PromptInputProps {
  onSubmit: (message: string, meta: { model: string; effort: string; attachments: File[] }) => void
  onLive?: () => void
  busy?: boolean
  placeholder?: string
  className?: string
}

const MODELS = [
  { id: 'auto', label: 'Auto', icon: <Sparkles size={14} /> },
  { id: 'flash', label: 'Flash', icon: <Zap size={14} /> },
  { id: 'pro', label: 'Pro', icon: <Brain size={14} /> },
]

const EFFORTS = ['Low', 'Medium', 'High']

export default function PromptInput({ onSubmit, onLive, busy = false, placeholder = 'Ask anything…', className = '' }: PromptInputProps) {
  const [value, setValue] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [isFocused, setIsFocused] = useState(false)
  const [model, setModel] = useState('auto')
  const [effort, setEffort] = useState('Medium')
  const [showModelMenu, setShowModelMenu] = useState(false)
  const [showEffortMenu, setShowEffortMenu] = useState(false)
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 52, maxHeight: 200 })
  const fileInputRef = useRef<HTMLInputElement>(null)
  const modelRef = useRef<HTMLDivElement>(null)
  const effortRef = useRef<HTMLDivElement>(null)

  const currentModel = MODELS.find((m) => m.id === model) || MODELS[0]

  const handleSubmit = useCallback(() => {
    if (!value.trim() && files.length === 0) return
    onSubmit(value, { model, effort, attachments: files })
    setValue('')
    setFiles([])
    adjustHeight(true)
  }, [value, files, model, effort, onSubmit, adjustHeight])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setFiles((prev) => [...prev, ...Array.from(e.target.files || [])])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // Close menus on outside click
  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      const t = e.target as Node
      if (modelRef.current && !modelRef.current.contains(t)) setShowModelMenu(false)
      if (effortRef.current && !effortRef.current.contains(t)) setShowEffortMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className={`pi-wrap ${className}`}>
      <div className={`pi-box${isFocused ? ' focused' : ''}`} onClick={() => textareaRef.current?.focus()}>
        {/* File chips */}
        <AnimatePresence>
          {files.length > 0 && (
            <motion.div className="pi-files" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
              {files.map((file, i) => (
                <motion.div key={`${file.name}-${i}`} className="pi-file-chip" initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }}>
                  <span>{file.name.length > 18 ? file.name.slice(0, 15) + '…' : file.name}</span>
                  <button className="pi-file-x" onClick={(e) => { e.stopPropagation(); setFiles((prev) => prev.filter((_, j) => j !== i)) }}><X size={10} /></button>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Textarea */}
        <div className="pi-textarea-wrap">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => { setValue(e.target.value); adjustHeight() }}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={placeholder}
            className="pi-textarea"
            rows={1}
          />
        </div>

        {/* Bottom toolbar */}
        <div className="pi-toolbar">
          <div className="pi-left">
            <button className="pi-icon-btn" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }} title="Attach files"><Paperclip size={16} /></button>
            <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileChange} />

            {/* Model selector */}
            <div className="pi-select" ref={modelRef}>
              <button className="pi-select-btn" onClick={(e) => { e.stopPropagation(); setShowModelMenu((v) => !v); setShowEffortMenu(false) }}>
                {currentModel.icon}<span>{currentModel.label}</span><ChevronDown size={12} />
              </button>
              <AnimatePresence>
                {showModelMenu && (
                  <motion.div className="pi-dropdown" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}>
                    {MODELS.map((m) => (
                      <button key={m.id} className={`pi-dropdown-item${model === m.id ? ' active' : ''}`} onClick={(e) => { e.stopPropagation(); setModel(m.id); setShowModelMenu(false) }}>
                        {m.icon}<span>{m.label}</span>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Effort selector */}
            <div className="pi-select" ref={effortRef}>
              <button className="pi-select-btn" onClick={(e) => { e.stopPropagation(); setShowEffortMenu((v) => !v); setShowModelMenu(false) }}>
                <span>{effort}</span><ChevronDown size={12} />
              </button>
              <AnimatePresence>
                {showEffortMenu && (
                  <motion.div className="pi-dropdown" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}>
                    {EFFORTS.map((e) => (
                      <button key={e} className={`pi-dropdown-item${effort === e ? ' active' : ''}`} onClick={(ev) => { ev.stopPropagation(); setEffort(e); setShowEffortMenu(false) }}>
                        <span>{e}</span>
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          <div className="pi-right">
            {onLive && (
              <button className="pi-icon-btn pi-live" onClick={(e) => { e.stopPropagation(); onLive() }} title="Live voice">
                <Mic2 size={16} />
              </button>
            )}
            <button className={`pi-send${(value.trim() || files.length > 0) && !busy ? ' ready' : ''}${busy ? ' busy' : ''}`} onClick={handleSubmit} disabled={(!value.trim() && files.length === 0) || busy}>
              {busy ? <Swirling size={18} /> : <Send size={16} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
