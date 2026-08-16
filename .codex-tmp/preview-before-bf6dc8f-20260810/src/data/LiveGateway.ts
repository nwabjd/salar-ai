import type { SalarGateway } from "../contracts/gateway";
import type {
  AccessState,
  AttentionItem,
  BriefingSnapshot,
  CalendarItem,
  ChatMessage,
  ChatStreamEvent,
  CommunicationSummary,
  ConfirmableAction,
  ConfirmedActionResult,
  ConversationSummary,
  CreateReminderInput,
  CreateTaskInput,
  LoginCredentials,
  PairingCredentials,
  ReminderItem,
  SourceItem,
  SystemSummary,
  TaskItem,
  UpdateReminderInput,
  UpdateTaskInput,
  WorkflowSummary,
} from "../contracts/models";
import {
  asArray,
  asRecord,
  normalizeCalendarItem,
  normalizeConversation,
  normalizeMessage,
  normalizeReminder,
  normalizeSource,
  normalizeTask,
} from "../contracts/normalize";

const API_URL_KEY = "salar-preview.apiUrl";
const SESSION_KEY = "salar-preview.session";
const DEFAULT_API_URL = "https://salar-backend.onrender.com";

export class GatewayError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "GatewayError";
  }
}

interface LiveGatewayOptions {
  storage?: Storage;
  fetcher?: typeof fetch;
}

export class LiveGateway implements SalarGateway {
  private readonly configuredStorage?: Storage;
  private readonly configuredFetch?: typeof fetch;

  constructor(options: LiveGatewayOptions = {}) {
    this.configuredStorage = options.storage;
    this.configuredFetch = options.fetcher;
  }

  async getAccessState(): Promise<AccessState> {
    const { token } = this.previewSettings();
    if (!token) {
      return "unpaired";
    }
    try {
      await this.request("/api/auth/session");
      return "paired";
    } catch (error) {
      if (error instanceof GatewayError && (error.status === 401 || error.status === 403)) {
        return "expired";
      }
      if (error instanceof GatewayError && error.status === 0) {
        return "offline";
      }
      throw error;
    }
  }

  async pair(credentials: PairingCredentials): Promise<AccessState> {
    const response = asRecord(
      await this.request("/api/auth/pairing/redeem", {
        method: "POST",
        body: JSON.stringify(credentials),
      }),
    );
    this.storeSession(response.access_token);
    return "paired";
  }

