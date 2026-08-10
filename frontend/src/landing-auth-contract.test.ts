import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const landing = readFileSync(new URL("./components/SalaarLanding.tsx", import.meta.url), "utf8");

describe("cosmic landing auth contract", () => {
  it("ships the three approved narrative chapters", () => {
    expect(landing).toContain("One intelligence that remembers");
    expect(landing).toContain("Voice-first companion");
    expect(landing).toContain("Your private command center");
    expect(landing).toContain("<CosmicIntelligence");
  });

  it("retains every configured authentication path", () => {
    expect(landing).toContain('handleOAuth("google")');
    expect(landing).toContain('handleOAuth("github")');
    expect(landing).toContain('handleOAuth("azure")');
    expect(landing).toContain("handleWalletSignIn");
    expect(landing).toContain("supabase.auth.signInWithOtp");
    expect(landing).toContain("supabase.auth.verifyOtp");
    expect(landing).toContain("onEnterApp?.(session.access_token)");
    expect(landing).toContain("cleanAuthFromUrl");
    expect(landing).toContain("<OnboardingWizard");
  });

  it("guards manual app entry instead of bypassing session validation", () => {
    expect(landing).toContain("await onEnterApp?.()");
    expect(landing).toContain("if (!entered)");
    expect(landing).not.toContain('onClick={onEnterApp}>Open SALAR');
  });

  it("loads the scoped cosmic visual system after the base landing styles", () => {
    const main = readFileSync(new URL("./main.tsx", import.meta.url), "utf8");
    const css = readFileSync(new URL("./cosmic-landing.css", import.meta.url), "utf8");
    expect(main.indexOf("./cosmic-landing.css")).toBeGreaterThan(main.indexOf("./landing.css"));
    expect(css).toContain("#salar-landing .cosmic-intelligence");
    expect(css).toContain("prefers-reduced-motion");
    expect(css).toContain("@media (max-width: 760px)");
  });
});
