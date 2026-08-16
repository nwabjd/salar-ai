import { AlertCircle, CheckCircle2, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

type StatusTone = "info" | "success" | "warning" | "error" | "loading";

interface StatusMessageProps {
  children: ReactNode;
  tone?: StatusTone;
}

export function StatusMessage({
  children,
  tone = "info",
}: StatusMessageProps) {
  const Icon = tone === "success" ? CheckCircle2 : tone === "loading" ? LoaderCircle : AlertCircle;
  const urgent = tone === "error";

  return (
    <p
      className={`status-message status-message--${tone}`}
      role={urgent ? "alert" : "status"}
      aria-live={urgent ? "assertive" : "polite"}
    >
      <Icon aria-hidden="true" size={18} />
      <span>{children}</span>
    </p>
  );
}
