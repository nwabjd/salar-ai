"use client"

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"

export interface OrbInputProps {
  value?: string
  defaultValue?: string
  placeholder?: string
  disabled?: boolean
  loading?: boolean
  className?: string
  onChange?: (value: string) => void
  onSubmit?: (value: string) => void
}

export function OrbInput({
  value: controlledValue,
  defaultValue = "",
  placeholder,
  disabled = false,
  loading = false,
  className,
  onChange,
  onSubmit,
}: OrbInputProps) {
  const [internalValue, setInternalValue] = useState(defaultValue)
  const [isFocused, setIsFocused] = useState(false)
  const [placeholderIdx, setPlaceholderIdx] = useState(0)
  const [typed, setTyped] = useState("")
  const [typing, setTyping] = useState(true)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const intervalRef = useRef<number | null>(null)
  const timeoutRef = useRef<number | null>(null)

  const value = controlledValue ?? internalValue

  const placeholders = useMemo(
    () => [
      "Ask anything...",
      "What's on your mind?",
      "How can I help you?",
      "What would you like to know?",
    ],
    []
  )

  const displayPlaceholder = placeholder ?? `${typed}${typing ? "|" : ""}`

  useEffect(() => {
    if (placeholder) return

    if (intervalRef.current) clearInterval(intervalRef.current)
    if (timeoutRef.current) clearTimeout(timeoutRef.current)

    const current = placeholders[placeholderIdx]
    if (!current) {
      setTyped("")
      setTyping(false)
      return
    }

    const chars = Array.from(current)
    setTyped("")
    setTyping(true)
    let ci = 0

    intervalRef.current = window.setInterval(() => {
      if (ci < chars.length) {
        setTyped(chars.slice(0, ci + 1).join(""))
        ci++
      } else {
        if (intervalRef.current) clearInterval(intervalRef.current)
        setTyping(false)
        timeoutRef.current = window.setTimeout(() => {
          setPlaceholderIdx((p) => (p + 1) % placeholders.length)
        }, 2200)
      }
    }, 75)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      if (timeoutRef.current) clearTimeout(timeoutRef.current)
    }
  }, [placeholderIdx, placeholders, placeholder])

  const autoResize = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = Math.min(el.scrollHeight, 200) + "px"
  }, [])

  useEffect(() => {
    autoResize()
  }, [value, autoResize])

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const v = e.target.value
    setInternalValue(v)
    onChange?.(v)
  }

  function handleSubmit() {
    const trimmed = value.trim()
    if (!trimmed || disabled || loading) return
    onSubmit?.(trimmed)
    if (controlledValue === undefined) setInternalValue("")
    if (textareaRef.current) textareaRef.current.style.height = "auto"
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const hasText = value.trim().length > 0

  return (
    <div className={`orb-input-root ${className ?? ""}`}>
      {/* Animated glow backdrop */}
      <div className={`orb-input-glow ${isFocused ? "orb-input-glow--active" : ""}`} />

      {/* Main container */}
      <div className={`orb-input-bar ${isFocused ? "orb-input-bar--focused" : ""} ${disabled ? "orb-input-bar--disabled" : ""}`}>

        {/* Orb */}
        <div className="orb-input-orb-wrap">
          <div className="orb-input-orb">
            <div className="orb-input-orb-core" />
            <div className="orb-input-orb-ring" />
          </div>
        </div>

        {/* Divider */}
        <div className="orb-input-divider" />

        {/* Textarea */}
        <div className="orb-input-field-wrap">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={displayPlaceholder}
            disabled={disabled}
            rows={1}
            className="orb-input-textarea"
            aria-label="Ask a question"
          />
        </div>

        {/* Send / Loading indicator */}
        <button
          className={`orb-input-send ${hasText && !disabled && !loading ? "orb-input-send--ready" : ""} ${loading ? "orb-input-send--loading" : ""}`}
          onClick={handleSubmit}
          disabled={!hasText || disabled || loading}
          aria-label="Send message"
          type="button"
        >
          {loading ? (
            <svg className="orb-input-spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="orb-input-send-icon">
              <path d="M5 12h14" />
              <path d="m12 5 7 7-7 7" />
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}

export default OrbInput
