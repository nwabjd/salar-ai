import { ArrowUpRight, MessageCircle } from "lucide-react";
import { type ReactNode, useId } from "react";

interface ActionCardProps {
  eyebrow: string;
  title: string;
  detail?: string;
  meta?: ReactNode;
  primaryLabel: string;
  primaryAriaLabel?: string;
  onPrimary: () => void;
  onDiscuss: () => void;
  busy?: boolean;
}

export function ActionCard({
  eyebrow,
  title,
  detail,
  meta,
  primaryLabel,
  primaryAriaLabel,
  onPrimary,
  onDiscuss,
  busy = false,
}: ActionCardProps) {
  const titleId = `${useId()}-action-title`;

  return (
    <article className="action-row" aria-labelledby={titleId}>
      <div className="action-row__body">
        <p className="action-row__eyebrow">{eyebrow}</p>
        <h3 className="action-row__title" id={titleId}>
          {title}
        </h3>
        {detail ? <p className="action-row__detail">{detail}</p> : null}
        {meta ? <div className="action-row__meta">{meta}</div> : null}
      </div>
      <div className="action-row__actions">
        <button
          className="action-row__primary"
          type="button"
          aria-label={primaryAriaLabel}
          onClick={onPrimary}
          disabled={busy}
        >
          <span>{primaryLabel}</span>
          <ArrowUpRight aria-hidden="true" size={15} />
        </button>
        <button
          className="action-row__discuss"
          type="button"
          onClick={onDiscuss}
          disabled={busy}
        >
          <MessageCircle aria-hidden="true" size={15} />
          <span>Discuss with SALAR</span>
        </button>
      </div>
    </article>
  );
}
