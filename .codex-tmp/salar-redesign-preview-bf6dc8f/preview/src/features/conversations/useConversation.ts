import { useCallback, useEffect, useRef, useState } from "react";

import type { SalarGateway } from "../../contracts/gateway";
import type {
  ApprovalStreamRequest,
  ChatMessage,
  ChatStreamEvent,
  ConversationSummary,
} from "../../contracts/models";

export interface ToolActivity {
  id: string;
  tool: string;
  args: Record<string, unknown>;
  result?: unknown;
  state: "working" | "complete";
}

type ConversationStatus =
  | "loading"
  | "ready"
  | "sending"
  | "offline"
  | "interrupted";

export interface ConversationState {
  conversations: ConversationSummary[];
  activeConversation?: ConversationSummary;
  messages: ChatMessage[];
  tools: ToolActivity[];
  approvals: ApprovalStreamRequest[];
  completionAnnouncement: string;
  status: ConversationStatus;
  error: string;
  load: () => Promise<void>;
  selectConversation: (conversation: ConversationSummary) => Promise<void>;
  createConversation: () => Promise<void>;
  send: (content: string) => Promise<boolean>;
}

function isAbort(error: unknown) {
  return (
    (error instanceof Error || error instanceof DOMException) &&
    error.name === "AbortError"
  );
}

