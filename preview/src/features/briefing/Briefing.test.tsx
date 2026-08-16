import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SalarGateway } from "../../contracts/gateway";
import { FixtureGateway } from "../../data/FixtureGateway";
import { createFixtureData } from "../../data/fixtures";
import { Briefing } from "./Briefing";

afterEach(() => {
  cleanup();
});

describe("Briefing", () => {
  it("uses truthful acknowledgement copy for the fixture alert", async () => {
    render(
      <Briefing
        gateway={new FixtureGateway()}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    const action = await screen.findByRole("button", {
      name: "Acknowledge alert",
    });
    expect(action).toBeInTheDocument();
    expect(screen.queryByText(/Send the prepared follow-up/i)).toBeNull();
  });

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
        "I couldn’t reach your connected sources yet, so I won’t guess at your day.",
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
        "Your focused work is moving. Attention is unavailable, so I can’t verify whether a decision is waiting.",
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
        "Calendar is unavailable, so I can’t call the day clear yet.",
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

  it("announces reminder mutation failure and leaves the action available", async () => {
    const gateway = new FixtureGateway();
    vi.spyOn(gateway, "dismissReminder").mockRejectedValueOnce(
      new Error("offline"),
    );

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Mark Take a real break done" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "I couldn’t verify whether Take a real break completed. I refreshed the briefing before retrying.",
    );
    expect(screen.queryByText(/Nothing changed/i)).toBeNull();
    expect(
      screen.getByRole("button", { name: "Mark Take a real break done" }),
    ).toBeEnabled();
  });

  it("announces task mutation failure and leaves the action available", async () => {
    const gateway = new FixtureGateway();
    vi.spyOn(gateway, "updateTask").mockRejectedValueOnce(new Error("offline"));

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Mark Review the launch brief complete",
      }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "I couldn’t verify whether Review the launch brief completed. I refreshed the briefing before retrying.",
    );
    expect(screen.queryByText(/Nothing changed/i)).toBeNull();
    expect(
      screen.getByRole("button", {
        name: "Mark Review the launch brief complete",
      }),
    ).toBeEnabled();
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

    const opener = await screen.findByRole("button", {
      name: "Acknowledge alert",
    });
    opener.focus();
    fireEvent.click(opener);

    expect(perform).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog", {
      name: "Confirm Acknowledge alert",
    });
    expect(dialog).toHaveTextContent(
      "Acknowledge this alert after reviewing it. No message will be sent.",
    );
    expect(dialog).toHaveTextContent("A prepared message needs review");
    expect(document.body).toHaveStyle({ overflow: "hidden" });
    expect(document.querySelector(".briefing__surface")).toHaveAttribute(
      "inert",
    );
    expect(document.querySelector(".briefing__surface")).toHaveAttribute(
      "aria-hidden",
      "true",
    );

    const cancel = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", {
      name: "Confirm Acknowledge alert",
    });
    await waitFor(() => expect(confirm).toHaveFocus());
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(cancel).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(confirm).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    await waitFor(() => expect(opener).toHaveFocus());
    expect(document.body).not.toHaveStyle({ overflow: "hidden" });

    fireEvent.click(opener);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(opener).toHaveFocus());

    fireEvent.click(opener);
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm Acknowledge alert" }),
    );

    expect(perform).toHaveBeenCalledOnce();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByRole("button", { name: "Refresh" })).toHaveFocus();
  });

  it("keeps failed confirmation open for an accessible retry", async () => {
    const gateway = new FixtureGateway();
    const perform = vi
      .spyOn(gateway, "performConfirmedAction")
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ok: true, message: "Alert acknowledged." });

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Acknowledge alert" }),
    );
    const confirm = screen.getByRole("button", {
      name: "Confirm Acknowledge alert",
    });
    fireEvent.click(confirm);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "I couldn’t verify whether Acknowledge alert completed. Refresh status before retrying.",
    );
    expect(screen.queryByText(/Nothing changed/i)).toBeNull();
    expect(
      screen.getByRole("dialog", { name: "Confirm Acknowledge alert" }),
    ).toBeInTheDocument();
    expect(confirm).toBeDisabled();

    fireEvent.click(
      screen.getByRole("button", { name: "Refresh status before retrying" }),
    );
    await waitFor(() => expect(confirm).toBeEnabled());

    fireEvent.click(confirm);

    expect(perform).toHaveBeenCalledTimes(2);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("restores the exact opener across repeated confirmation cancellation", async () => {
    render(
      <Briefing
        gateway={new FixtureGateway()}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );
    const opener = await screen.findByRole("button", {
      name: "Acknowledge alert",
    });

    for (let cycle = 0; cycle < 3; cycle += 1) {
      opener.focus();
      fireEvent.click(opener);
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: "Confirm Acknowledge alert" }),
        ).toHaveFocus(),
      );
      fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
      await waitFor(() => expect(opener).toHaveFocus());
    }
  });

  it("keeps a backend-declared confirmed failure open and refresh-gated", async () => {
    const gateway = new FixtureGateway();
    const perform = vi
      .spyOn(gateway, "performConfirmedAction")
      .mockResolvedValueOnce({
        ok: false,
        message: "The alert is already being processed.",
      });

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Acknowledge alert" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm Acknowledge alert" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The alert is already being processed. Refresh status before retrying.",
    );
    expect(perform).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("button", { name: "Confirm Acknowledge alert" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Refresh status before retrying" }),
    ).toBeEnabled();
  });

  it("keeps retry blocked when attention status cannot be refreshed", async () => {
    const gateway = new FixtureGateway();
    vi.spyOn(gateway, "performConfirmedAction").mockRejectedValueOnce(
      new Error("connection lost"),
    );

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Acknowledge alert" }),
    );
    vi.spyOn(gateway, "listAttention").mockRejectedValueOnce(
      new Error("attention offline"),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm Acknowledge alert" }),
    );
    await screen.findByRole("alert");
    fireEvent.click(
      screen.getByRole("button", { name: "Refresh status before retrying" }),
    );

    expect(
      await screen.findByText(
        "I couldn’t verify the alert status because Attention is unavailable. Refresh status before retrying.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Confirm Acknowledge alert" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("dialog", { name: "Confirm Acknowledge alert" }),
    ).toBeInTheDocument();
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
      "Refreshing your briefing…",
    );

    releaseRefresh?.();

    expect(await screen.findByText("Briefing updated.")).toBeInTheDocument();
  });

  it("ignores a stale refresh after the gateway changes", async () => {
    const staleGateway = new FixtureGateway();
    const freshSeed = createFixtureData();
    freshSeed.tasks = [
      {
        id: "task-fresh",
        title: "Fresh gateway work",
        description: "",
        status: "in_progress",
        priority: "high",
        dueAt: null,
      },
    ];
    const freshGateway = new FixtureGateway(freshSeed);
    let releaseStale: ((tasks: Awaited<ReturnType<SalarGateway["listTasks"]>>) => void) | undefined;
    const staleTasks = new Promise<
      Awaited<ReturnType<SalarGateway["listTasks"]>>
    >((resolve) => {
      releaseStale = resolve;
    });
    const now = () => new Date(2026, 6, 29, 15, 30);
    const view = render(<Briefing gateway={staleGateway} now={now} />);

    await screen.findByText("Review the launch brief");
    vi.spyOn(staleGateway, "listTasks").mockReturnValueOnce(staleTasks);
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    view.rerender(<Briefing gateway={freshGateway} now={now} />);
    expect(await screen.findByText("Fresh gateway work")).toBeInTheDocument();

    releaseStale?.([
      {
        id: "task-stale",
        title: "Stale gateway work",
        description: "",
        status: "in_progress",
        priority: "high",
        dueAt: null,
      },
    ]);

    await waitFor(() =>
      expect(screen.queryByText("Stale gateway work")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("Fresh gateway work")).toBeInTheDocument();
  });

  it("prevents overlapping row mutations", async () => {
    const gateway = new FixtureGateway();
    let releaseReminder: (() => void) | undefined;
    const reminderMutation = new Promise<void>((resolve) => {
      releaseReminder = resolve;
    });
    vi.spyOn(gateway, "dismissReminder").mockReturnValueOnce(reminderMutation);
    const updateTask = vi.spyOn(gateway, "updateTask");

    render(
      <Briefing
        gateway={gateway}
        now={() => new Date(2026, 6, 29, 15, 30)}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Mark Take a real break done" }),
    );
    const taskAction = screen.getByRole("button", {
      name: "Mark Review the launch brief complete",
    });
    expect(taskAction).toBeDisabled();
    fireEvent.click(taskAction);
    expect(updateTask).not.toHaveBeenCalled();

    releaseReminder?.();
    await screen.findByText("Take a real break is complete.");
  });
});
