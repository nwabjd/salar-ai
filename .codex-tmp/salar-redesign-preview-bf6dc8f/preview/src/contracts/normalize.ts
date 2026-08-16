import type {
  CalendarItem,
  ChatMessage,
  ConversationSummary,
  ReminderItem,
  SourceItem,
  TaskItem,
  TaskPriority,
  TaskStatus,
} from "./models";

type UnknownRecord = Record<string, unknown>;

const TASK_STATUSES = new Set<TaskStatus>([
  "todo",
  "in_progress",
  "done",
  "archived",
]);
const TASK_PRIORITIES = new Set<TaskPriority>([
  "low",
  "medium",
  "high",
  "urgent",
]);

function record(value: unknown): UnknownRecord {
  return value !== null && typeof value === "object"
    ? (value as UnknownRecord)
    : {};
}

function text(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function identifier(value: unknown): string {
  return typeof value === "string" || typeof value === "number"
    ? String(value)
    : "";
}

function nullableText(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export function normalizeTask(value: unknown): TaskItem {
  const input = record(value);
  const status = text(input.status) as TaskStatus;
  const priority = text(input.priority) as TaskPriority;

  return {
    id: identifier(input.id),
    title: text(input.title, "Untitled task"),
    description: text(input.description),
    status: TASK_STATUSES.has(status) ? status : "todo",
    priority: TASK_PRIORITIES.has(priority) ? priority : "medium",
    dueAt: nullableText(input.dueAt ?? input.due_at ?? input.due_date),
  };
}

export function normalizeReminder(value: unknown): ReminderItem {
  const input = record(value);
  const recurrence = text(input.recurrence);
  const allowed = new Set(["none", "daily", "weekly", "monthly"]);

  return {
    id: identifier(input.id),
    title: text(input.title, "Reminder"),
    message: text(input.message),
    remindAt: text(input.remindAt ?? input.remind_at),
    recurrence: allowed.has(recurrence)
      ? (recurrence as ReminderItem["recurrence"])
      : "none",
    done: Boolean(input.done ?? input.is_done),
  };
}

export function normalizeCalendarItem(value: unknown): CalendarItem {
  const input = record(value);
  return {
    id: identifier(input.id ?? input.uid),
    title: text(input.title ?? input.summary, "Untitled event"),
    startsAt: text(input.startsAt ?? input.start ?? input.start_at),
    endsAt: nullableText(input.endsAt ?? input.end ?? input.end_at),
    location: text(input.location),
    allDay: Boolean(input.allDay ?? input.all_day),
  };
}

export function normalizeConversation(value: unknown): ConversationSummary {
  const input = record(value);
  return {
    id: identifier(input.id),
    title: text(input.title, "New conversation"),
    preview: text(input.preview ?? input.last_message),
    updatedAt: text(input.updatedAt ?? input.updated_at ?? input.created_at),
    unreadCount: Number(input.unreadCount ?? input.unread_count ?? 0) || 0,
  };
}

export function normalizeMessage(
  value: unknown,
  conversationId = "",
): ChatMessage {
  const input = record(value);
  const role = text(input.role);
  return {
    id: identifier(input.id),
    conversationId: identifier(
      input.conversationId ?? input.conversation_id ?? conversationId,
    ),
    role:
      role === "user" || role === "assistant" || role === "system"
        ? role
        : "assistant",
    content: text(input.content),
    createdAt: text(input.createdAt ?? input.created_at),
  };
}

export function normalizeSource(value: unknown): SourceItem {
  const input = record(value);
  const kind = text(input.kind ?? input.type);
  const allowed = new Set(["memory", "document", "knowledge", "file"]);
  return {
    id: identifier(input.id),
    kind: allowed.has(kind) ? (kind as SourceItem["kind"]) : "document",
    title: text(input.title ?? input.filename ?? input.name, "Untitled source"),
    excerpt: text(input.excerpt ?? input.content ?? input.text),
    updatedAt: text(input.updatedAt ?? input.updated_at ?? input.created_at),
    ...(typeof input.mimeType === "string" || typeof input.mime_type === "string"
      ? { mimeType: text(input.mimeType ?? input.mime_type) }
      : {}),
  };
}

export function asRecord(value: unknown): UnknownRecord {
  return record(value);
}

export function asArray(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return value;
  }
  const input = record(value);
  for (const key of ["items", "results", "data", "events", "alerts"]) {
    if (Array.isArray(input[key])) {
      return input[key] as unknown[];
    }
  }
  return [];
}
