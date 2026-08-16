import { MessageCircle, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { SalarGateway } from "../../contracts/gateway";
import type { ChatMessage, ConversationSummary } from "../../contracts/models";

interface ConversationPanelProps {
  gateway: SalarGateway;
  onClose: () => void;
}

export function ConversationPanel({
  gateway,
  onClose,
}: ConversationPanelProps) {
  const [conversations, setConversations] = useState<ConversationSummary[]>(
    [],
  );
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    gateway.listConversations().then(setConversations);
  }, [gateway]);

  useEffect(() => {
    if (!activeId) {
      setMessages([]);
      return;
    }
    gateway.getConversation(activeId).then(setMessages);
  }, [activeId, gateway]);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  function formatTime(value: string): string {
    return new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));
  }

  return (
    <div className="conversation-panel" ref={panelRef}>
      <header className="conversation-panel__header">
        <div className="conversation-panel__title-group">
          <MessageCircle aria-hidden="true" size={18} />
          <h2 className="conversation-panel__title">Conversations</h2>
        </div>
        <button
          className="conversation-panel__close"
          type="button"
          aria-label="Close conversations"
          onClick={onClose}
          ref={closeRef}
        >
          <X size={18} aria-hidden="true" />
        </button>
      </header>

      <div className="conversation-panel__body">
        {activeId ? (
          <div className="conversation-panel__messages">
            <button
              className="conversation-panel__back"
              type="button"
              onClick={() => setActiveId(null)}
            >
              ← Back to conversations
            </button>
            {messages.length === 0 ? (
              <p className="conversation-panel__empty">
                No messages yet in this conversation.
              </p>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`conversation-panel__message conversation-panel__message--${msg.role}`}
                >
                  <div className="conversation-panel__message-role">
                    {msg.role === "assistant" ? "SALAR" : "You"}
                  </div>
                  <p className="conversation-panel__message-content">
                    {msg.content}
                  </p>
                  <span className="conversation-panel__message-time">
                    {formatTime(msg.createdAt)}
                  </span>
                </div>
              ))
            )}
            <div className="conversation-panel__compose">
              <input
                className="conversation-panel__input"
                type="text"
                placeholder="Message SALAR…"
                aria-label="Message SALAR"
                disabled
              />
              <button
                className="conversation-panel__send"
                type="button"
                aria-label="Send message"
                disabled
              >
                Send
              </button>
            </div>
          </div>
        ) : (
          <ul className="conversation-panel__list">
            {conversations.length === 0 ? (
              <p className="conversation-panel__empty">
                No conversations yet. Tap the button above to start one.
              </p>
            ) : (
              conversations.map((conv) => (
                <li key={conv.id}>
                  <button
                    className="conversation-panel__item"
                    type="button"
                    onClick={() => setActiveId(conv.id)}
                  >
                    <div className="conversation-panel__item-info">
                      <span className="conversation-panel__item-title">
                        {conv.title}
                      </span>
                      <span className="conversation-panel__item-preview">
                        {conv.preview}
                      </span>
                    </div>
                    <div className="conversation-panel__item-meta">
                      <span className="conversation-panel__item-time">
                        {formatTime(conv.updatedAt)}
                      </span>
                      {conv.unreadCount > 0 ? (
                        <span className="conversation-panel__item-unread">
                          {conv.unreadCount}
                        </span>
                      ) : null}
                    </div>
                  </button>
                </li>
              ))
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
