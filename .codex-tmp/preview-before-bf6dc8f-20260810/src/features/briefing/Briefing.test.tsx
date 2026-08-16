import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SalarGateway } from "../../contracts/gateway";
import { FixtureGateway } from "../../data/FixtureGateway";
import { createFixtureData } from "../../data/fixtures";
import { Briefing } from "./Briefing";

afterEach(() => {
  cleanup();
});

describe("Briefing", () => {
  it("shows a warm loading state before the sources settle", () => {
    const never = new Promise<never>(() => undefined);
    const gateway = {
      listTasks: () => never,
      listReminders: () => never,
      listCalendar: () => never,
      listAttention: () => never,
      listConversations: () => never,
      dismissReminder: vi.fn(),
      updateTask: vi.fn(),
      performConfirmedAction: vi.fn(),
    } as Pick<
      SalarGateway,
      | "listTasks"
      | "listReminders"
      | "listCalendar"
      | "listAttention"
      | "listConversations"
      | "dismissReminder"
      | "updateTask"
      | "performConfirmedAction"
    >;

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Gathering what matters",
    );
    expect(screen.getAllByTestId("briefing-skeleton")).toHaveLength(3);
  });

  it("renders the editorial briefing sections with context actions", async () => {
    const gateway = new FixtureGateway();
    const onDiscuss = vi.fn();

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
        onDiscuss={onDiscuss}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Good afternoon." }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "One decision needs you, and your focused work is already moving.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Needs you" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "In motion" }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getAllByRole("button", { name: "Discuss with SALAR" })[0],
    );
    expect(onDiscuss).toHaveBeenCalledWith(
      expect.objectContaining({ id: "reminder-water" }),
    );
  });

  it("keeps useful content visible and names unavailable sources", async () => {
    const gateway = new FixtureGateway() as SalarGateway;
    vi.spyOn(gateway, "listCalendar").mockRejectedValue(
      new Error("calendar offline"),
    );

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    expect(
      await screen.findByText("Calendar is unavailable right now."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Calendar is unavailable, so this view may be incomplete\./,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Review the launch brief")).toBeInTheDocument();
  });

  it("does not describe the day as quiet when every source is unavailable", async () => {
    const unavailable = () => Promise.reject(new Error("offline"));
    const gateway = {
      listTasks: unavailable,
      listReminders: unavailable,
      listCalendar: unavailable,
      listAttention: unavailable,
      listConversations: unavailable,
      dismissReminder: vi.fn(),
      updateTask: vi.fn(),
      performConfirmedAction: vi.fn(),
    } as unknown as SalarGateway;

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    expect(
      await screen.findByText(
        "I couldn\u2019t reach your connected sources yet, so I won\u2019t guess at your day.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Your day is quiet/),
    ).not.toBeInTheDocument();
  });

  it("does not claim no decisions are waiting when attention is unavailable", async () => {
    const gateway = new FixtureGateway() as SalarGateway;
    vi.spyOn(gateway, "listAttention").mockRejectedValue(
      new Error("attention offline"),
    );

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    expect(
      await screen.findByText(
        "Your focused work is moving. Attention is unavailable, so I can\u2019t verify whether a decision is waiting.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/no new decisions waiting/i),
    ).not.toBeInTheDocument();
  });

  it("does not call the day quiet when a relevant source is unavailable", async () => {
    const seed = createFixtureData();
    seed.tasks = [];
    seed.reminders = [];
    seed.calendar = [];
    seed.attention = [];
    seed.conversations = [];
    const gateway = new FixtureGateway(seed) as SalarGateway;
    vi.spyOn(gateway, "listCalendar").mockRejectedValue(
      new Error("calendar offline"),
    );

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    expect(
      await screen.findByText(
        "Calendar is unavailable, so I can\u2019t call the day clear yet.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Some context is out of reach." }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Your day is quiet/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/connected sources are quiet/i),
    ).not.toBeInTheDocument();
  });

  it("offers a calm empty state when there is nothing to surface", async () => {
    const seed = createFixtureData();
    seed.tasks = [];
    seed.reminders = [];
    seed.calendar = [];
    seed.attention = [];
    seed.conversations = [];

    render(
      <Briefing
        gateway={new FixtureGateway(seed)}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    expect(
      await screen.findByRole("heading", { name: "Nothing needs your hand." }),
    ).toBeInTheDocument();
  });

  it("runs a reminder's primary action and refreshes the briefing", async () => {
    const gateway = new FixtureGateway();
    const dismiss = vi.spyOn(gateway, "dismissReminder");

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Mark Take a real break done" }),
    );

    expect(dismiss).toHaveBeenCalledWith("reminder-water");
    expect(
      await screen.findByText("Take a real break is complete."),
    ).toBeInTheDocument();
  });

  it("requires explicit confirmation before a confirmable attention action", async () => {
    const gateway = new FixtureGateway();
    const perform = vi.spyOn(gateway, "performConfirmedAction");

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Review and send" }),
    );

    expect(perform).not.toHaveBeenCalled();
    expect(
      screen.getByRole("dialog", { name: "Confirm Review and send" }),
    ).toHaveTextContent("Send the prepared follow-up to the project partner.");
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "A message is ready to send",
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Confirm Review and send" }),
    );

    expect(perform).toHaveBeenCalledOnce();
  });

  it("announces manual refresh progress and completion", async () => {
    const gateway = new FixtureGateway();
    let releaseRefresh: (() => void) | undefined;
    const pendingRefresh = new Promise<void>((resolve) => {
      releaseRefresh = resolve;
    });
    const listTasks = vi.spyOn(gateway, "listTasks");
    listTasks.mockResolvedValueOnce(await gateway.listTasks());
    listTasks.mockImplementationOnce(async () => {
      await pendingRefresh;
      return [];
    });

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Refresh" }));

    expect(screen.getByRole("status")).toHaveTextContent(
      "Refreshing your briefing\u2026",
    );

    releaseRefresh?.();

    expect(await screen.findByText("Briefing updated.")).toBeInTheDocument();
  });
});
