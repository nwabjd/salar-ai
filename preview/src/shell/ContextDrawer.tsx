import { X } from "lucide-react";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

import { IconButton } from "../components/IconButton";

interface ContextDrawerProps {
  children: ReactNode;
  open?: boolean;
  title?: string;
  onClose?: () => void;
}

const focusableSelector = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function isMobileViewport() {
  return typeof window !== "undefined" && window.innerWidth <= 820;
}

export function ContextDrawer({
  children,
  open = true,
  title = "Context",
  onClose,
}: ContextDrawerProps) {
  const titleId = `${useId()}-context-title`;
  const drawerRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const [mobile, setMobile] = useState(isMobileViewport);
  const [locallyDismissed, setLocallyDismissed] = useState(false);
  const visible = open && !locallyDismissed;

  useEffect(() => {
    const updateViewport = () => setMobile(isMobileViewport());
    window.addEventListener("resize", updateViewport);
    return () => window.removeEventListener("resize", updateViewport);
  }, []);

  useEffect(() => {
    if (open) {
      setLocallyDismissed(false);
    }
  }, [open]);

  const dismiss = useCallback(() => {
    setLocallyDismissed(true);
    onClose?.();
  }, [onClose]);

  useEffect(() => {
    if (!visible || !mobile) {
      return;
    }

    previousFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const drawer = drawerRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const firstFocusable =
      drawer?.querySelector<HTMLElement>(focusableSelector);
    (firstFocusable ?? drawer)?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      previousFocusRef.current?.focus();
      previousFocusRef.current = null;
    };
  }, [mobile, visible]);

  function containFocus(event: ReactKeyboardEvent<HTMLElement>) {
    if (!mobile) {
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      dismiss();
      return;
    }
    if (event.key !== "Tab") {
      return;
    }

    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>(focusableSelector),
    ).filter((element) => !element.hasAttribute("hidden"));
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first || !last) {
      event.preventDefault();
      event.currentTarget.focus();
      return;
    }

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  if (!visible) {
    return null;
  }

  const drawer = (
    <aside
      ref={drawerRef}
      className={`context-drawer${mobile ? " context-drawer--sheet" : ""}`}
      aria-labelledby={titleId}
      aria-modal={mobile ? true : undefined}
      role={mobile ? "dialog" : undefined}
      tabIndex={mobile ? -1 : undefined}
      onKeyDown={containFocus}
    >
      <header className="context-drawer__header">
        <h2 className="context-drawer__title" id={titleId}>
          {title}
        </h2>
        {mobile || onClose ? (
          <IconButton label="Close context drawer" onClick={dismiss}>
            <X aria-hidden="true" size={18} />
          </IconButton>
        ) : null}
      </header>
      {children}
    </aside>
  );

  if (!mobile) {
    return drawer;
  }

  return (
    <div
      className="context-drawer-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          dismiss();
        }
      }}
    >
      {drawer}
    </div>
  );
}
