import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowUp, Mic2, Paperclip, Square, UploadCloud, X } from 'lucide-react'

const ALLOWED_EXT = ['.txt', '.md', '.pdf', '.docx', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.html', '.css', '.png', '.jpg', '.jpeg', '.webp', '.gif']
const MAX_BYTES = 20 * 1024 * 1024

export interface DraftFile {
  id: string
  file: File
}

interface ComposerProps {
  onSend: (text: string, files: File[]) => void
  onVoice?: () => void
  busy?: boolean
  onStop?: () => void
  placeholder?: string
  compact?: boolean
}

export default function Composer({
  onSend, onVoice, busy, onStop, placeholder, compact,
}: ComposerProps) {
  const [value, setValue] = useState('')
  const [files, setFiles] = useState<DraftFile[]>([])
  const [focused, setFocused] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [rejected, setRejected] = useState<string[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const boxRef = useRef<HTMLDivElement>(null)

  const addFiles = useCallback((list: FileList | File[]) => {
    const incoming = Array.from(list)
    if (incoming.length === 0) return
    const rejections: string[] = []
    setFiles((prev) => {
      const existing = new Set(prev.map((d) => `${d.file.name}-${d.file.size}-${d.file.lastModified}`))
      const fresh = incoming
        .filter((f) => {
          const ext = `.${f.name.split('.').pop()?.toLowerCase() || ''}`
          if (!ALLOWED_EXT.includes(ext)) {
            rejections.push(`${f.name} (unsupported type)`)
            return false
          }
          if (f.size > MAX_BYTES) {
            rejections.push(`${f.name} (over 20MB)`)
            return false
          }
          return !existing.has(`${f.name}-${f.size}-${f.lastModified}`)
        })
        .map((file) => ({ id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, file }))
      return [...prev, ...fresh].slice(0, 6)
    })
    if (rejections.length) {
      setRejected(rejections)
      window.setTimeout(() => setRejected([]), 4000)
    }
  }, [])

  const removeFile = (id: string) => setFiles((prev) => prev.filter((f) => f.id !== id))

  const submit = () => {
    const text = value.trim()
    if (!text && files.length === 0) return
    if (busy) return
    const draft = files
    setValue('')
    setFiles([])
    onSend(text, draft.map((d) => d.file))
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const target = e.target as Node
      if (boxRef.current && boxRef.current.contains(target)) {
        const items = Array.from(e.clipboardData?.items || [])
        const incoming = items.filter((i) => i.type.startsWith('image/')).map((i) => i.getAsFile()!).filter(Boolean)
        if (incoming.length) {
          e.preventDefault()
          addFiles(incoming)
        }
      }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [addFiles])

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer?.files) addFiles(e.dataTransfer.files)
  }

  return (
    <div className="ws-composer-wrap" style={compact ? { marginTop: 0, width: '100%' } : undefined}>
      <div
        ref={boxRef}
        className={`ws-composer${focused ? ' is-focused' : ''}`}
        onDragEnter={(e) => { e.preventDefault(); setDragging(true) }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={(e) => { if (!boxRef.current?.contains(e.relatedTarget as Node)) setDragging(false) }}
        onDrop={onDrop}
      >
        {files.length > 0 && (
          <div className="ws-composer__chips">
            {files.map((d) => (
              <span key={d.id} className="ws-chip" title={d.file.name}>
                <span>{d.file.name}</span>
                <button className="ws-chip__x" onClick={() => removeFile(d.id)} aria-label={`Remove ${d.file.name}`}>
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
        {rejected.length > 0 && (
          <div className="ws-composer__reject" role="alert">
            Skipped: {rejected.join(', ')}
          </div>
        )}
        <div className="ws-composer__row">
          <textarea
            className="ws-composer__textarea"
            value={value}
            placeholder={placeholder || 'Ask Salaar anything — or drop files here…'}
            rows={1}
            onChange={(e) => {
              setValue(e.target.value)
              e.target.style.height = 'auto'
              e.target.style.height = `${Math.min(e.target.scrollHeight, 200)}px`
            }}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={onKeyDown}
            aria-label="Message"
          />
          <button className="ws-composer__btn" onClick={() => fileInput.current?.click()} title="Attach files" aria-label="Attach files">
            <Paperclip size={17} />
          </button>
          {onVoice && (
            <button className="ws-composer__btn" onClick={onVoice} title="Voice message" aria-label="Voice message">
              <Mic2 size={17} />
            </button>
          )}
          <input
            ref={fileInput}
            type="file"
            multiple
            hidden
            onChange={(e) => { if (e.target.files) addFiles(e.target.files); e.target.value = '' }}
          />
          {busy && onStop ? (
            <button className="ws-composer__send" onClick={onStop} title="Stop" aria-label="Stop">
              <Square size={15} fill="currentColor" />
            </button>
          ) : (
            <button className="ws-composer__send" onClick={submit} disabled={!value.trim() && files.length === 0} title="Send" aria-label="Send">
              <ArrowUp size={18} />
            </button>
          )}
        </div>
        <div className="ws-composer__foot">
          <UploadCloud size={11} />
          Drag & drop or paste images · Enter to send · Shift+Enter for newline
        </div>
        {dragging && <div className="ws-drop-overlay">Drop files to attach</div>}
      </div>
    </div>
  )
}