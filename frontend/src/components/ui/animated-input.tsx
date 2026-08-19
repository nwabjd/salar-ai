"use client"

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react"

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
  const [placeholderIndex, setPlaceholderIndex] = useState(0)
  const [displayedText, setDisplayedText] = useState("")
  const [isTyping, setIsTyping] = useState(true)
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

  const CHAR_DELAY = 75
  const IDLE_DELAY_AFTER_FINISH = 2200

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }

    if (placeholder) return

    const current = placeholders[placeholderIndex]
    if (!current) {
      setDisplayedText("")
      setIsTyping(false)
      return
    }

    const chars = Array.from(current)
    setDisplayedText("")
    setIsTyping(true)
    let charIndex = 0

    intervalRef.current = window.setInterval(() => {
      if (charIndex < chars.length) {
        setDisplayedText(chars.slice(0, charIndex + 1).join(""))
        charIndex += 1
      } else {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        setIsTyping(false)
        timeoutRef.current = window.setTimeout(() => {
          setPlaceholderIndex((prev) => (prev + 1) % placeholders.length)
        }, IDLE_DELAY_AFTER_FINISH)
      }
    }, CHAR_DELAY)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, [placeholderIndex, placeholders, placeholder])

  const autoResize = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = Math.min(el.scrollHeight, 220) + "px"
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

  const displayPlaceholder = placeholder ?? `${displayedText}${isTyping ? "|" : ""}`
  const hasText = value.trim().length > 0

  return (
    <div className={`relative ${className ?? ""}`}>
      <div
        className={`flex items-center gap-4 rounded-full border transition-all duration-300 ease-out ${
          isFocused
            ? "orb-bar-focused"
            : "orb-bar"
        } ${disabled ? "orb-bar-disabled" : ""}`}
      >
        <div className="relative flex-shrink-0">
          <div className={`orb-gif-wrap ${loading ? "orb-gif-loading" : ""}`}>
            <img
              src="https://media.giphy.com/media/26gsuUjoEBmLrNBxC/giphy.gif"
              alt="Animated orb"
              className="w-full h-full object-cover"
            />
          </div>
        </div>

        <div className="orb-divider" />

        <div className="flex-1 min-w-0">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={displayPlaceholder}
            disabled={disabled || loading}
            rows={1}
            data-testid="orb-input"
            aria-label="Ask a question"
            className="orb-textarea"
          />
        </div>

        <button
          className={`orb-send ${hasText && !disabled ? "orb-send-ready" : ""} ${loading ? "orb-send-loading" : ""}`}
          onClick={loading ? undefined : handleSubmit}
          disabled={!hasText || disabled}
          aria-label={loading ? "Stop" : "Send message"}
          type="button"
        >
          {loading ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <rect x="3" y="3" width="10" height="10" rx="2" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
