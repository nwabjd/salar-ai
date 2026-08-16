import type {
  AttentionItem,
  CalendarItem,
  ChatMessage,
  CommunicationSummary,
  ConversationSummary,
  ReminderItem,
  SourceItem,
  SystemSummary,
  TaskItem,
  WorkflowSummary,
} from "../contracts/models";

export const FIXTURE_NOW = "2026-07-29T15:30:00.000Z";

export interface FixtureData {
  conversations: ConversationSummary[];
  messages: Record<string, ChatMessage[]>;
  tasks: TaskItem[];
  reminders: ReminderItem[];
  calendar: CalendarItem[];
  attention: AttentionItem[];
  sources: SourceItem[];
  communication: CommunicationSummary;
  workflows: WorkflowSummary;
  system: SystemSummary;
}

export function createFixtureData(): FixtureData {
  return {
    conversations: [
      {
        id: "conversation-morning",
        title: "Morning reset",
        preview: "We made room for the work that matters today.",
        updatedAt: "2026-07-29T15:24:00.000Z",
        unreadCount: 0,
      },
      {
        id: "conversation-studio",
        title: "Studio planning",
        preview: "The launch brief is ready for your review.",
        updatedAt: "2026-07-28T22:10:00.000Z",
        unreadCount: 1,
      },
    ],
    messages: {
      "conversation-morning": [
        {
          id: "message-morning-1",
          conversationId: "conversation-morning",
          role: "assistant",
          content:
            "Good morning. You have a clear first hour, then one planning call. I kept the brief and yesterday's notes close.",
          createdAt: "2026-07-29T15:20:00.000Z",
        },
      ],
      "conversation-studio": [
        {
          id: "message-studio-1",
          conversationId: "conversation-studio",
          role: "assistant",
          content:
            "I gathered the launch notes into one brief and flagged the two decisions still waiting on you.",
          createdAt: "2026-07-28T22:10:00.000Z",
        },
      ],
    },
    tasks: [
      {
        id: "task-brief",
        title: "Review the launch brief",
        description: "Resolve audience and rollout timing before the team sync.",
        status: "in_progress",
        priority: "high",
        dueAt: "2026-07-29T18:00:00.000Z",
      },
      {
        id: "task-follow-up",
        title: "Send the partner follow-up",
        description: "Share the agreed next steps and the revised milestone.",
        status: "todo",
        priority: "medium",
        dueAt: "2026-07-30T17:00:00.000Z",
      },
    ],
    reminders: [
      {
        id: "reminder-water",
        title: "Take a real break",
        message: "Step away before the planning call.",
        remindAt: "2026-07-29T16:30:00.000Z",
        recurrence: "none",
        done: false,
      },
    ],
    calendar: [
      {
        id: "calendar-planning",
        title: "Product planning",
        startsAt: "2026-07-29T19:00:00.000Z",
        endsAt: "2026-07-29T19:45:00.000Z",
        location: "Studio room",
        allDay: false,
      },
    ],
    attention: [
      {
        id: "attention-approval",
        title: "A prepared message needs review",
        detail: "A draft follow-up was detected and is waiting for your review.",
        severity: "warning",
        action: {
          id: "send-partner-follow-up",
          kind: "acknowledge_alert",
          label: "Acknowledge alert",
          description:
            "Acknowledge this alert after reviewing it. No message will be sent.",
        },
      },
    ],
    sources: [
      {
        id: "source-launch-brief",
        kind: "document",
        title: "Launch brief",
        excerpt: "Audience, narrative, rollout sequence, and open decisions.",
        updatedAt: "2026-07-29T14:40:00.000Z",
        mimeType: "text/markdown",
      },
      {
        id: "source-working-style",
        kind: "memory",
        title: "Working rhythm",
        excerpt: "Protect the first hour for focused work when possible.",
        updatedAt: "2026-07-27T17:15:00.000Z",
      },
      {
        id: "source-research",
        kind: "knowledge",
        title: "Customer research synthesis",
        excerpt: "People value a calm daily view more than another dashboard.",
        updatedAt: "2026-07-26T20:00:00.000Z",
      },
    ],
    communication: {
      emailUnread: 4,
      whatsappUnread: 1,
      connectedChannels: ["Email", "WhatsApp"],
      unavailable: [],
    },
    workflows: {
      active: 3,
      paused: 1,
      recentRuns: 8,
      failedRuns: 0,
    },
    system: {
      status: "healthy",
      connectedDevices: 2,
      pendingApprovals: 1,
      lastCheckedAt: FIXTURE_NOW,
    },
  };
}
