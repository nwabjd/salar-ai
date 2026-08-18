import React, { useCallback, useRef, useState } from 'react'
import { Paperclip, Send, Globe, X, Mic2, Image as ImageIcon } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAutoResizeTextarea } from '../hooks/use-auto-resize-textarea'

interface PromptInputBoxProps {
  onSend: (message: string, files?: File[]) => void
  placeholder?: string
  className?: string
}

export default function PromptInputBox({ onSend, placeholder = 'Type a message…', className = '' }: PromptInputBoxProps) {
  const [value, setValue] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [isFocused, setIsFocused] = useState(false)
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 52, maxHeight: 200 })
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = useCallback(() => {
    if (!value.trim() && files.length === 0) return
    onSend(value, files.length > 0 ? files : undefined)
    setValue('')
    setFiles([])
    adjustHeight(true)
  }, [value, files, onSend, adjustHeight])

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(e.target.files || [])
    setFiles((prev) => [...prev, ...selected])
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
  }

  return (
    <div className={`prompt-wrap ${className}`}>
      <div className={`prompt-box${isFocused ? ' focused' : ''}`} onClick={() => textareaRef.current?.focus()}>
        {/* File chips */}
        <AnimatePresence>
          {files.length > 0 && (
            <motion.div
              className="prompt-files"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
            >
              {files.map((file, i) => (
                <motion.div
                  key={`${file.name}-${i}`}
                  className="prompt-file-chip"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                >
                  <ImageIcon size={12} />
                  <span>{file.name.length > 20 ? file.name.slice(0, 17) + '…' : file.name}</span>
                  <button className="prompt-file-remove" onClick={(e) => { e.stopPropagation(); removeFile(i) }}>
                    <X size={10} />
                  </button>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Textarea */}
        <div className="prompt-textarea-wrap">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => { setValue(e.target.value); adjustHeight() }}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={placeholder}
            className="prompt-textarea"
            rows={1}
          />
        </div>

        {/* Bottom bar */}
        <div className="prompt-bottom">
          <div className="prompt-left">
            <button className="prompt-icon-btn" onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click() }} title="Attach files">
              <Paperclip size={16} />
            </button>
            <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleFileChange} />
          </div>
          <button
            className={`prompt-send${value.trim() || files.length > 0 ? ' ready' : ''}`}
            onClick={handleSubmit}
            disabled={!value.trim() && files.length === 0}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
