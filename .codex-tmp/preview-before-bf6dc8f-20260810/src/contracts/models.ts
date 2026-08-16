export type AccessState =
  | "checking"
  | "paired"
  | "unpaired"
  | "offline"
  | "expired";

export type TaskStatus = "todo" | "in_progress" | "done" | "archived";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface ConversationSummary {
  id: string;
  title: string;
  preview: string;
  updatedAt: string;
  unreadCount: number;
}

export interface ChatMessage {
  id: string;
  conversationId: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
}

export interface TaskItem {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  dueAt: string | null;
}

export interface ReminderItem {
  id: string;
  title: string;
  message: string;
  remindAt: string;
  recurrence: "none" | "daily" | "weekly" | "monthly";
  done: boolean;
}

export interface CalendarItem {
  id: string;
  title: string;
  startsAt: string;
  endsAt: string | null;
  location: string;
  allDay: boolean;
}

export type ConfirmableActionKind =
  | "approve_command"
  | "acknowledge_alert";

export interface ConfirmableAction {
  id: string;
  kind: ConfirmableActionKind;
  label: string;
  description?: string;
  payload?: Record<string, unknown>;
}

export interface AttentionItem {
  id: string;
  title: string;
  detail: string;
  severity: "neutral" | "info" | "warning" | "critical";
  action?: ConfirmableAction;
}

export interface SourceItem {
  id: string;
  kind: "memory" | "document" | "knowledge" | "file";
  title: string;
  excerpt: string;
  updatedAt: string;
  mimeType?: string;
}

export interface BriefingSnapshot {
  generatedAt: string;
  tasks: TaskItem[];
  reminders: ReminderItem[];
  calendar: CalendarItem[];
  attention: AttentionItem[];
  conversations: ConversationSummary[];
  unavailable: string[];
}

export type ChatStreamEvent =
  | { type: "token"; content: string }
  | { type: "tool_call"; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; tool: string; result: unknown }
  | { type: "done"; messageId: string; createdAt: string }
  | { type: "error"; message: string };

export interface CommunicationSummary {
  emailUnread: number;
  whatsappUnread: number;
  connectedChannels: string[];
  unavailable: string[];
}

export interface WorkflowSummary {
  active: number;
  paused: number;
  recentRuns: number;
  failedRuns: number;
}

export interface SystemSummary {
  status: "healthy" | "degraded" | "offline";
  connectedDevices: number;
  pendingApprovals: number;
  lastCheckedAt: string;
}

export interface ConfirmedActionResult {
  ok: boolean;
  message: string;
  data?: unknown;
}

export interface PairingCredentials {
  code: string;
  name: string;
  platform: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface CreateTaskInput {
  title: string;
  description?: string;
  priority?: TaskPriority;
  dueAt?: string | null;
}

export type UpdateTaskInput = Partial<Omit<TaskItem, "id">>;

export interface CreateReminderInput {
  title: string;
  message?: string;
  remindAt: string;
  recurrence?: ReminderItem["recurrence"];
}

export type UpdateReminderInput = Partial<Omit<ReminderItem, "id">>;
