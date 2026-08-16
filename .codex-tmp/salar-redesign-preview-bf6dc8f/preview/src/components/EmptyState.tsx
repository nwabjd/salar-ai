import { CircleDashed } from "lucide-react";
import { type ReactNode, useId } from "react";

interface EmptyStateProps {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, children, action }: EmptyStateProps) {
  const titleId = `${useId()}-empty-title`;

  return (
    <section className="empty-state" aria-labelledby={titleId}>
      <CircleDashed className="empty-state__icon" aria-hidden="true" size={28} />
      <h2 className="empty-state__title" id={titleId}>
        {title}
      </h2>
      <div className="empty-state__body">{children}</div>
      {action}
    </section>
  );
}
