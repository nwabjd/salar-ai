import React, { useEffect, KeyboardEvent } from "react";

export function Skeleton({ className = "", style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={`skeleton ${className}`} style={style} />;
}

export function KeyboardHint({ children }: { children: React.ReactNode }) {
  return <kbd className="kbd">{children}</kbd>;
}

export function useKeyboardShortcut(key: string, ctrlKey: boolean, action: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === key && e.ctrlKey === ctrlKey && !e.shiftKey) {
        e.preventDefault();
        action();
      }
    };
    window.addEventListener("keydown", onKey as unknown as EventListener);
    return () => window.removeEventListener("keydown", onKey as unknown as EventListener);
  }, [key, ctrlKey, action]);
}
