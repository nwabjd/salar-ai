import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { getCosmicScene, getParticleBudget } from "./cosmic-state";

describe("cosmic landing visual state", () => {
  it("moves through intelligence, voice, and command scenes in order", () => {
    expect(getCosmicScene(0.1).scene).toBe("intelligence");
    expect(getCosmicScene(0.5).scene).toBe("voice");
    expect(getCosmicScene(0.9).scene).toBe("command");
  });

  it("clamps progress and returns normalized local scene progress", () => {
    expect(getCosmicScene(-2)).toEqual({ scene: "intelligence", localProgress: 0 });
    expect(getCosmicScene(2)).toEqual({ scene: "command", localProgress: 1 });
  });

  it("keeps a dense field on mobile while scaling up for larger canvases", () => {
    expect(getParticleBudget({ width: 390, height: 844, dpr: 3 })).toBeGreaterThanOrEqual(900);
    expect(getParticleBudget({ width: 1440, height: 900, dpr: 2 })).toBeGreaterThan(1200);
  });

  it("keeps the renderer decorative and lifecycle-safe", () => {
    const source = readFileSync(new URL("./CosmicIntelligence.tsx", import.meta.url), "utf8");
    expect(source).toContain('aria-hidden="true"');
    expect(source).toContain("cancelAnimationFrame");
    expect(source).toContain("removeEventListener");
    expect(source).toContain("getParticleBudget");
  });
});
