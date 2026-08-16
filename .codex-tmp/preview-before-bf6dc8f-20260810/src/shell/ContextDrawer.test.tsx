import { useState } from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ContextDrawer } from "./ContextDrawer";

afterEach(() => {
  cleanup();
  window.innerWidth = 1024;
  window.dispatchEvent(new Event("resize"));
});

function DrawerHarness() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open context
      </button>
      <ContextDrawer
        open={open}
        title="Conversation context"
        onClose={() => setOpen(false)}
      >
        <button type="button">Last action</button>
      </ContextDrawer>
    </>
  );
}

describe("ContextDrawer", () => {
  it("acts as a contained, dismissible mobile dialog and restores focus", async () => {
    window.innerWidth = 390;
    render(<DrawerHarness />);

    const opener = screen.getByRole("button", { name: "Open context" });
    opener.focus();
    fireEvent.click(opener);

    const dialog = screen.getByRole("dialog", {
      name: "Conversation context",
    });
    const close = screen.getByRole("button", {
      name: "Close context drawer",
    });
    const last = screen.getByRole("button", { name: "Last action" });

    expect(dialog).toHaveAttribute("aria-modal", "true");
    await waitFor(() => expect(close).toHaveFocus());

    last.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(opener).toHaveFocus();
  });

  it("always offers a working mobile dismiss control", () => {
    window.innerWidth = 390;
    render(
      <ContextDrawer title="Details">
        <p>Useful context.</p>
      </ContextDrawer>,
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Close context drawer" }),
    );

    expect(screen.queryByRole("dialog", { name: "Details" })).toBeNull();
  });

  it("uses unique labels for repeated desktop inspectors", () => {
    window.innerWidth = 1024;
    render(
      <>
        <ContextDrawer title="Context">First inspector.</ContextDrawer>
        <ContextDrawer title="Context">Second inspector.</ContextDrawer>
      </>,
    );

    const inspectors = screen.getAllByRole("complementary", {
      name: "Context",
    });
    const labelledBy = inspectors.map((inspector) =>
      inspector.getAttribute("aria-labelledby"),
    );

    expect(new Set(labelledBy).size).toBe(2);
  });
});
