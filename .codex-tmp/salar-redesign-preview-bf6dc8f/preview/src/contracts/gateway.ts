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
} from "./models";

export interface SalarGateway {
  getAccessState(): Promise<AccessState>;
  pair(credentials: PairingCredentials): Promise<AccessState>;
  login(credentials: LoginCredentials): Promise<AccessState>;

  listConversations(): Promise<ConversationSummary[]>;
  getConversation(conversationId: string): Promise<ChatMessage[]>;
  createConversation(title?: string): Promise<ConversationSummary>;
  streamConversation(
    conversationId: string,
    message: string,
    signal?: AbortSignal,
  ): AsyncIterable<ChatStreamEvent>;

  listTasks(): Promise<TaskItem[]>;
  listReminders(): Promise<ReminderItem[]>;
  listCalendar(): Promise<CalendarItem[]>;
  listAttention(): Promise<AttentionItem[]>;
  getBriefing(): Promise<BriefingSnapshot>;
  listSources(): Promise<SourceItem[]>;
  searchSources(query: string): Promise<SourceItem[]>;
  uploadSource(file: File): Promise<SourceItem>;

  createTask(input: CreateTaskInput): Promise<TaskItem>;
  updateTask(taskId: string, patch: UpdateTaskInput): Promise<TaskItem>;
  deleteTask(taskId: string): Promise<void>;

  createReminder(input: CreateReminderInput): Promise<ReminderItem>;
  updateReminder(
    reminderId: string,
    patch: UpdateReminderInput,
  ): Promise<ReminderItem>;
  dismissReminder(reminderId: string): Promise<void>;

  getCommunicationSummary(): Promise<CommunicationSummary>;
  getWorkflowSummary(): Promise<WorkflowSummary>;
  getSystemSummary(): Promise<SystemSummary>;
  performConfirmedAction(
    action: ConfirmableAction,
  ): Promise<ConfirmedActionResult>;
}
