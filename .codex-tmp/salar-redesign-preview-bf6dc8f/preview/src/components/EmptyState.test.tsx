import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { EmptyState } from "./EmptyState";

afterEach(cleanup);

describe("EmptyState", () => {
  it("generates unique accessible labels for repeated instances", () => {
    render(
      <>
        <EmptyState title="Nothing here">First empty state.</EmptyState>
        <EmptyState title="Nothing here">Second empty state.</EmptyState>
      </>,
    );

    const sections = screen.getAllByRole("region", { name: "Nothing here" });
    const labelledBy = sections.map((section) =>
      section.getAttribute("aria-labelledby"),
    );

    expect(new Set(labelledBy).size).toBe(2);
    for (const id of labelledBy) {
      expect(id).toBeTruthy();
      expect(document.getElementById(id!)).toBeInTheDocument();
    }
  });
});
