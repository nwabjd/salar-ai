import {
  Library,
  MessageCircle,
  MoreHorizontal,
  Sunrise,
} from "lucide-react";

export type Destination =
  | "briefing"
  | "conversations"
  | "library"
  | "more";

interface PrimaryNavProps {
  activeDestination: Destination;
  onDestinationChange: (destination: Destination) => void;
  variant: "rail" | "dock";
  hidden?: boolean;
}

const destinations = [
  { id: "briefing", label: "Briefing", Icon: Sunrise },
  { id: "conversations", label: "Conversations", Icon: MessageCircle },
  { id: "library", label: "Library", Icon: Library },
  { id: "more", label: "More", Icon: MoreHorizontal },
] as const;

export function PrimaryNav({
  activeDestination,
  onDestinationChange,
  variant,
  hidden,
}: PrimaryNavProps) {
  const testId =
    variant === "rail" ? "desktop-primary-nav" : "mobile-primary-nav";

  return (
    <nav
      className={`primary-nav primary-nav--${variant}`}
      aria-label={variant === "rail" ? "Primary" : "Mobile primary"}
      data-testid={testId}
      data-layout={variant}
      hidden={hidden}
    >
      {variant === "rail" ? (
        <div className="primary-nav__brand" aria-label="SALAR">
          <span className="primary-nav__brand-mark" aria-hidden="true">
            S
          </span>
        </div>
      ) : null}

      <ul className="primary-nav__list">
        {destinations.map(({ id, label, Icon }) => (
          <li key={id}>
            <button
              className="primary-nav__item"
              type="button"
              aria-label={label}
              aria-current={activeDestination === id ? "page" : undefined}
              onClick={() => onDestinationChange(id)}
            >
              <Icon aria-hidden="true" size={variant === "rail" ? 20 : 19} />
              <span className="primary-nav__label">{label}</span>
            </button>
          </li>
        ))}
      </ul>

      {variant === "rail" ? (
        <div
          className="primary-nav__connection"
          title="Private connection is ready"
        >
          <span className="connection-dot" aria-hidden="true" />
          <span>Ready</span>
        </div>
      ) : null}
    </nav>
  );
}
