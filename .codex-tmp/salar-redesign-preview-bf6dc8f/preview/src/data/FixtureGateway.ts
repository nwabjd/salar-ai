import type { SalarGateway } from "../contracts/gateway";
import type {
  AccessState,
  BriefingSnapshot,
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
import { createFixtureData, FIXTURE_NOW, type FixtureData } from "./fixtures";

function copy<T>(value: T): T {
  return structuredClone(value);
}

export class FixtureGateway implements SalarGateway {
  private accessState: AccessState = "paired";
  private readonly store: FixtureData;
  private sequence = 0;

  constructor(seed: FixtureData = createFixtureData()) {
    this.store = copy(seed);
  }

  async getAccessState(): Promise<AccessState> {
    return this.accessState;
  }

  async pair(credentials: PairingCredentials): Promise<AccessState> {
    this.accessState = credentials.code.trim() ? "paired" : "unpaired";
    return this.accessState;
  }

  async login(credentials: LoginCredentials): Promise<AccessState> {
    this.accessState =
      credentials.email.trim() && credentials.password ? "paired" : "unpaired";
    return this.accessState;
  }

  async listConversations(): Promise<ConversationSummary[]> {
    return copy(this.store.conversations);
  }

  async getConversation(conversationId: string): Promise<ChatMessage[]> {
    return copy(this.store.messages[conversationId] ?? []);
  }

  async createConversation(title = "New conversation"): Promise<ConversationSummary> {
    const id = this.nextId("conversation");
    const conversation: ConversationSummary = {
      id,
      title: title.trim() || "New conversation",
      preview: "",
      updatedAt: FIXTURE_NOW,
      unreadCount: 0,
    };
    this.store.conversations.unshift(conversation);
    this.store.messages[id] = [];
    return copy(conversation);
  }

  async *streamConversation(
    conversationId: string,
    message: string,
    signal?: AbortSignal,
  ): AsyncIterable<ChatStreamEvent> {
    if (signal?.aborted) {
      return;
    }

    const userMessage: ChatMessage = {
      id: this.nextId("message"),
      conversationId,
      role: "user",
      content: message,
      createdAt: FIXTURE_NOW,
    };
    const reply =
      "I’m with you. I’ve gathered the relevant context and kept the next step clear.";
    const assistantMessage: ChatMessage = {
      id: this.nextId("message"),
      conversationId,
      role: "assistant",
      content: reply,
      createdAt: FIXTURE_NOW,
    };
    const thread = (this.store.messages[conversationId] ??= []);
    thread.push(userMessage);

    for (const content of [
      "I’m with you. ",
      "I’ve gathered the relevant context ",
      "and kept the next step clear.",
    ]) {
      if (signal?.aborted) {
        return;
      }
      yield { type: "token", content };
    }

    thread.push(assistantMessage);
    const conversation = this.store.conversations.find(
      (item) => item.id === conversationId,
    );
    if (conversation) {
      conversation.preview = reply;
      conversation.updatedAt = FIXTURE_NOW;
    }
    yield {
      type: "done",
      messageId: assistantMessage.id,
      createdAt: assistantMessage.createdAt,
    };
  }

  async getBriefing(): Promise<BriefingSnapshot> {
    return copy({
      generatedAt: FIXTURE_NOW,
      tasks: this.store.tasks,
      reminders: this.store.reminders,
      calendar: this.store.calendar,
      attention: this.store.attention,
      conversations: this.store.conversations,
      unavailable: [],
    });
  }

  async listTasks(): Promise<TaskItem[]> {
    return copy(this.store.tasks);
  }

  async listReminders(): Promise<ReminderItem[]> {
    return copy(this.store.reminders);
  }

  async listCalendar() {
    return copy(this.store.calendar);
  }

  async listAttention() {
    return copy(this.store.attention);
  }

  async listSources(): Promise<SourceItem[]> {
    return copy(this.store.sources);
  }

  async searchSources(query: string): Promise<SourceItem[]> {
    const needle = query.trim().toLocaleLowerCase();
    if (!needle) {
      return this.listSources();
    }
    return copy(
      this.store.sources.filter((source) =>
        `${source.title} ${source.excerpt}`.toLocaleLowerCase().includes(needle),
      ),
    );
  }

  async uploadSource(file: File): Promise<SourceItem> {
    const source: SourceItem = {
      id: this.nextId("source"),
      kind: "file",
      title: file.name,
      excerpt: `${file.type || "File"} · ${file.size} bytes`,
      updatedAt: FIXTURE_NOW,
      ...(file.type ? { mimeType: file.type } : {}),
    };
    this.store.sources.unshift(source);
    return copy(source);
  }

  async createTask(input: CreateTaskInput): Promise<TaskItem> {
    const task: TaskItem = {
      id: this.nextId("task"),
      title: input.title,
      description: input.description ?? "",
      status: "todo",
      priority: input.priority ?? "medium",
      dueAt: input.dueAt ?? null,
    };
    this.store.tasks.push(task);
    return copy(task);
  }

  async updateTask(taskId: string, patch: UpdateTaskInput): Promise<TaskItem> {
    const task = this.requireItem(this.store.tasks, taskId, "Task");
    Object.assign(task, patch);
    return copy(task);
  }

  async deleteTask(taskId: string): Promise<void> {
    const index = this.store.tasks.findIndex((task) => task.id === taskId);
    if (index < 0) {
      throw new Error("Task not found");
    }
    this.store.tasks.splice(index, 1);
  }

  async createReminder(input: CreateReminderInput): Promise<ReminderItem> {
    const reminder: ReminderItem = {
      id: this.nextId("reminder"),
      title: input.title,
      message: input.message ?? "",
      remindAt: input.remindAt,
      recurrence: input.recurrence ?? "none",
      done: false,
    };
    this.store.reminders.push(reminder);
    return copy(reminder);
  }

  async updateReminder(
    reminderId: string,
    patch: UpdateReminderInput,
  ): Promise<ReminderItem> {
    const reminder = this.requireItem(
      this.store.reminders,
      reminderId,
      "Reminder",
    );
    Object.assign(reminder, patch);
    return copy(reminder);
  }

  async dismissReminder(reminderId: string): Promise<void> {
    const reminder = this.requireItem(
      this.store.reminders,
      reminderId,
      "Reminder",
    );
    reminder.done = true;
  }

  async getCommunicationSummary(): Promise<CommunicationSummary> {
    return copy(this.store.communication);
  }

  async getWorkflowSummary(): Promise<WorkflowSummary> {
    return copy(this.store.workflows);
  }

  async getSystemSummary(): Promise<SystemSummary> {
    return copy(this.store.system);
  }

  async performConfirmedAction(
    action: ConfirmableAction,
  ): Promise<ConfirmedActionResult> {
    this.store.attention = this.store.attention.filter(
      (item) => item.action?.id !== action.id,
    );
    this.store.system.pendingApprovals = this.store.attention.filter(
      (item) => item.action,
    ).length;
    return {
      ok: true,
      message: `${action.label} completed in the preview.`,
    };
  }

  private nextId(prefix: string): string {
    this.sequence += 1;
    return `${prefix}-fixture-${this.sequence}`;
  }

  private requireItem<T extends { id: string }>(
    items: T[],
    id: string,
    label: string,
  ): T {
    const item = items.find((candidate) => candidate.id === id);
    if (!item) {
      throw new Error(`${label} not found`);
    }
    return item;
  }
}
