import {
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";

import type { ConfirmedActionResult } from "../contracts/models";
import { StatusMessage } from "./StatusMessage";

export interface ApprovalRequest {
  title: string;
  actionLabel: string;
  target: string;
  scope: string;
  effect: string;
}

interface ApprovalDialogProps {
  request: ApprovalRequest;
  onConfirm: () =>
    | void
    | ConfirmedActionResult
    | Promise<void | ConfirmedActionResult>;
  onCancel: () => void;
  onRefreshStatus?: () => void | Promise<void>;
  initialUncertain?: boolean;
  onUncertain?: () => void;
  onVerified?: () => void;
}

const focusableSelector = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

export function ApprovalDialog({
  request,
  onConfirm,
  onCancel,
  onRefreshStatus,
  initialUncertain = false,
  onUncertain,
  onVerified,
}: ApprovalDialogProps) {
  const titleId = `${useId()}-approval-title`;
  const confirmRef = useRef<HTMLButtonElement>(null);
  const refreshRef = useRef<HTMLButtonElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(initialUncertain);
  const [message, setMessage] = useState(
    initialUncertain
      ? "The previous outcome is still unverified. Refresh status before retrying."
      : "",
  );

  useEffect(() => {
    previousFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const previousOverflow = document.body.style.overflow;
    const isolated: Array<{
      element: HTMLElement;
      inert: string | null;
      ariaHidden: string | null;
    }> = [];
    let current: HTMLElement | null = backdropRef.current;
    while (current?.parentElement) {
      const parent = current.parentElement;
      for (const sibling of Array.from(parent.children)) {
        if (sibling === current || !(sibling instanceof HTMLElement)) continue;
        isolated.push({
          element: sibling,
          inert: sibling.getAttribute("inert"),
          ariaHidden: sibling.getAttribute("aria-hidden"),
        });
        sibling.setAttribute("inert", "");
        sibling.setAttribute("aria-hidden", "true");
      }
      current = parent;
      if (parent === document.body) break;
    }
    document.body.style.overflow = "hidden";
    confirmRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      for (const previous of isolated) {
        if (previous.inert === null) {
          previous.element.removeAttribute("inert");
        } else {
          previous.element.setAttribute("inert", previous.inert);
        }
        if (previous.ariaHidden === null) {
          previous.element.removeAttribute("aria-hidden");
        } else {
          previous.element.setAttribute("aria-hidden", previous.ariaHidden);
        }
      }
      previousFocusRef.current?.focus();
    };
  }, []);

  useEffect(() => {
    if (!busy && uncertain) refreshRef.current?.focus();
  }, [busy, uncertain]);

  async function confirm() {
    if (busyRef.current || uncertain) return;
    busyRef.current = true;
    setBusy(true);
    setMessage("");
    try {
      const result = await onConfirm();
      if (result && !result.ok) {
        setUncertain(true);
        onUncertain?.();
        setMessage(`${result.message} Refresh status before retrying.`);
      }
    } catch {
      setUncertain(true);
      onUncertain?.();
      setMessage(
        `I couldn’t verify the outcome of ${request.actionLabel}. Refresh status before retrying.`,
      );
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  async function refreshStatus() {
    if (busyRef.current || !onRefreshStatus) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await onRefreshStatus();
      setUncertain(false);
      onVerified?.();
      setMessage("Status refreshed. Review the details before confirming again.");
      queueMicrotask(() => confirmRef.current?.focus());
    } catch {
      setMessage("Status is still unavailable. Confirmation remains blocked.");
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function containFocus(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key === "Escape" && !busy) {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>(focusableSelector),
    );
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first || !last) {
      event.preventDefault();
      event.currentTarget.focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div className="approval-dialog__backdrop" ref={backdropRef}>
      <section
        className="approval-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={containFocus}
        tabIndex={-1}
      >
        <p className="approval-dialog__eyebrow">Your approval</p>
        <h2 id={titleId}>{request.title}</h2>
        <dl className="approval-dialog__scope">
          <div>
            <dt>Target</dt>
            <dd>{request.target}</dd>
          </div>
          <div>
            <dt>Scope</dt>
            <dd>{request.scope}</dd>
          </div>
          <div>
            <dt>Effect</dt>
            <dd>{request.effect}</dd>
          </div>
        </dl>
        {message ? (
          <StatusMessage tone={uncertain ? "error" : "success"}>
            {message}
          </StatusMessage>
        ) : null}
        <div className="approval-dialog__actions">
          <button type="button" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          {uncertain ? (
            <button
              type="button"
              ref={refreshRef}
              onClick={() => void refreshStatus()}
              disabled={busy || !onRefreshStatus}
            >
              Refresh status before retrying
            </button>
          ) : null}
          <button
            className="approval-dialog__confirm"
            type="button"
            ref={confirmRef}
            onClick={() => void confirm()}
            disabled={busy || uncertain}
          >
            Confirm {request.actionLabel}
          </button>
        </div>
      </section>
    </div>
  );
}
