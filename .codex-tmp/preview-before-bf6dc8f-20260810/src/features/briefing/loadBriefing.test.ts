import { describe, expect, it, vi } from "vitest";

import type {
  AttentionItem,
  CalendarItem,
  ConversationSummary,
  ReminderItem,
  TaskItem,
} from "../../contracts/models";
import {
  groupBriefing,
  loadBriefing,
  type BriefingSourceGateway,
} from "./loadBriefing";

const tasks: TaskItem[] = [
  {
    id: "task-later",
    title: "Prepare tomorrow",
    description: "",
    status: "todo",
    priority: "medium",
    dueAt: "2026-07-30T10:00:00.000Z",
  },
  {
    id: "task-focus",
    title: "Finish the brief",
    description: "",
    status: "in_progress",
    priority: "high",
    dueAt: "2026-07-29T17:00:00.000Z",
  },
];

const reminders: ReminderItem[] = [
  {
    id: "reminder-late",
    title: "Take a break",
    message: "",
    remindAt: "2026-07-29T16:30:00.000Z",
    recurrence: "none",
    done: false,
  },
  {
    id: "reminder-early",
    title: "Check the room",
    message: "",
    remindAt: "2026-07-29T14:00:00.000Z",
    recurrence: "none",
    done: false,
  },
];

const calendar: CalendarItem[] = [
  {
    id: "event-late",
    title: "Planning",
    startsAt: "2026-07-29T19:00:00.000Z",
    endsAt: null,
    location: "",
    allDay: false,
  },
  {
    id: "event-early",
    title: "Studio check-in",
    startsAt: "2026-07-29T15:00:00.000Z",
    endsAt: null,
    location: "",
    allDay: false,
  },
];

const attention: AttentionItem[] = [
  {
    id: "attention-low",
    title: "For your awareness",
    detail: "",
    severity: "info",
  },
  {
    id: "attention-high",
    title: "Approval waiting",
    detail: "",
    severity: "critical",
  },
];

const conversations: ConversationSummary[] = [
  {
    id: "conversation-old",
    title: "Yesterday",
    preview: "",
    updatedAt: "2026-07-28T17:00:00.000Z",
    unreadCount: 0,
  },
  {
    id: "conversation-new",
    title: "Morning reset",
    preview: "",
    updatedAt: "2026-07-29T15:20:00.000Z",
    unreadCount: 0,
  },
];

function sourceGateway(
  overrides: Partial<BriefingSourceGateway> = {},
): BriefingSourceGateway {
  return {
    listTasks: vi.fn().mockResolvedValue(tasks),
    listReminders: vi.fn().mockResolvedValue(reminders),
    listCalendar: vi.fn().mockResolvedValue(calendar),
    listAttention: vi.fn().mockResolvedValue(attention),
    listConversations: vi.fn().mockResolvedValue(conversations),
    ...overrides,
  };
}

describe("loadBriefing", () => {
  it("aggregates each briefing source independently", async () => {
    const gateway = sourceGateway();

    const snapshot = await loadBriefing(
      gateway,
      () => new Date("2026-07-29T15:30:00.000Z"),
    );

    expect(snapshot).toEqual({
      generatedAt: "2026-07-29T15:30:00.000Z",
      tasks,
      reminders,
      calendar,
      attention,
      conversations,
      unavailable: [],
    });
    expect(gateway.listTasks).toHaveBeenCalledOnce();
    expect(gateway.listReminders).toHaveBeenCalledOnce();
    expect(gateway.listCalendar).toHaveBeenCalledOnce();
    expect(gateway.listAttention).toHaveBeenCalledOnce();
    expect(gateway.listConversations).toHaveBeenCalledOnce();
  });

  it("keeps successful task data when calendar is unavailable", async () => {
    const gateway = sourceGateway({
      listCalendar: vi.fn().mockRejectedValue(new Error("calendar offline")),
    });

    const snapshot = await loadBriefing(gateway);

    expect(snapshot.tasks).toHaveLength(2);
    expect(snapshot.calendar).toEqual([]);
    expect(snapshot.unavailable).toEqual(["calendar"]);
  });
});

describe("groupBriefing", () => {
  it("orders Today, Needs you, and In motion deterministically", () => {
    const grouped = groupBriefing(
      {
        generatedAt: "2026-07-29T15:30:00.000Z",
        tasks,
        reminders,
        calendar,
        attention,
        conversations,
        unavailable: [],
      },
      new Date("2026-07-29T15:30:00.000Z"),
    );

    expect(grouped.today.map((item) => item.id)).toEqual([
      "reminder-early",
      "event-early",
      "reminder-late",
      "event-late",
    ]);
    expect(grouped.needsYou.map((item) => item.id)).toEqual([
      "attention-high",
      "attention-low",
    ]);
    expect(grouped.inMotion.map((item) => item.id)).toEqual([
      "task-focus",
      "conversation-new",
      "conversation-old",
    ]);
  });
});
