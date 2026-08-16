import { type ReactNode } from "react";

interface IconButtonProps {
  children: ReactNode;
  label: string;
  onClick?: () => void;
}

export function IconButton({ children, label, onClick }: IconButtonProps) {
  return (
    <button
      className="icon-button"
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
