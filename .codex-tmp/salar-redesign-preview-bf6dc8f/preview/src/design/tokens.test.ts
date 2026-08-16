import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const tokens = readFileSync(
  resolve(process.cwd(), "src/design/tokens.css"),
  "utf8",
);

describe("Hearth design tokens", () => {
  it("publishes the canonical shell dimensions and shadow names", () => {
    expect(tokens).toContain("--shadow-soft: 0 1.5rem 4rem rgba(20, 11, 7, 0.34)");
    expect(tokens).toContain("--content: 52rem");
    expect(tokens).toContain("--rail: 5.25rem");

    expect(tokens).not.toContain("--shadow-lifted");
    expect(tokens).not.toContain("--content-width");
    expect(tokens).not.toContain("--rail-width");
  });
});
