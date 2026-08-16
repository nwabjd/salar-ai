import { CircleCheck, Info, LoaderCircle, TriangleAlert } from "lucide-react";
import { type ReactNode, useId } from "react";

interface StatusMessageProps {
  children: ReactNode;
  tone: "loading" | "success" | "warning" | "info";
}

const icons = {
  loading: LoaderCircle,
  success: CircleCheck,
  warning: TriangleAlert,
  info: Info,
};

export function StatusMessage({ children, tone }: StatusMessageProps) {
  const Icon = icons[tone];
  const labelledId = `${useId()}-status-label`;

  return (
    <div
      className="status-message"
      role="status"
      aria-labelledby={labelledId}
    >
      <Icon
        className={`status-message__icon status-message__icon--${tone}`}
        aria-hidden="true"
        size={18}
      />
      <span id={labelledId}>{children}</span>
    </div>
  );
}
