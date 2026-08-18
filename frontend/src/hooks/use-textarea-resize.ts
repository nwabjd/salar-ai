import { useCallback, useEffect, useRef } from 'react'

export function useTextareaResize(value: string, rows = 1) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const adjustHeight = useCallback(
    (reset?: boolean) => {
      const textarea = textareaRef.current
      if (!textarea) return
      if (reset) {
        textarea.style.height = 'auto'
        return
      }
      textarea.style.height = 'auto'
      const newHeight = Math.min(textarea.scrollHeight, 400)
      textarea.style.height = `${newHeight}px`
    },
    [],
  )

  useEffect(() => {
    adjustHeight()
  }, [value, adjustHeight])

  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
    }
  }, [])

  return textareaRef
}