  async login(credentials: LoginCredentials): Promise<AccessState> {
    const response = asRecord(
      await this.request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(credentials),
      }),
    );
    this.storeSession(response.access_token);
    return "paired";
  }

  async listConversations(): Promise<ConversationSummary[]> {
    return asArray(await this.request("/api/conversations")).map(
      normalizeConversation,
    );
  }

  async getConversation(conversationId: string): Promise<ChatMessage[]> {
    const response = asRecord(
      await this.request(`/api/conversations/${encodeURIComponent(conversationId)}`),
    );
    return asArray(response.messages).map((message) =>
      normalizeMessage(message, conversationId),
    );
  }

  async createConversation(title = "New conversation"): Promise<ConversationSummary> {
    return normalizeConversation(
      await this.request("/api/conversations", {
        method: "POST",
        body: JSON.stringify({ title }),
      }),
    );
  }

  async *streamConversation(
    conversationId: string,
    message: string,
    signal?: AbortSignal,
  ): AsyncIterable<ChatStreamEvent> {
    const response = await this.fetchResponse("/api/chat/stream", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: conversationId,
        content: message,
      }),
      signal,
    });
    if (!response.ok) {
      throw await this.errorFromResponse(response);
    }
    if (!response.body) {
      throw new GatewayError("The response stream was unavailable.", 0);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let reachedEnd = false;

    try {
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const event = this.parseSseFrame(frame);
          if (event) {
            yield event;
          }
        }
        if (done) {
          reachedEnd = true;
          break;
        }
      }
      if (buffer.trim()) {
        const event = this.parseSseFrame(buffer);
        if (event) {
          yield event;
        }
      }
    } finally {
      try {
        if (!reachedEnd) {
          await reader.cancel();
        }
      } finally {
        reader.releaseLock();
      }
    }
  }

  async getBriefing(): Promise<BriefingSnapshot> {
    const results = await Promise.allSettled([
      this.listTasks(),
      this.listReminders(),
      this.listCalendar(),
      this.listAttention(),
      this.listConversations(),
    ]);
    const unavailable: string[] = [];
    const valueAt = (index: number, label: string): unknown => {
      const result = results[index];
      if (!result || result.status === "rejected") {
        unavailable.push(label);
        return [];
      }
      return result.value;
    };

    return {
      generatedAt: new Date().toISOString(),
      tasks: valueAt(0, "tasks") as TaskItem[],
      reminders: valueAt(1, "reminders") as ReminderItem[],
      calendar: valueAt(2, "calendar") as CalendarItem[],
      attention: valueAt(3, "attention") as AttentionItem[],
      conversations: valueAt(4, "conversations") as ConversationSummary[],
      unavailable,
    };
  }

  async listTasks(): Promise<TaskItem[]> {
    return asArray(await this.request("/api/tasks")).map(normalizeTask);
  }

  async listReminders(): Promise<ReminderItem[]> {
    return asArray(
      await this.request("/api/reminders?upcoming_only=true"),
    ).map(normalizeReminder);
  }

  async listCalendar(): Promise<CalendarItem[]> {
    const response = await this.request("/api/calendar/today");
    const record = asRecord(response);
    return asArray(record.events ?? response).map(normalizeCalendarItem);
  }

  async listAttention(): Promise<AttentionItem[]> {
    const response = await this.request("/api/alerts/triggered");
    const record = asRecord(response);
    return asArray(record.alerts ?? response).map((item) =>
      this.normalizeAttention(item),
    );
  }

  async listSources(): Promise<SourceItem[]> {
    return asArray(await this.request("/api/knowledge")).map((value) =>
      this.normalizeKnowledgeSource(value),
    );
  }

  async searchSources(query: string): Promise<SourceItem[]> {
    return asArray(
      await this.request("/api/knowledge/search", {
        method: "POST",
        body: JSON.stringify({ query }),
      }),
    ).map((value) => this.normalizeKnowledgeSource(value));
  }

  async uploadSource(file: File): Promise<SourceItem> {
    const body = new FormData();
    body.append("file", file);
    return this.normalizeKnowledgeSource(
      await this.request("/api/knowledge/upload", {
        method: "POST",
        body,
      }),
    );
  }

  async createTask(input: CreateTaskInput): Promise<TaskItem> {
    return normalizeTask(
      await this.request("/api/tasks", {
        method: "POST",
        body: JSON.stringify({
          title: input.title,
          description: input.description ?? "",
          priority: input.priority ?? "medium",
          due_date: input.dueAt ?? null,
        }),
      }),
    );
  }

  async updateTask(taskId: string, patch: UpdateTaskInput): Promise<TaskItem> {
    return normalizeTask(
      await this.request(`/api/tasks/${encodeURIComponent(taskId)}`, {
        method: "PUT",
        body: JSON.stringify({
          ...patch,
          ...(patch.dueAt !== undefined ? { due_date: patch.dueAt } : {}),
          dueAt: undefined,
        }),
      }),
    );
  }

  async deleteTask(taskId: string): Promise<void> {
    await this.request(`/api/tasks/${encodeURIComponent(taskId)}`, {
      method: "DELETE",
    });
  }

  async createReminder(input: CreateReminderInput): Promise<ReminderItem> {
    return normalizeReminder(
      await this.request("/api/reminders", {
        method: "POST",
        body: JSON.stringify({
          title: input.title,
          message: input.message ?? "",
          remind_at: input.remindAt,
          recurrence: input.recurrence ?? "none",
        }),
      }),
    );
  }

  async updateReminder(
    reminderId: string,
    patch: UpdateReminderInput,
  ): Promise<ReminderItem> {
    return normalizeReminder(
      await this.request(`/api/reminders/${encodeURIComponent(reminderId)}`, {
        method: "PUT",
        body: JSON.stringify({
          ...patch,
          ...(patch.remindAt !== undefined
            ? { remind_at: patch.remindAt }
            : {}),
          ...(patch.done !== undefined ? { is_done: patch.done } : {}),
          remindAt: undefined,
          done: undefined,
        }),
      }),
    );
  }

  async dismissReminder(reminderId: string): Promise<void> {
    await this.request(
      `/api/reminders/${encodeURIComponent(reminderId)}/done`,
      { method: "PATCH" },
    );
  }

  async getCommunicationSummary(): Promise<CommunicationSummary> {
    const [email, whatsapp] = await Promise.allSettled([
      this.request("/api/email/unread"),
      this.request("/api/whatsapp/status"),
    ]);
    const unavailable: string[] = [];
    const emailData =
      email.status === "fulfilled" ? asRecord(email.value) : undefined;
    const whatsappData =
      whatsapp.status === "fulfilled" ? asRecord(whatsapp.value) : undefined;
    if (!emailData) unavailable.push("email");
    if (!whatsappData) unavailable.push("whatsapp");
    const channels = [
      emailData ? "Email" : "",
      whatsappData && Boolean(whatsappData.connected) ? "WhatsApp" : "",
    ].filter(Boolean);

    return {
      emailUnread: this.readCount(emailData, ["unread", "count", "total"]),
      whatsappUnread: this.readCount(whatsappData, [
        "unread",
        "unread_count",
      ]),
      connectedChannels: channels,
      unavailable,
    };
  }

  async getWorkflowSummary(): Promise<WorkflowSummary> {
    const workflows = asArray(await this.request("/api/workflows")).map(asRecord);
    const isEnabled = (item: Record<string, unknown>): boolean =>
      Boolean(item.is_enabled ?? item.enabled ?? item.active);
    return {
      active: workflows.filter(isEnabled).length,
      paused: workflows.filter((item) => !isEnabled(item)).length,
      recentRuns: workflows.reduce(
        (count, item) => count + this.readCount(item, ["run_count", "runs"]),
        0,
      ),
      failedRuns: workflows.reduce(
        (count, item) => count + this.readCount(item, ["failed_runs", "failures"]),
        0,
      ),
    };
  }

  async getSystemSummary(): Promise<SystemSummary> {
    const [health, devices, commands] = await Promise.allSettled([
      this.request("/api/health"),
      this.request("/api/devices"),
      this.request("/api/commands"),
    ]);
    const healthData =
      health.status === "fulfilled" ? asRecord(health.value) : {};
    const isHealthy =
      health.status === "fulfilled" &&
      !["error", "offline"].includes(String(healthData.status).toLowerCase());
    return {
      status: health.status === "rejected" ? "offline" : isHealthy ? "healthy" : "degraded",
      connectedDevices:
        devices.status === "fulfilled" ? asArray(devices.value).length : 0,
      pendingApprovals:
        commands.status === "fulfilled"
          ? asArray(commands.value).filter((item) => {
              const command = asRecord(item);
              return ["pending", "awaiting_approval"].includes(
                String(command.status),
              );
            }).length
          : 0,
      lastCheckedAt: new Date().toISOString(),
    };
  }

  async performConfirmedAction(
    action: ConfirmableAction,
  ): Promise<ConfirmedActionResult> {
    let path: string;
    switch (action.kind) {
      case "approve_command":
        path = `/api/commands/${encodeURIComponent(action.id)}/approve`;
        break;
      case "acknowledge_alert":
        path = `/api/alerts/triggered/${encodeURIComponent(action.id)}/acknowledge`;
        break;
      default:
        throw new GatewayError(
          `Unsupported confirmed action: ${String(action.kind)}`,
          400,
        );
    }
    const result = asRecord(
      await this.request(path, {
        method: "POST",
      }),
    );
    return {
      ok: result.ok !== false,
      message:
        typeof result.message === "string"
          ? result.message
          : `${action.label} completed.`,
      ...(result.data !== undefined ? { data: result.data } : {}),
    };
  }

  private get storage(): Storage {
    const storage = this.configuredStorage ?? globalThis.sessionStorage;
    if (!storage) {
      throw new GatewayError("Session storage is unavailable.", 0);
    }
    return storage;
  }

  private get fetcher(): typeof fetch {
    return (
      this.configuredFetch ??
      ((input: RequestInfo | URL, init?: RequestInit) =>
        globalThis.fetch(input, init))
    );
  }

  private previewSettings(): { apiUrl: string; token: string } {
    const apiUrl = (
      this.storage.getItem(API_URL_KEY) ?? DEFAULT_API_URL
    ).replace(/\/+$/, "");
    const token = this.storage.getItem(SESSION_KEY) ?? "";
    return { apiUrl, token };
  }

  private storeSession(value: unknown): void {
    if (typeof value !== "string" || !value) {
      throw new GatewayError("The server did not return a session token.", 0);
    }
    this.storage.setItem(SESSION_KEY, value);
  }

  private async request<T = unknown>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const response = await this.fetchResponse(path, init);
    if (!response.ok) {
      throw await this.errorFromResponse(response);
    }
    if (response.status === 204) {
      return undefined as T;
    }
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("json")) {
      return (await response.json()) as T;
    }
    return (await response.text()) as T;
  }

  private async fetchResponse(
    path: string,
    init: RequestInit,
  ): Promise<Response> {
    const { apiUrl, token } = this.previewSettings();
    const isFormData = init.body instanceof FormData;
    const headers: Record<string, string> = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
    new Headers(init.headers).forEach((value, key) => {
      headers[key] = value;
    });

    try {
      return await this.fetcher(`${apiUrl}${path}`, {
        ...init,
        headers,
      });
    } catch (error) {
      if (
        (error instanceof Error || error instanceof DOMException) &&
        error.name === "AbortError"
      ) {
        throw error;
      }
      if (error instanceof GatewayError) {
        throw error;
      }
      throw new GatewayError(
        error instanceof Error
          ? error.message
          : "The SALAR backend could not be reached.",
        0,
        error,
      );
    }
  }

  private async errorFromResponse(response: Response): Promise<GatewayError> {
    const contentType = response.headers.get("content-type") ?? "";
    let details: unknown;
    try {
      details = contentType.includes("json")
        ? await response.json()
        : await response.text();
    } catch {
      details = undefined;
    }
    const data = asRecord(details);
    const message =
      [data.detail, data.message, data.error].find(
        (value): value is string => typeof value === "string" && Boolean(value),
      ) ||
      (typeof details === "string" && details) ||
      `SALAR request failed with status ${response.status}.`;
    return new GatewayError(message, response.status, details);
  }

  private parseSseFrame(frame: string): ChatStreamEvent | null {
    const data = frame
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data || data === "[DONE]") {
      return null;
    }
    try {
      const event = asRecord(JSON.parse(data));
      const type = String(event.type);
      if (type === "token") {
        return { type, content: String(event.content ?? "") };
      }
      if (type === "tool_call") {
        return {
          type,
          tool: String(event.tool ?? ""),
          args: asRecord(event.args),
        };
      }
      if (type === "tool_result") {
        return {
          type,
          tool: String(event.tool ?? ""),
          result: event.result,
        };
      }
      if (type === "done") {
        return {
          type,
          messageId: String(event.messageId ?? event.message_id ?? ""),
          createdAt: String(event.createdAt ?? event.created_at ?? ""),
        };
      }
      if (type === "error") {
        return { type, message: String(event.message ?? "Streaming failed.") };
      }
      return null;
    } catch {
      return { type: "error", message: "SALAR sent an unreadable stream event." };
    }
  }

  private normalizeKnowledgeSource(value: unknown): SourceItem {
    const item = asRecord(value);
    return normalizeSource({
      ...item,
      id: item.id ?? item.document_id ?? item.chunk_id,
      kind: "knowledge",
      title: item.title ?? item.filename ?? item.document_filename,
      excerpt: item.excerpt ?? item.content ?? item.full_text,
      mime_type: item.mime_type ?? item.content_type,
    });
  }

  private normalizeAttention(value: unknown): AttentionItem {
    const item = asRecord(value);
    const severity = String(item.severity ?? item.level ?? "neutral");
    const id = String(item.id ?? "");
    const acknowledged = Boolean(item.acknowledged ?? item.is_acknowledged);
    return {
      id,
      title: String(item.title ?? item.name ?? "Needs attention"),
      detail: String(item.detail ?? item.message ?? ""),
      severity: ["neutral", "info", "warning", "critical"].includes(severity)
        ? (severity as AttentionItem["severity"])
        : "neutral",
      ...(!acknowledged && id
        ? {
            action: {
              id,
              kind: "acknowledge_alert" as const,
              label: "Acknowledge",
            },
          }
        : {}),
    };
  }

  private readCount(
    value: Record<string, unknown> | undefined,
    keys: string[],
  ): number {
    if (!value) {
      return 0;
    }
    for (const key of keys) {
      const count = Number(value[key]);
      if (Number.isFinite(count)) {
        return count;
      }
    }
    return 0;
  }
}
