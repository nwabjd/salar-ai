import {
  FilePlus2,
  MessageCirclePlus,
  Mic2,
  Search,
  Send,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { ActionCard } from "../../components/ActionCard";
import {
  ApprovalDialog,
  type ApprovalRequest,
} from "../../components/ApprovalDialog";
import type { SalarGateway } from "../../contracts/gateway";
import type { ApprovalStreamRequest } from "../../contracts/models";
import { EmptyState } from "../../components/EmptyState";
import { StatusMessage } from "../../components/StatusMessage";
import { type ToolActivity, useConversation } from "./useConversation";

interface ConversationWorkspaceProps {
  gateway: SalarGateway;
  onStartLive?: () => void;
}

function friendlyToolName(tool: string) {
  return tool.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function ConversationWorkspace({
  gateway,
  onStartLive,
}: ConversationWorkspaceProps) {
  const conversation = useConversation(gateway);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [attachment, setAttachment] = useState("");
  const [selectedTool, setSelectedTool] = useState<ToolActivity>();
  const [selectedApproval, setSelectedApproval] =
    useState<ApprovalStreamRequest>();
  const [resolvedApprovalIds, setResolvedApprovalIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [uncertainApprovalIds, setUncertainApprovalIds] = useState<Set<string>>(
    () => new Set(),
  );
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) return conversation.conversations;
    return conversation.conversations.filter((item) =>
      `${item.title} ${item.preview}`.toLocaleLowerCase().includes(needle),
    );
  }, [conversation.conversations, query]);

  async function submit() {
    const content = draft.trim();
    if (!content) return;
    setDraft("");
    const accepted = conversation.send(content);
    composerRef.current?.focus();
    await accepted;
  }

  async function confirmApproval(request: ApprovalStreamRequest) {
    const result = await gateway.performConfirmedAction(request);
    if (result.ok) {
      setResolvedApprovalIds((current) => new Set(current).add(request.id));
      setUncertainApprovalIds((current) => {
        const next = new Set(current);
        next.delete(request.id);
        return next;
      });
      setSelectedApproval(undefined);
    }
    return result;
  }

  async function refreshApproval(request: ApprovalStreamRequest) {
    if (request.kind !== "acknowledge_alert") {
      throw new Error("A precise command status check is not available.");
    }
    const attention = await gateway.listAttention();
    const stillPending = attention.some(
      (item) => item.id === request.id || item.action?.id === request.id,
    );
    if (!stillPending) {
      setResolvedApprovalIds((current) => new Set(current).add(request.id));
      setSelectedApproval(undefined);
    }
  }

  function toDialogRequest(request: ApprovalStreamRequest): ApprovalRequest {
    return {
      title: request.title,
      actionLabel: request.label,
      target: request.target,
      scope: request.scope,
      effect: request.effect,
    };
  }

  return (
    <section className="conversation-workspace" aria-label="Conversations">
      <aside className="conversation-history" aria-label="Conversation history">
        <div className="conversation-history__heading">
          <div>
            <p className="conversation-workspace__eyebrow">Your threads</p>
            <h1>Conversations</h1>
          </div>
          <button
            className="conversation-history__new"
            type="button"
            aria-label="New conversation"
            onClick={() => void conversation.createConversation()}
          >
            <MessageCirclePlus aria-hidden="true" size={18} />
          </button>
        </div>
        <label className="conversation-history__search">
          <Search aria-hidden="true" size={17} />
          <span className="visually-hidden">Search conversations</span>
          <input
            type="search"
            aria-label="Search conversations"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search conversations"
          />
        </label>
        <div className="conversation-history__list">
          {conversation.status === "loading" && !conversation.conversations.length ? (
            <StatusMessage tone="loading">Gathering conversations…</StatusMessage>
          ) : null}
          {filtered.map((item) => (
            <button
              key={item.id}
              className="conversation-history__item"
              type="button"
              aria-current={conversation.activeConversation?.id === item.id ? "page" : undefined}
              onClick={() => void conversation.selectConversation(item)}
            >
              <strong>{item.title}</strong>
              <span>{item.preview || "A new space with SALAR"}</span>
            </button>
          ))}
        </div>
      </aside>

      <div className="conversation-thread">
        {conversation.error ? (
          <div className="conversation-thread__notice">
            <StatusMessage tone="error">{conversation.error}</StatusMessage>
            {conversation.status === "offline" ? (
              <button type="button" onClick={() => void conversation.load()}>
                Try conversations again
              </button>
            ) : null}
          </div>
        ) : null}

        {conversation.activeConversation ? (
          <>
            <header className="conversation-thread__header">
              <div>
                <p className="conversation-workspace__eyebrow">With SALAR</p>
                <h2>{conversation.activeConversation.title}</h2>
              </div>
              <button type="button" onClick={onStartLive}>
                <Mic2 aria-hidden="true" size={17} />
                Live
              </button>
            </header>

            <div
              className="conversation-messages"
              aria-label="Messages"
              role="log"
              aria-live="off"
            >
              {!conversation.messages.length && conversation.status !== "loading" ? (
                <EmptyState title="A clear place to begin.">
                  Ask what matters. SALAR will use only the connected context it can
                  actually reach.
                </EmptyState>
              ) : null}
              {conversation.messages.map((message) => (
                <article
                  key={message.id}
                  className={`conversation-message conversation-message--${message.role}`}
                  aria-label={`${message.role === "assistant" ? "SALAR" : message.role} message`}
                >
                  <span className="conversation-message__speaker">
                    {message.role === "assistant" ? "SALAR" : message.role === "user" ? "You" : "System"}
                  </span>
                  <p>{message.content}</p>
                </article>
              ))}
              {conversation.tools.map((activity) => (
                <ActionCard
                  key={activity.id}
                  eyebrow="Tool activity"
                  title={friendlyToolName(activity.tool)}
                  detail={
                    activity.state === "working"
                      ? "SALAR is waiting for this tool to finish."
                      : "The tool returned a result. No consequential action was inferred."
                  }
                  meta={activity.state === "working" ? "Working" : "Complete"}
                  primaryLabel="View details"
                  primaryAriaLabel={`View ${friendlyToolName(activity.tool)} details`}
                  onPrimary={() => setSelectedTool(activity)}
                />
              ))}
              {conversation.approvals.map((request) => (
                <ActionCard
                  key={`approval-${request.id}`}
                  eyebrow="Approval requested"
                  title={request.title}
                  detail={request.effect}
                  meta={
                    resolvedApprovalIds.has(request.id)
                      ? "Completed"
                      : "Waiting for your review"
                  }
                  primaryLabel={
                    resolvedApprovalIds.has(request.id) ? undefined : "Review"
                  }
                  primaryAriaLabel={`Review ${request.label}`}
                  onPrimary={
                    resolvedApprovalIds.has(request.id)
                      ? undefined
                      : () => setSelectedApproval(request)
                  }
                />
              ))}
            </div>
            <div
              className="conversation-response-announcement visually-hidden"
              aria-live="polite"
              aria-atomic="true"
            >
              {conversation.completionAnnouncement}
            </div>

            <div className="conversation-stream-status" aria-live="polite">
              {conversation.status === "sending" ? "SALAR is responding…" : ""}
            </div>

            <form
              className="conversation-composer"
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
            >
              {attachment ? (
                <p className="conversation-composer__attachment">
                  {attachment} selected. Chat upload is not connected in this preview yet.
                </p>
              ) : null}
              <textarea
                ref={composerRef}
                aria-label="Message SALAR"
                value={draft}
                rows={3}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void submit();
                  }
                }}
                placeholder="Ask SALAR anything…"
                disabled={conversation.status === "loading"}
              />
              <div className="conversation-composer__actions">
                <input
                  ref={fileRef}
                  className="visually-hidden"
                  type="file"
                  aria-label="Choose an attachment"
                  onChange={(event) => setAttachment(event.target.files?.[0]?.name ?? "")}
                />
                <button
                  type="button"
                  aria-label="Attach a file"
                  onClick={() => fileRef.current?.click()}
                >
                  <FilePlus2 aria-hidden="true" size={18} />
                </button>
                <button
                  className="conversation-composer__send"
                  type="submit"
                  aria-label="Send message"
                  disabled={!draft.trim() || conversation.status === "sending"}
                >
                  <Send aria-hidden="true" size={18} />
                  <span>Send</span>
                </button>
              </div>
            </form>
          </>
        ) : conversation.status !== "loading" ? (
          <EmptyState
            title="Start a conversation."
            action={
              <button type="button" onClick={() => void conversation.createConversation()}>
                New conversation
              </button>
            }
          >
            Create a thread when you’re ready to think something through with SALAR.
          </EmptyState>
        ) : null}
      </div>

      <aside className="conversation-inspector" aria-label="Conversation context">
        <p className="conversation-workspace__eyebrow">In this conversation</p>
        <h2>Context</h2>
        <section>
          <h3>Sources</h3>
          <p>No sources have been cited in this thread yet.</p>
        </section>
        <section>
          <h3>Actions</h3>
          <p>
            {conversation.tools.length || conversation.approvals.length
              ? `${conversation.tools.length} tool ${conversation.tools.length === 1 ? "activity" : "activities"} and ${conversation.approvals.length} explicit approval ${conversation.approvals.length === 1 ? "request" : "requests"} shown.`
              : "No tool activity in this thread."}
          </p>
          {selectedTool ? (
            <div className="conversation-inspector__tool" role="status">
              <strong>{friendlyToolName(selectedTool.tool)}</strong>
              <span>
                {selectedTool.state === "working"
                  ? "Request details"
                  : "Returned result"}
              </span>
              <pre>
                {JSON.stringify(
                  selectedTool.state === "working"
                    ? selectedTool.args
                    : selectedTool.result,
                  null,
                  2,
                )}
              </pre>
            </div>
          ) : null}
        </section>
        <p className="conversation-inspector__safety">
          Consequential actions pause for a target, scope, and effect review before execution.
        </p>
      </aside>
      {selectedApproval ? (
        <ApprovalDialog
          request={toDialogRequest(selectedApproval)}
          onCancel={() => setSelectedApproval(undefined)}
          onConfirm={() => confirmApproval(selectedApproval)}
          onRefreshStatus={() => refreshApproval(selectedApproval)}
          initialUncertain={uncertainApprovalIds.has(selectedApproval.id)}
          onUncertain={() =>
            setUncertainApprovalIds((current) =>
              new Set(current).add(selectedApproval.id),
            )
          }
          onVerified={() =>
            setUncertainApprovalIds((current) => {
              const next = new Set(current);
              next.delete(selectedApproval.id);
              return next;
            })
          }
        />
      ) : null}
    </section>
  );
}
