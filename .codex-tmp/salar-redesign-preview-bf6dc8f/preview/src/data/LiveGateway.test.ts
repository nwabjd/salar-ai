import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveGateway } from "./LiveGateway";

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("LiveGateway", () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStorage.setItem("salar-preview.apiUrl", "https://preview.example.test/");
    sessionStorage.setItem("salar-preview.session", "preview-token");
    sessionStorage.setItem("salar_session", "production-token");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    sessionStorage.clear();
  });

  it("uses only preview-scoped session keys and sends the bearer token", async () => {
    const reads: string[] = [];
    const originalGetItem = sessionStorage.getItem.bind(sessionStorage);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(
      function (this: Storage, key: string) {
        if (this === sessionStorage) {
          reads.push(key);
        }
        return originalGetItem(key);
      },
    );

    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ state: "paired" }));
    vi.stubGlobal("fetch", fetchMock);

    const gateway = new LiveGateway();
    await expect(gateway.getAccessState()).resolves.toBe("paired");

    expect(new Set(reads)).toEqual(
      new Set(["salar-preview.apiUrl", "salar-preview.session"]),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "https://preview.example.test/api/auth/session",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer preview-token",
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("unwraps calendar events and triggered alerts in the briefing", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/calendar/today")) {
        return jsonResponse({
          events: [
            {
              id: "event-1",
              title: "Planning",
              start: "2026-07-29T19:00:00Z",
            },
          ],
        });
      }
      if (url.endsWith("/api/alerts/triggered")) {
        return jsonResponse({
          alerts: [
            {
              id: "alert-1",
              title: "Review needed",
              message: "A workflow is waiting.",
              severity: "warning",
            },
          ],
        });
      }
      return jsonResponse([]);
    });
    vi.stubGlobal("fetch", fetchMock);

    const briefing = await new LiveGateway().getBriefing();

    expect(briefing.calendar).toEqual([
      expect.objectContaining({ id: "event-1", title: "Planning" }),
    ]);
    expect(briefing.attention).toEqual([
      expect.objectContaining({
        id: "alert-1",
        title: "Review needed",
        severity: "warning",
      }),
    ]);
  });

  it("dispatches supported confirmed actions to existing backend routes", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ status: "approved" }));
    vi.stubGlobal("fetch", fetchMock);
    const gateway = new LiveGateway();

    await gateway.performConfirmedAction({
      id: "command-7",
      kind: "approve_command",
      label: "Approve command",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "https://preview.example.test/api/commands/command-7/approve",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it.each([
    [{ ok: false, message: "The alert could not be acknowledged." }, "The alert could not be acknowledged."],
    [{ detail: "The command is no longer pending." }, "The command is no longer pending."],
    [{ error: "Approval was rejected." }, "Approval was rejected."],
  ])(
    "treats a successful HTTP response carrying a failure body as not ok",
    async (body, message) => {
      vi.stubGlobal(
        "fetch",
        vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body)),
      );

      await expect(
        new LiveGateway().performConfirmedAction({
          id: "alert-7",
          kind: "acknowledge_alert",
          label: "Acknowledge alert",
        }),
      ).resolves.toEqual({
        ok: false,
        message,
      });
    },
  );

  it("rejects unsupported confirmed actions before making a request", async () => {
    const fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal("fetch", fetchMock);
    const gateway = new LiveGateway();

    await expect(
      gateway.performConfirmedAction({
        id: "dangerous",
        kind: "arbitrary_endpoint",
        label: "Do anything",
      } as never),
    ).rejects.toThrow("Unsupported confirmed action");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("counts workflows using the backend is_enabled field", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse([
          { id: "one", is_enabled: true },
          { id: "two", is_enabled: false },
          { id: "three", is_enabled: true },
        ]),
      ),
    );

    await expect(new LiveGateway().getWorkflowSummary()).resolves.toEqual(
      expect.objectContaining({ active: 2, paused: 1 }),
    );
  });

  it("parses fragmented and malformed SSE frames without losing later events", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      'data: {"type":"token","content":"Hel',
      'lo"}\n\ndata: not-json\n\n',
      'data: {"type":"done","message_id":"m1","created_at":"now"}\n\n',
    ];
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          new Response(stream, {
            headers: { "Content-Type": "text/event-stream" },
          }),
        ),
    );

    const events = [];
    for await (const event of new LiveGateway().streamConversation(
      "conversation-1",
      "Hello",
    )) {
      events.push(event);
    }

    expect(events).toEqual([
      { type: "token", content: "Hello" },
      { type: "error", message: "SALAR sent an unreadable stream event." },
      { type: "done", messageId: "m1", createdAt: "now" },
    ]);
  });

  it("accepts only explicit, fully typed approval request stream events", async () => {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            [
              'data: {"type":"approval_request","request":{"id":"alert-7","kind":"acknowledge_alert","label":"Acknowledge alert","title":"Review acknowledgement","target":"Alert 7","scope":"This alert only","effect":"Marks it acknowledged."}}',
              "",
              'data: {"type":"approval_request","request":{"id":"unsafe","kind":"arbitrary_endpoint","label":"Run","target":"Everything"}}',
              "",
              "",
            ].join("\n"),
          ),
        );
        controller.close();
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(stream, { headers: { "Content-Type": "text/event-stream" } }),
      ),
    );

    const events = [];
    for await (const event of new LiveGateway().streamConversation("conversation-1", "Hello")) {
      events.push(event);
    }
    expect(events).toEqual([
      {
        type: "approval_request",
        request: {
          id: "alert-7",
          kind: "acknowledge_alert",
          label: "Acknowledge alert",
          title: "Review acknowledgement",
          target: "Alert 7",
          scope: "This alert only",
          effect: "Marks it acknowledged.",
        },
      },
    ]);
  });

  it("preserves AbortError from an aborted stream request", async () => {
    const abortError = new DOMException("Aborted", "AbortError");
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockRejectedValue(abortError),
    );
    const stream = new LiveGateway().streamConversation(
      "conversation-1",
      "Hello",
    );

    await expect(stream[Symbol.asyncIterator]().next()).rejects.toBe(abortError);
  });

  it("cancels the response reader when a stream consumer stops early", async () => {
    const encoder = new TextEncoder();
    const cancel = vi.fn();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode('data: {"type":"token","content":"first"}\n\n'),
        );
      },
      cancel,
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          new Response(stream, {
            headers: { "Content-Type": "text/event-stream" },
          }),
        ),
    );

    for await (const _event of new LiveGateway().streamConversation(
      "conversation-1",
      "Hello",
    )) {
      break;
    }

    expect(cancel).toHaveBeenCalledOnce();
  });
});
