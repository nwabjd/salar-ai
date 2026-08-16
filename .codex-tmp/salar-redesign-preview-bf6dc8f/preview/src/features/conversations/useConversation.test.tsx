import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChatStreamEvent, ConversationSummary } from "../../contracts/models";
import { FixtureGateway } from "../../data/FixtureGateway";
import { ConversationWorkspace } from "./ConversationWorkspace";

class ControlledStream implements AsyncIterable<ChatStreamEvent> {
  private waiting:
    | ((result: IteratorResult<ChatStreamEvent>) => void)
    | undefined;
  private queued: ChatStreamEvent[] = [];
  private closed = false;

  push(event: ChatStreamEvent) {
    if (this.waiting) {
      const resolve = this.waiting;
      this.waiting = undefined;
      resolve({ done: false, value: event });
    } else {
      this.queued.push(event);
    }
  }

  finish() {
    this.closed = true;
    this.waiting?.({ done: true, value: undefined });
    this.waiting = undefined;
  }

  [Symbol.asyncIterator](): AsyncIterator<ChatStreamEvent> {
    return {
      next: () => {
        const value = this.queued.shift();
        if (value) return Promise.resolve({ done: false, value });
        if (this.closed) return Promise.resolve({ done: true, value: undefined });
        return new Promise((resolve) => {
          this.waiting = resolve;
        });
      },
    };
  }
}

afterEach(cleanup);

