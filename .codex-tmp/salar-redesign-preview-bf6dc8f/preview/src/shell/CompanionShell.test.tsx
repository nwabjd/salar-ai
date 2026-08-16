import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CompanionShell } from "./CompanionShell";

afterEach(() => {
  cleanup();
  window.innerWidth = 1024;
  window.dispatchEvent(new Event("resize"));
});

describe("CompanionShell", () => {
  it("provides the companion's core accessible navigation", () => {
    render(
      <CompanionShell>
        <h1>Your day, gathered</h1>
      </CompanionShell>,
    );

    expect(
      screen.getByRole("link", { name: "Skip to conversation" }),
    ).toHaveAttribute("href", "#conversation");
    expect(
      screen.getAllByRole("button", { name: "Briefing" })[0],
    ).toHaveAttribute("aria-current", "page");
    expect(
      screen.getByRole("button", { name: "Start Live conversation" }),
    ).toBeVisible();
  });

  it("uses the mobile dock and hides the desktop rail at 390px", () => {
    window.innerWidth = 390;
    fireEvent(window, new Event("resize"));

    render(
      <CompanionShell>
        <p>Companion canvas</p>
      </CompanionShell>,
    );

    expect(screen.getByTestId("mobile-primary-nav")).not.toHaveAttribute(
      "hidden",
    );
    expect(screen.getByTestId("desktop-primary-nav")).toHaveAttribute("hidden");
  });
});