export function useConversation(gateway: SalarGateway): ConversationState {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConversation, setActiveConversation] =
    useState<ConversationSummary>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [tools, setTools] = useState<ToolActivity[]>([]);
  const [approvals, setApprovals] = useState<ApprovalStreamRequest[]>([]);
  const [status, setStatus] = useState<ConversationStatus>("loading");
  const [error, setError] = useState("");
  const [completionAnnouncement, setCompletionAnnouncement] = useState("");
  const generationRef = useRef(0);
  const streamRef = useRef<AbortController | undefined>(undefined);
  const sendingRef = useRef(false);
  const mountedRef = useRef(true);

  const cancelCurrent = useCallback(() => {
    generationRef.current += 1;
    streamRef.current?.abort();
    streamRef.current = undefined;
    sendingRef.current = false;
  }, []);

  const selectConversation = useCallback(
    async (conversation: ConversationSummary) => {
      cancelCurrent();
      const generation = generationRef.current;
      setActiveConversation(conversation);
      setMessages([]);
      setTools([]);
      setApprovals([]);
      setError("");
      setCompletionAnnouncement("");
      setStatus("loading");
      try {
        const history = await gateway.getConversation(conversation.id);
        if (!mountedRef.current || generation !== generationRef.current) return;
        setMessages(history);
        setStatus("ready");
      } catch (loadError) {
        if (!mountedRef.current || generation !== generationRef.current) return;
        setStatus("offline");
        setError(
          `I couldn’t load ${conversation.title}. Your other conversations are still available.`,
        );
      }
    },
    [cancelCurrent, gateway],
  );

  const load = useCallback(async () => {
    cancelCurrent();
    const generation = generationRef.current;
    setStatus("loading");
    setError("");
    setCompletionAnnouncement("");
    setTools([]);
    setApprovals([]);
    try {
      const next = await gateway.listConversations();
      if (!mountedRef.current || generation !== generationRef.current) return;
      setConversations(next);
      const first = next[0];
      if (first) {
        setActiveConversation(first);
        try {
          const history = await gateway.getConversation(first.id);
          if (!mountedRef.current || generation !== generationRef.current) return;
          setMessages(history);
        } catch {
          if (!mountedRef.current || generation !== generationRef.current) return;
          setMessages([]);
          setError(`I couldn’t load ${first.title}. You can try it again.`);
          setStatus("offline");
          return;
        }
      } else {
        setActiveConversation(undefined);
        setMessages([]);
      }
      setStatus("ready");
    } catch {
      if (!mountedRef.current || generation !== generationRef.current) return;
      setStatus("offline");
      setError("I couldn’t reach your conversations. Check the connection and try again.");
    }
  }, [cancelCurrent, gateway]);

  useEffect(() => {
    mountedRef.current = true;
    void load();
    return () => {
      mountedRef.current = false;
      cancelCurrent();
    };
  }, [cancelCurrent, load]);

  const createConversation = useCallback(async () => {
    cancelCurrent();
    const generation = generationRef.current;
    setError("");
    setCompletionAnnouncement("");
    try {
      const conversation = await gateway.createConversation();
      if (!mountedRef.current || generation !== generationRef.current) return;
      setConversations((current) => [
        conversation,
        ...current.filter((item) => item.id !== conversation.id),
      ]);
      setActiveConversation(conversation);
      setMessages([]);
      setTools([]);
      setApprovals([]);
      setStatus("ready");
    } catch {
      if (!mountedRef.current || generation !== generationRef.current) return;
      setStatus("offline");
      setError("I couldn’t start a new conversation. Nothing was created.");
    }
  }, [cancelCurrent, gateway]);

  const send = useCallback(
    async (rawContent: string): Promise<boolean> => {
      const content = rawContent.trim();
      const conversation = activeConversation;
      if (!content || !conversation || sendingRef.current) return false;

      sendingRef.current = true;
      streamRef.current?.abort();
      const controller = new AbortController();
      streamRef.current = controller;
      generationRef.current += 1;
      const generation = generationRef.current;
      const createdAt = new Date().toISOString();
      const userId = `optimistic-user-${generation}`;
      const assistantId = `optimistic-assistant-${generation}`;
      let assistantStarted = false;
      let assistantContent = "";
      let doneReceived = false;

      setMessages((current) => [
        ...current,
        {
          id: userId,
          conversationId: conversation.id,
          role: "user",
          content,
          createdAt,
        },
      ]);
      setError("");
      setCompletionAnnouncement("");
      setStatus("sending");

      try {
        for await (const event of gateway.streamConversation(
          conversation.id,
          content,
          controller.signal,
        )) {
          if (!mountedRef.current || generation !== generationRef.current) {
            return false;
          }
          if (event.type === "token") {
            assistantContent += event.content;
            setMessages((current) => {
              if (!assistantStarted) {
                assistantStarted = true;
                return [
                  ...current,
                  {
                    id: assistantId,
                    conversationId: conversation.id,
                    role: "assistant",
                    content: event.content,
                    createdAt: new Date().toISOString(),
                  },
                ];
              }
              return current.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + event.content }
                  : message,
              );
            });
          } else if (event.type === "tool_call") {
            const id = `tool-${generation}-${event.tool}-${Date.now()}`;
            setTools((current) => [
              ...current,
              { id, tool: event.tool, args: event.args, state: "working" },
            ]);
          } else if (event.type === "tool_result") {
            setTools((current) => {
              let index = -1;
              for (let currentIndex = current.length - 1; currentIndex >= 0; currentIndex -= 1) {
                const activity = current[currentIndex];
                if (activity?.tool === event.tool && activity.state === "working") {
                  index = currentIndex;
                  break;
                }
              }
              return current.map((activity, activityIndex) =>
                activityIndex === index
                  ? { ...activity, result: event.result, state: "complete" }
                  : activity,
              );
            });
          } else if (event.type === "approval_request") {
            setApprovals((current) => [
              ...current.filter((request) => request.id !== event.request.id),
              event.request,
            ]);
          } else if (event.type === "error") {
            setError(
              `The response was interrupted: ${event.message} Your partial response is preserved.`,
            );
            setStatus("interrupted");
            return true;
          } else if (event.type === "done") {
            doneReceived = true;
            if (assistantStarted) {
              setMessages((current) =>
                current.map((message) =>
                  message.id === assistantId
                    ? {
                        ...message,
                        id: event.messageId || message.id,
                        createdAt: event.createdAt || message.createdAt,
                      }
                    : message,
                ),
              );
              setCompletionAnnouncement(`SALAR replied: ${assistantContent}`);
            }
          }
        }
        if (mountedRef.current && generation === generationRef.current) {
          if (doneReceived) {
            setStatus("ready");
          } else {
            setStatus("interrupted");
            setError(
              "The response ended before SALAR confirmed completion. Your partial response is preserved.",
            );
          }
        }
        return true;
      } catch (streamError) {
        if (
          isAbort(streamError) ||
          !mountedRef.current ||
          generation !== generationRef.current
        ) {
          return false;
        }
        setStatus("interrupted");
        setError(
          "The response was interrupted. Your partial response is preserved, and no action was assumed complete.",
        );
        return true;
      } finally {
        if (generation === generationRef.current) {
          sendingRef.current = false;
          streamRef.current = undefined;
        }
      }
    },
    [activeConversation, gateway],
  );

  return {
    conversations,
    activeConversation,
    messages,
    tools,
    approvals,
    completionAnnouncement,
    status,
    error,
    load,
    selectConversation,
    createConversation,
    send,
  };
}