describe("ConversationWorkspace", () => {
  it("loads history and searches it", async () => {
    render(<ConversationWorkspace gateway={new FixtureGateway()} />);

    expect(screen.getByRole("status")).toHaveTextContent("Gathering conversations");
    expect(await screen.findByRole("heading", { name: "Morning reset" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search conversations" }), {
      target: { value: "studio" },
    });
    expect(screen.getByText("Studio planning")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Morning reset/ })).toBeNull();
  });

  it("creates and selects a new conversation", async () => {
    const gateway = new FixtureGateway();
    const create = vi.spyOn(gateway, "createConversation");
    render(<ConversationWorkspace gateway={gateway} />);

    fireEvent.click(await screen.findByRole("button", { name: "New conversation" }));
    expect(create).toHaveBeenCalledOnce();
    expect(await screen.findByRole("heading", { name: "New conversation" })).toBeInTheDocument();
  });

  it("optimistically inserts the user message and accumulates streamed tokens", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    vi.spyOn(gateway, "streamConversation").mockReturnValue(stream);
    render(<ConversationWorkspace gateway={gateway} />);

    const composer = await screen.findByRole("textbox", { name: "Message SALAR" });
    fireEvent.change(composer, { target: { value: "Help me plan" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(screen.getByText("Help me plan")).toBeInTheDocument();

    await act(async () => stream.push({ type: "token", content: "Let’s " }));
    await act(async () => stream.push({ type: "token", content: "make space." }));
    expect(screen.getByText("Let’s make space.")).toBeInTheDocument();
    await act(async () => {
      stream.push({ type: "done", messageId: "assistant-1", createdAt: "2026-07-30T10:00:00Z" });
      stream.finish();
    });
  });

  it("moves tool activity from working to complete", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    vi.spyOn(gateway, "streamConversation").mockReturnValue(stream);
    render(<ConversationWorkspace gateway={gateway} />);

    fireEvent.change(await screen.findByRole("textbox", { name: "Message SALAR" }), {
      target: { value: "Find my brief" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () =>
      stream.push({
        type: "tool_call",
        tool: "search_knowledge",
        args: {
          query: "brief",
          requires_confirmation: true,
          target: "This must not be inferred as an approval",
        },
      }),
    );
    expect(screen.getByText("Working")).toBeInTheDocument();
    expect(screen.getByText("Search Knowledge").closest("article")).toHaveClass("action-row");
    expect(screen.getByRole("button", { name: "View Search Knowledge details" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Review/ })).toBeNull();
    await act(async () => stream.push({ type: "tool_result", tool: "search_knowledge", result: { count: 1 } }));
    expect(screen.getByText("Complete")).toBeInTheDocument();
    stream.finish();
  });

  it("preserves a partial response when streaming is interrupted", async () => {
    const gateway = new FixtureGateway();
    async function* interrupted(): AsyncIterable<ChatStreamEvent> {
      yield { type: "token", content: "I found the " };
      throw new Error("connection lost");
    }
    vi.spyOn(gateway, "streamConversation").mockReturnValue(interrupted());
    render(<ConversationWorkspace gateway={gateway} />);

    fireEvent.change(await screen.findByRole("textbox", { name: "Message SALAR" }), {
      target: { value: "Continue" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("I found the")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("The response was interrupted");
  });

  it("treats EOF without an explicit done event as interrupted", async () => {
    const gateway = new FixtureGateway();
    async function* incomplete(): AsyncIterable<ChatStreamEvent> {
      yield { type: "token", content: "This is only partial" };
    }
    vi.spyOn(gateway, "streamConversation").mockReturnValue(incomplete());
    render(<ConversationWorkspace gateway={gateway} />);

    fireEvent.change(await screen.findByRole("textbox", { name: "Message SALAR" }), {
      target: { value: "Finish explicitly" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("This is only partial")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "ended before SALAR confirmed completion",
    );
  });

  it("recovers after the conversation list is offline", async () => {
    const gateway = new FixtureGateway();
    const recovered = await gateway.listConversations();
    vi.spyOn(gateway, "listConversations")
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(recovered);
    render(<ConversationWorkspace gateway={gateway} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("couldn’t reach your conversations");
    fireEvent.click(screen.getByRole("button", { name: "Try conversations again" }));
    expect(await screen.findByRole("heading", { name: "Morning reset" })).toBeInTheDocument();
  });

  it("returns focus to the composer after an accepted send", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    vi.spyOn(gateway, "streamConversation").mockReturnValue(stream);
    render(<ConversationWorkspace gateway={gateway} />);

    const composer = await screen.findByRole("textbox", { name: "Message SALAR" });
    fireEvent.change(composer, { target: { value: "Stay with this" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(composer).toHaveFocus();
    stream.finish();
  });

  it("aborts stale streams when switching conversations", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    const signals: (AbortSignal | undefined)[] = [];
    vi.spyOn(gateway, "streamConversation").mockImplementation((_id, _text, signal) => {
      signals.push(signal);
      return stream;
    });
    render(<ConversationWorkspace gateway={gateway} />);

    fireEvent.change(await screen.findByRole("textbox", { name: "Message SALAR" }), {
      target: { value: "Old work" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    fireEvent.click(screen.getByRole("button", { name: /Studio planning/ }));
    expect(signals[0]?.aborted).toBe(true);
    await act(async () => stream.push({ type: "token", content: "stale answer" }));
    expect(screen.queryByText("stale answer")).toBeNull();
  });

  it("prevents duplicate sends while a response is active", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    const send = vi.spyOn(gateway, "streamConversation").mockReturnValue(stream);
    render(<ConversationWorkspace gateway={gateway} />);
    const composer = await screen.findByRole("textbox", { name: "Message SALAR" });
    fireEvent.change(composer, { target: { value: "Only once" } });
    const button = screen.getByRole("button", { name: "Send message" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(send).toHaveBeenCalledOnce();
    stream.finish();
  });

  it("requires review and confirmation before an explicit approval request executes", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    vi.spyOn(gateway, "streamConversation").mockReturnValue(stream);
    const perform = vi.spyOn(gateway, "performConfirmedAction");
    render(<ConversationWorkspace gateway={gateway} />);

    fireEvent.change(await screen.findByRole("textbox", { name: "Message SALAR" }), {
      target: { value: "Check the alert" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () =>
      stream.push({
        type: "approval_request",
        request: {
          id: "send-partner-follow-up",
          kind: "acknowledge_alert",
          label: "Acknowledge alert",
          title: "Review alert acknowledgement",
          target: "A prepared message needs review",
          scope: "This alert only",
          effect: "Marks the alert acknowledged. It does not send the message.",
        },
      }),
    );

    expect(perform).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Review Acknowledge alert" }));
    expect(perform).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Review alert acknowledgement" })).toHaveTextContent(
      "Marks the alert acknowledged. It does not send the message.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm Acknowledge alert" }));
    await waitFor(() => expect(perform).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    stream.finish();
  });

  it("refresh-gates an uncertain explicit approval outcome before retrying", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    vi.spyOn(gateway, "streamConversation").mockReturnValue(stream);
    const perform = vi
      .spyOn(gateway, "performConfirmedAction")
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ok: true, message: "Acknowledged." });
    const refresh = vi.spyOn(gateway, "listAttention");
    render(<ConversationWorkspace gateway={gateway} />);
    fireEvent.change(await screen.findByRole("textbox", { name: "Message SALAR" }), {
      target: { value: "Check the alert" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () =>
      stream.push({
        type: "approval_request",
        request: {
          id: "send-partner-follow-up",
          kind: "acknowledge_alert",
          label: "Acknowledge alert",
          title: "Review alert acknowledgement",
          target: "A prepared message needs review",
          scope: "This alert only",
          effect: "Marks the alert acknowledged.",
        },
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Review Acknowledge alert" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm Acknowledge alert" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("couldn’t verify the outcome");
    fireEvent.click(screen.getByRole("button", { name: "Refresh status before retrying" }));
    await waitFor(() => expect(refresh).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Confirm Acknowledge alert" })).toBeEnabled(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Confirm Acknowledge alert" }));
    await waitFor(() => expect(perform).toHaveBeenCalledTimes(2));
    stream.finish();
  });

  it("does not let cancel and reopen bypass an uncertain approval outcome", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    vi.spyOn(gateway, "streamConversation").mockReturnValue(stream);
    const perform = vi
      .spyOn(gateway, "performConfirmedAction")
      .mockRejectedValue(new Error("offline"));
    render(<ConversationWorkspace gateway={gateway} />);
    fireEvent.change(await screen.findByRole("textbox", { name: "Message SALAR" }), {
      target: { value: "Check the alert" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () =>
      stream.push({
        type: "approval_request",
        request: {
          id: "send-partner-follow-up",
          kind: "acknowledge_alert",
          label: "Acknowledge alert",
          title: "Review alert acknowledgement",
          target: "A prepared message needs review",
          scope: "This alert only",
          effect: "Marks the alert acknowledged.",
        },
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Review Acknowledge alert" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm Acknowledge alert" }));
    await screen.findByText(/couldn’t verify the outcome/);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "Review Acknowledge alert" }));

    expect(screen.getByRole("button", { name: "Confirm Acknowledge alert" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Refresh status before retrying" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm Acknowledge alert" }));
    expect(perform).toHaveBeenCalledOnce();
    stream.finish();
  });

  it("uses a chat log and announces only a completed assistant response", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    vi.spyOn(gateway, "streamConversation").mockReturnValue(stream);
    render(<ConversationWorkspace gateway={gateway} />);
    expect(await screen.findByRole("log", { name: "Messages" })).toHaveAttribute(
      "aria-live",
      "off",
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Message SALAR" }), {
      target: { value: "Announce once" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await act(async () => stream.push({ type: "token", content: "One " }));
    expect(document.querySelector(".conversation-response-announcement")).toBeEmptyDOMElement();
    await act(async () => stream.push({ type: "token", content: "answer." }));
    expect(document.querySelector(".conversation-response-announcement")).toBeEmptyDOMElement();
    await act(async () =>
      stream.push({
        type: "done",
        messageId: "assistant-complete",
        createdAt: "2026-07-30T10:00:00Z",
      }),
    );
    expect(document.querySelector(".conversation-response-announcement")).toHaveTextContent(
      "SALAR replied: One answer.",
    );
    stream.finish();
  });

  it("aborts an active stream on unmount without applying later events", async () => {
    const gateway = new FixtureGateway();
    const stream = new ControlledStream();
    let signal: AbortSignal | undefined;
    vi.spyOn(gateway, "streamConversation").mockImplementation((_id, _message, nextSignal) => {
      signal = nextSignal;
      return stream;
    });
    const view = render(<ConversationWorkspace gateway={gateway} />);
    fireEvent.change(await screen.findByRole("textbox", { name: "Message SALAR" }), {
      target: { value: "Hold this" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    view.unmount();
    expect(signal?.aborted).toBe(true);
    await act(async () => stream.push({ type: "token", content: "late token" }));
    expect(screen.queryByText("late token")).toBeNull();
  });
});
