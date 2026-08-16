import { describe, expect, it } from "vitest";

import { normalizeTask } from "./normalize";

describe("normalizeTask", () => {
  it("fills optional task fields with stable preview defaults", () => {
    expect(normalizeTask({ id: 7, title: "Prepare brief", status: "todo" })).toEqual({
      id: "7",
      title: "Prepare brief",
      description: "",
      status: "todo",
      priority: "medium",
      dueAt: null,
    });
  });
});
