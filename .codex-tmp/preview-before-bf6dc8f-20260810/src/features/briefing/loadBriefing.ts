import type { SalarGateway } from "../../contracts/gateway";
import type {
  AttentionItem,
  BriefingSnapshot,
  CalendarItem,
  ConversationSummary,
  ReminderItem,
  TaskItem,
} from "../../contracts/models";

export type BriefingSourceGateway = Pick<
  SalarGateway,
  | "listTasks"
  | "listReminders"
  | "listCalendar"
  | "listAttention"
  | "listConversations"
>;

const sources = [
  "tasks",
  "reminders",
  "calendar",
  "attention",
  "conversations",
] as const;

export async function loadBriefing(
  gateway: BriefingSourceGateway,
  now: () => Date = () => new Date(),
): Promise<BriefingSnapshot> {
  const results = await Promise.allSettled([
    gateway.listTasks(),
    gateway.listReminders(),
    gateway.listCalendar(),
    gateway.listAttention(),
    gateway.listConversations(),
  ]);
  const unavailable: string[] = [];

  function read<T>(index: number): T[] {
    const result = results[index];
    if (!result || result.status === "rejected") {
      unavailable.push(sources[index] ?? "unknown");
      return [];
    }
    return result.value as T[];
  }

  return {
    generatedAt: now().toISOString(),
    tasks: read<TaskItem>(0),
    reminders: read<ReminderItem>(1),
    calendar: read<CalendarItem>(2),
    attention: read<AttentionItem>(3),
    conversations: read<ConversationSummary>(4),
    unavailable,
  };
}

export type BriefingEntry =
  | { id: string; kind: "task"; item: TaskItem }
  | { id: string; kind: "reminder"; item: ReminderItem }
  | { id: string; kind: "calendar"; item: CalendarItem }
  | { id: string; kind: "attention"; item: AttentionItem }
  | { id: string; kind: "conversation"; item: ConversationSummary };

export interface BriefingGroups {
  today: BriefingEntry[];
  needsYou: BriefingEntry[];
  inMotion: BriefingEntry[];
}

type TodayEntry = Extract<
  BriefingEntry,
  { kind: "calendar" | "reminder" }
>;

const severityRank: Record<AttentionItem["severity"], number> = {
  critical: 4,
  warning: 3,
  info: 2,
  neutral: 1,
};

const priorityRank: Record<TaskItem["priority"], number> = {
  urgent: 4,
  high: 3,
  medium: 2,
  low: 1,
};

function onUtcDay(value: string, now: Date): boolean {
  const date = new Date(value);
  return (
    date.getUTCFullYear() === now.getUTCFullYear() &&
    date.getUTCMonth() === now.getUTCMonth() &&
    date.getUTCDate() === now.getUTCDate()
  );
}

export function groupBriefing(
  snapshot: BriefingSnapshot,
  now: Date,
): BriefingGroups {
  const today: TodayEntry[] = [
    ...snapshot.calendar
      .filter((item) => onUtcDay(item.startsAt, now))
      .map(
        (item): TodayEntry => ({ id: item.id, kind: "calendar", item }),
      ),
    ...snapshot.reminders
      .filter((item) => !item.done && onUtcDay(item.remindAt, now))
      .map(
        (item): TodayEntry => ({ id: item.id, kind: "reminder", item }),
      ),
  ].sort((left, right) => {
    const leftAt =
      left.kind === "calendar" ? left.item.startsAt : left.item.remindAt;
    const rightAt =
      right.kind === "calendar" ? right.item.startsAt : right.item.remindAt;
    return leftAt.localeCompare(rightAt) || left.id.localeCompare(right.id);
  });

  const needsYou: BriefingEntry[] = snapshot.attention
    .map((item) => ({ id: item.id, kind: "attention" as const, item }))
    .sort(
      (left, right) =>
        severityRank[right.item.severity] - severityRank[left.item.severity] ||
        left.id.localeCompare(right.id),
    );

  const inProgress: BriefingEntry[] = snapshot.tasks
    .filter((item) => item.status === "in_progress")
    .map((item) => ({ id: item.id, kind: "task" as const, item }))
    .sort(
      (left, right) =>
        priorityRank[right.item.priority] - priorityRank[left.item.priority] ||
        (left.item.dueAt ?? "9999").localeCompare(
          right.item.dueAt ?? "9999",
        ) ||
        left.id.localeCompare(right.id),
    );
  const recentConversations: BriefingEntry[] = snapshot.conversations
    .map((item) => ({ id: item.id, kind: "conversation" as const, item }))
    .sort(
      (left, right) =>
        right.item.updatedAt.localeCompare(left.item.updatedAt) ||
        left.id.localeCompare(right.id),
    );

  return {
    today,
    needsYou,
    inMotion: [...inProgress, ...recentConversations],
  };
}
