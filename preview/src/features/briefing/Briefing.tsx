import { CalendarDays, RefreshCw } from "lucide-react";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { ActionCard } from "../../components/ActionCard";
import { EmptyState } from "../../components/EmptyState";
import { Skeleton } from "../../components/Skeleton";
import { StatusMessage } from "../../components/StatusMessage";
import type { SalarGateway } from "../../contracts/gateway";
import type { BriefingSnapshot } from "../../contracts/models";
import {
  type BriefingEntry,
  type BriefingSourceGateway,
  groupBriefing,
  loadBriefing,
} from "./loadBriefing";

interface BriefingProps {
  gateway: BriefingSourceGateway &
    Pick<
      SalarGateway,
      "dismissReminder" | "updateTask" | "performConfirmedAction"
    >;
  now?: () => Date;
  onDiscuss?: (item: BriefingEntry) => void;
}

const systemNow = () => new Date();

function greeting(now: Date): string {
  const hour = now.getHours();
  if (hour < 12) return "Good morning.";
  if (hour < 18) return "Good afternoon.";
  return "Good evening.";
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function humanSource(source: string): string {
  return source.charAt(0).toUpperCase() + source.slice(1);
}

function summaryFor(snapshot: BriefingSnapshot): string {
  if (snapshot.unavailable.length === 5) {
    return "I couldn’t reach your connected sources yet, so I won’t guess at your day.";
  }

  const decisions = snapshot.attention.length;
  const moving = snapshot.tasks.filter(
    (task) => task.status === "in_progress",
  ).length;
  const unavailable = snapshot.unavailable.map(humanSource).join(", ");
  const attentionUnavailable = snapshot.unavailable.includes("attention");

  if (attentionUnavailable && moving > 0) {
    const otherUnavailable = snapshot.unavailable
      .filter((source) => source !== "attention")
      .map(humanSource);
    return [
      "Your focused work is moving. Attention is unavailable, so I can’t verify whether a decision is waiting.",
      otherUnavailable.length
        ? `${otherUnavailable.join(", ")} ${
            otherUnavailable.length === 1 ? "is" : "are"
          } also unavailable, so this view may be incomplete.`
        : "",
    ]
      .filter(Boolean)
      .join(" ");
  }

  if (decisions === 0 && moving === 0 && snapshot.unavailable.length) {
    return `${unavailable} ${
      snapshot.unavailable.length === 1 ? "is" : "are"
    } unavailable, so I can’t call the day clear yet.`;
  }

  let summary: string;
  if (decisions === 1 && moving > 0) {
    summary =
      "One decision needs you, and your focused work is already moving.";
  } else if (decisions > 1 && moving > 0) {
    summary = `${decisions} decisions need you, while your focused work keeps moving.`;
  } else if (decisions > 0) {
    summary =
      decisions === 1
      ? "One decision is waiting for your attention."
      : `${decisions} decisions are waiting for your attention.`;
  } else if (moving > 0) {
    summary = "Your focused work is moving, with no new decisions waiting.";
  } else {
    summary = "Your day is quiet. There is room to choose what matters next.";
  }

  if (snapshot.unavailable.length) {
    summary += ` ${unavailable} ${
      snapshot.unavailable.length === 1 ? "is" : "are"
    } unavailable, so this view may be incomplete.`;
  }
  return summary;
}

function detailFor(entry: BriefingEntry): string {
  switch (entry.kind) {
    case "calendar":
      return entry.item.location
        ? `${formatTime(entry.item.startsAt)} · ${entry.item.location}`
        : formatTime(entry.item.startsAt);
    case "reminder":
      return entry.item.message;
    case "attention":
      return entry.item.detail;
    case "task":
      return entry.item.description;
    case "conversation":
      return entry.item.preview;
  }
}

function eyebrowFor(entry: BriefingEntry): string {
  switch (entry.kind) {
    case "calendar":
      return "Calendar";
    case "reminder":
      return `Reminder · ${formatTime(entry.item.remindAt)}`;
    case "attention":
      return entry.item.severity === "critical"
        ? "Needs attention"
        : "For your review";
    case "task":
      return "Focused work";
    case "conversation":
      return "Recent conversation";
  }
}

function titleFor(entry: BriefingEntry): string {
  return entry.item.title;
}

type ConfirmableAttentionEntry = Extract<
  BriefingEntry,
  { kind: "attention" }
>;

interface BriefingConfirmationProps {
  entry: ConfirmableAttentionEntry;
  busy: boolean;
  error: string;
  requiresRefresh: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  onRefreshStatus: () => void;
}

const focusableSelector = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function BriefingConfirmation({
  entry,
  busy,
  error,
  requiresRefresh,
  onCancel,
  onConfirm,
  onRefreshStatus,
}: BriefingConfirmationProps) {
  const titleId = `${useId()}-confirmation-title`;
  const dialogRef = useRef<HTMLElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const refreshRef = useRef<HTMLButtonElement>(null);
  const onCancelRef = useRef(onCancel);
  const action = entry.item.action;
  onCancelRef.current = onCancel;

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    confirmRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  useEffect(() => {
    if (requiresRefresh && !busy) {
      refreshRef.current?.focus();
    } else if (!requiresRefresh && !busy) {
      confirmRef.current?.focus();
    }
  }, [busy, requiresRefresh]);

  if (!action) return null;

  function containFocus(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key === "Escape" && !busy) {
      event.preventDefault();
      onCancelRef.current();
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
    <div className="briefing-confirmation__backdrop">
      <section
        ref={dialogRef}
        className="briefing-confirmation"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={containFocus}
        tabIndex={-1}
      >
        <p className="briefing-confirmation__eyebrow">Your approval</p>
        <h2 id={titleId}>Confirm {action.label}</h2>
        <dl className="briefing-confirmation__scope">
          <div>
            <dt>Target</dt>
            <dd>{entry.item.title}</dd>
          </div>
          <div>
            <dt>Scope</dt>
            <dd>This briefing item only.</dd>
          </div>
          <div>
            <dt>Effect</dt>
            <dd>
              {action.description ??
                "SALAR will carry out the action shown above."}
            </dd>
          </div>
        </dl>
        {error ? (
          <StatusMessage
            tone={busy ? "loading" : requiresRefresh ? "error" : "success"}
          >
            {error}
          </StatusMessage>
        ) : null}
        <div className="briefing-confirmation__actions">
          <button
            className="briefing-confirmation__cancel"
            type="button"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </button>
          {requiresRefresh ? (
            <button
              className="briefing-confirmation__refresh"
              type="button"
              onClick={onRefreshStatus}
              disabled={busy}
              ref={refreshRef}
            >
              Refresh status before retrying
            </button>
          ) : null}
          <button
            className="briefing-confirmation__confirm"
            type="button"
            onClick={onConfirm}
            ref={confirmRef}
            disabled={busy || requiresRefresh}
          >
            Confirm {action.label}
          </button>
        </div>
      </section>
    </div>
  );
}

export function Briefing({
  gateway,
  now = systemNow,
  onDiscuss = () => undefined,
}: BriefingProps) {
  const [snapshot, setSnapshot] = useState<BriefingSnapshot>();
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");
  const [statusTone, setStatusTone] =
    useState<"success" | "warning" | "error" | "loading">("success");
  const [busyId, setBusyId] = useState<string>();
  const [pendingConfirmation, setPendingConfirmation] =
    useState<ConfirmableAttentionEntry>();
  const [confirmationError, setConfirmationError] = useState("");
  const [confirmationNeedsRefresh, setConfirmationNeedsRefresh] =
    useState(false);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const refreshButtonRef = useRef<HTMLButtonElement>(null);
  const focusRefreshAfterMutationRef = useRef(false);
  const requestIdRef = useRef(0);
  const mutationInFlightRef = useRef(false);

  const refresh = useCallback(async (announce = false) => {
    const requestId = ++requestIdRef.current;
    if (announce) {
      setStatus("Refreshing your briefing…");
      setStatusTone("loading");
    }
    setLoading(true);
    const next = await loadBriefing(gateway, now);
    if (requestId !== requestIdRef.current) return undefined;
    setSnapshot(next);
    setLoading(false);
    if (announce) {
      setStatus(
        next.unavailable.length
          ? "Briefing updated with some sources unavailable."
          : "Briefing updated.",
      );
      setStatusTone(next.unavailable.length ? "warning" : "success");
    }
    return next;
  }, [gateway, now]);

  useEffect(() => {
    const requestId = ++requestIdRef.current;
    let active = true;
    setLoading(true);
    setStatus("");
    void loadBriefing(gateway, now).then((next) => {
      if (active && requestId === requestIdRef.current) {
        setSnapshot(next);
        setLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [gateway, now]);

  useLayoutEffect(() => {
    if (
      focusRefreshAfterMutationRef.current &&
      !busyId &&
      !pendingConfirmation
    ) {
      focusRefreshAfterMutationRef.current = false;
      refreshButtonRef.current?.focus();
    }
  }, [busyId, pendingConfirmation]);

  const groups = useMemo(
    () => (snapshot ? groupBriefing(snapshot, now()) : undefined),
    [now, snapshot],
  );

  async function runPrimary(entry: BriefingEntry) {
    if (mutationInFlightRef.current) return;

    if (entry.kind === "attention" && entry.item.action) {
      returnFocusRef.current =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      setConfirmationError("");
      setConfirmationNeedsRefresh(false);
      setPendingConfirmation(entry);
      return;
    }

    if (
      entry.kind === "calendar" ||
      entry.kind === "conversation" ||
      entry.kind === "attention"
    ) {
      onDiscuss(entry);
      return;
    }

    mutationInFlightRef.current = true;
    setBusyId(entry.id);
    setStatus("");
    try {
      if (entry.kind === "reminder") {
        await gateway.dismissReminder(entry.item.id);
        setStatus(`${entry.item.title} is complete.`);
        setStatusTone("success");
        await refresh();
      } else {
        await gateway.updateTask(entry.item.id, { status: "done" });
        setStatus(`${entry.item.title} is complete.`);
        setStatusTone("success");
        await refresh();
      }
    } catch {
      await refresh();
      setStatus(
        `I couldn’t verify whether ${entry.item.title} completed. I refreshed the briefing before retrying.`,
      );
      setStatusTone("error");
    } finally {
      mutationInFlightRef.current = false;
      setBusyId(undefined);
    }
  }

  function cancelConfirmation() {
    if (mutationInFlightRef.current) return;
    setPendingConfirmation(undefined);
    setConfirmationError("");
    setConfirmationNeedsRefresh(false);
    queueMicrotask(() => returnFocusRef.current?.focus());
  }

  async function confirmAttention() {
    const entry = pendingConfirmation;
    if (!entry?.item.action || mutationInFlightRef.current) return;
    mutationInFlightRef.current = true;
    setBusyId(entry.id);
    setConfirmationError("");
    try {
      const result = await gateway.performConfirmedAction(entry.item.action);
      if (!result.ok) {
        setConfirmationError(
          `${result.message} Refresh status before retrying.`,
        );
        setConfirmationNeedsRefresh(true);
        return;
      }
      setStatus(result.message);
      setStatusTone("success");
      await refresh();
      focusRefreshAfterMutationRef.current = true;
      setPendingConfirmation(undefined);
    } catch {
      setConfirmationError(
        `I couldn’t verify whether ${entry.item.action.label} completed. Refresh status before retrying.`,
      );
      setConfirmationNeedsRefresh(true);
    } finally {
      mutationInFlightRef.current = false;
      setBusyId(undefined);
    }
  }

  async function refreshConfirmationStatus() {
    const entry = pendingConfirmation;
    if (
      !entry?.item.action ||
      mutationInFlightRef.current ||
      !confirmationNeedsRefresh
    ) {
      return;
    }

    mutationInFlightRef.current = true;
    setBusyId(entry.id);
    setConfirmationError("Refreshing the action status…");
    try {
      const next = await refresh();
      if (!next) return;
      if (next.unavailable.includes("attention")) {
        setConfirmationError(
          "I couldn’t verify the alert status because Attention is unavailable. Refresh status before retrying.",
        );
        return;
      }
      const stillPending = next.attention.some(
        (item) => item.action?.id === entry.item.action?.id,
      );
      if (stillPending) {
        setConfirmationNeedsRefresh(false);
        setConfirmationError(
          "Status refreshed. Review the details before confirming again.",
        );
      } else {
        setStatus("Status refreshed. This alert no longer needs action.");
        setStatusTone("success");
        focusRefreshAfterMutationRef.current = true;
        setPendingConfirmation(undefined);
        setConfirmationNeedsRefresh(false);
        setConfirmationError("");
      }
    } finally {
      mutationInFlightRef.current = false;
      setBusyId(undefined);
    }
  }

  function primaryFor(entry: BriefingEntry): {
    label: string;
    ariaLabel?: string;
  } {
    switch (entry.kind) {
      case "reminder":
        return {
          label: "Mark done",
          ariaLabel: `Mark ${entry.item.title} done`,
        };
      case "task":
        return {
          label: "Complete",
          ariaLabel: `Mark ${entry.item.title} complete`,
        };
      case "attention":
        return { label: entry.item.action?.label ?? "Review with SALAR" };
      case "calendar":
        return { label: "Prepare with SALAR" };
      case "conversation":
        return { label: "Continue conversation" };
    }
  }

  if (loading && !snapshot) {
    return (
      <section className="briefing briefing--loading" aria-label="Briefing">
        <StatusMessage tone="loading">
          Gathering what matters for you…
        </StatusMessage>
        {[1, 2, 3].map((item) => (
          <div
            className="briefing-skeleton"
            data-testid="briefing-skeleton"
            key={item}
          >
            <Skeleton height="0.7rem" width="7rem" />
            <Skeleton height="1.35rem" width="min(22rem, 72%)" />
            <Skeleton height="0.9rem" width="min(34rem, 88%)" />
          </div>
        ))}
      </section>
    );
  }

  if (!snapshot || !groups) return null;

  const isEmpty =
    groups.today.length + groups.needsYou.length + groups.inMotion.length === 0;

  return (
    <section className="briefing" aria-labelledby="briefing-title">
      <div
        className="briefing__surface"
        aria-hidden={pendingConfirmation ? true : undefined}
        inert={pendingConfirmation ? true : undefined}
      >
        <header className="briefing__header">
        <div>
          <p className="briefing__eyebrow">Your personal briefing</p>
          <h1 id="briefing-title">{greeting(now())}</h1>
          <p className="briefing__summary">{summaryFor(snapshot)}</p>
        </div>
        <button
          ref={refreshButtonRef}
          className="briefing__refresh"
          type="button"
          onClick={() => void refresh(true)}
          disabled={loading || Boolean(busyId)}
        >
          <RefreshCw aria-hidden="true" size={16} />
          Refresh
        </button>
        </header>

        <div className="briefing__announcements" aria-live="polite">
        {status ? (
          <StatusMessage tone={statusTone}>
            {status}
          </StatusMessage>
        ) : null}
        {snapshot.unavailable.length ? (
          <StatusMessage tone="warning">
            {snapshot.unavailable.map(humanSource).join(", ")}{" "}
            {snapshot.unavailable.length === 1 ? "is" : "are"} unavailable right
            now.
          </StatusMessage>
        ) : null}
        </div>

        {isEmpty ? (
        <EmptyState
          title={
            snapshot.unavailable.length === 5
              ? "Your briefing is out of reach."
              : snapshot.unavailable.length
                ? "Some context is out of reach."
              : "Nothing needs your hand."
          }
        >
          <p>
            {snapshot.unavailable.length === 5
              ? "Reconnect or refresh when your sources are available."
              : snapshot.unavailable.length
                ? "Refresh when the missing source is available."
              : "Your connected sources are quiet. SALAR will keep watch."}
          </p>
        </EmptyState>
        ) : (
        <div className="briefing__sections">
          {(
            [
              ["Today", groups.today],
              ["Needs you", groups.needsYou],
              ["In motion", groups.inMotion],
            ] as const
          ).map(([title, entries]) =>
            entries.length ? (
              <section
                className="briefing-section"
                aria-labelledby={`briefing-${title.replace(" ", "-")}`}
                key={title}
              >
                <div className="briefing-section__heading">
                  <CalendarDays aria-hidden="true" size={17} />
                  <h2 id={`briefing-${title.replace(" ", "-")}`}>{title}</h2>
                  <span>{entries.length}</span>
                </div>
                <div className="briefing-section__rows">
                  {entries.map((entry) => {
                    const primary = primaryFor(entry);
                    return (
                      <ActionCard
                        key={`${entry.kind}-${entry.id}`}
                        eyebrow={eyebrowFor(entry)}
                        title={titleFor(entry)}
                        detail={detailFor(entry)}
                        primaryLabel={primary.label}
                        primaryAriaLabel={primary.ariaLabel}
                        onPrimary={() => void runPrimary(entry)}
                        onDiscuss={() => onDiscuss(entry)}
                        busy={Boolean(busyId)}
                      />
                    );
                  })}
                </div>
              </section>
            ) : null,
          )}
        </div>
        )}
      </div>
      {pendingConfirmation ? (
        <BriefingConfirmation
          entry={pendingConfirmation}
          busy={busyId === pendingConfirmation.id}
          error={confirmationError}
          requiresRefresh={confirmationNeedsRefresh}
          onCancel={cancelConfirmation}
          onConfirm={() => void confirmAttention()}
          onRefreshStatus={() => void refreshConfirmationStatus()}
        />
      ) : null}
    </section>
  );
}
