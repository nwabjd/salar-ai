# SALAR Cosmic Intelligence Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready cosmic particle landing page in the main SALAR frontend while preserving every existing Supabase authentication and onboarding path.

**Architecture:** Keep authentication state and handlers inside `SalaarLanding`, but replace only its public marketing composition. Add an isolated canvas renderer whose pure scene and quality calculations live in a separately tested module; load a new scoped stylesheet after the current landing stylesheet so the existing auth modal remains intact.

**Tech Stack:** React 19, TypeScript, Canvas 2D, CSS, Vitest, Vite

---

## File Structure

- Create `frontend/src/components/cosmic-state.ts`: pure scroll-scene and renderer-budget calculations.
- Create `frontend/src/components/cosmic-state.test.ts`: focused tests for scene sequencing, clamping, and cross-device fidelity.
- Create `frontend/src/components/CosmicIntelligence.tsx`: isolated particle renderer and lifecycle management.
- Create `frontend/src/cosmic-landing.css`: scoped dark cosmic presentation, responsive layout, and reduced-motion styling.
- Create `frontend/src/landing-auth-contract.test.ts`: characterization guard for all Supabase entry points plus the new narrative structure.
- Modify `frontend/src/components/SalaarLanding.tsx`: replace public marketing JSX only; keep auth handlers and modal flow.
- Modify `frontend/src/main.tsx`: import the cosmic stylesheet after `landing.css`.

### Task 1: Lock the visual-state contract with failing tests

**Files:**
- Create: `frontend/src/components/cosmic-state.test.ts`
- Create: `frontend/src/components/cosmic-state.ts`

- [ ] **Step 1: Write the failing scene and quality tests**

```ts
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
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- --run src/components/cosmic-state.test.ts`

Expected: FAIL because `./cosmic-state` does not exist.

- [ ] **Step 3: Implement the pure visual-state helpers**

```ts
export type CosmicScene = "intelligence" | "voice" | "command";

export type CosmicSceneState = {
  scene: CosmicScene;
  localProgress: number;
};

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

export function getCosmicScene(progress: number): CosmicSceneState {
  const value = clamp01(progress);
  if (value < 1 / 3) return { scene: "intelligence", localProgress: value * 3 };
  if (value < 2 / 3) return { scene: "voice", localProgress: (value - 1 / 3) * 3 };
  return { scene: "command", localProgress: (value - 2 / 3) * 3 };
}

export function getParticleBudget({ width, height, dpr }: { width: number; height: number; dpr: number }): number {
  const areaScale = Math.sqrt((Math.max(320, width) * Math.max(568, height)) / (390 * 844));
  const densityScale = Math.min(1.3, Math.max(1, dpr / 2));
  return Math.round(Math.min(2200, Math.max(900, 950 * areaScale * densityScale)));
}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm test -- --run src/components/cosmic-state.test.ts`

Expected: 3 tests pass.

### Task 2: Build the isolated particle renderer

**Files:**
- Create: `frontend/src/components/CosmicIntelligence.tsx`
- Test: `frontend/src/components/cosmic-state.test.ts`

- [ ] **Step 1: Add a failing renderer-source contract test**

Append to `cosmic-state.test.ts`:

```ts
import { readFileSync } from "node:fs";

it("keeps the renderer decorative and lifecycle-safe", () => {
  const source = readFileSync(new URL("./CosmicIntelligence.tsx", import.meta.url), "utf8");
  expect(source).toContain('aria-hidden="true"');
  expect(source).toContain("cancelAnimationFrame");
  expect(source).toContain("removeEventListener");
  expect(source).toContain("getParticleBudget");
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- --run src/components/cosmic-state.test.ts`

Expected: FAIL because `CosmicIntelligence.tsx` does not exist.

- [ ] **Step 3: Implement the renderer component**

Create a `CosmicIntelligence` component with this public interface:

```tsx
import { useEffect, useRef, type RefObject } from "react";
import { getCosmicScene, getParticleBudget } from "./cosmic-state";

export type CosmicIntelligenceProps = {
  scrollRoot: RefObject<HTMLDivElement | null>;
};

export default function CosmicIntelligence({ scrollRoot }: CosmicIntelligenceProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const root = scrollRoot.current;
    if (!canvas || !root) return;
    // Initialize a dense deterministic particle field, resize it using
    // getParticleBudget, map root scroll progress with getCosmicScene, and draw
    // the intelligence sphere, voice waveform, and command network states.
    // Register passive scroll/pointer/resize/visibility listeners, honor
    // prefers-reduced-motion, and dispose every listener plus the animation frame.
  }, [scrollRoot]);

  return <canvas ref={canvasRef} className="cosmic-intelligence" aria-hidden="true" />;
}
```

The actual implementation must use deterministic seeded points, perspective projection, violet/magenta/cyan/gold color groups, pointer parallax, scroll interpolation, a static reduced-motion frame, and a CSS fallback class when canvas context creation fails.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm test -- --run src/components/cosmic-state.test.ts`

Expected: all renderer and helper tests pass.

### Task 3: Protect authentication while replacing the public narrative

**Files:**
- Create: `frontend/src/landing-auth-contract.test.ts`
- Modify: `frontend/src/components/SalaarLanding.tsx:577-805`

- [ ] **Step 1: Write the failing landing/auth contract test**

```ts
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
    expect(landing).toContain("bridgeToBackend");
    expect(landing).toContain("cleanAuthFromUrl");
    expect(landing).toContain("<OnboardingWizard");
  });
});
```

- [ ] **Step 2: Run the contract test and verify RED**

Run: `npm test -- --run src/landing-auth-contract.test.ts`

Expected: the auth assertions pass and the new narrative assertions fail.

- [ ] **Step 3: Replace only the marketing composition**

Import the renderer:

```tsx
import CosmicIntelligence from "./CosmicIntelligence";
```

Inside `#salar-landing`, place `<CosmicIntelligence scrollRoot={shellRef} />`, then build these semantic sections before the existing `{modalOpen && (...)}` block:

```tsx
<section className="cosmic-hero" id="top">
  <p className="cosmic-kicker">Private intelligence / continuously yours</p>
  <h1>One intelligence that remembers.<br /><em>Reasons. Acts.</em></h1>
  <p>Salaar turns your conversations, context, and connected world into forward motion.</p>
  <button onClick={launchSignup}>Meet your SALAR <Icon.Arrow /></button>
</section>

<section className="cosmic-chapter voice-chapter" id="experience">
  <span>01 / Live presence</span>
  <h2>Voice-first companion.</h2>
  <p>Speak naturally. SALAR listens, understands context, and stays with the thread.</p>
</section>

<section className="cosmic-chapter command-chapter" id="capabilities">
  <span>02 / Connected intelligence</span>
  <h2>Your private command center.</h2>
  <p>Memory, knowledge, calendar, tasks, automations, and devices move as one system.</p>
</section>
```

Retain the existing pricing cards, privacy claims, final CTA, footer, and complete auth modal JSX, but rewrap their public containers with cosmic class names. Do not change `handleOAuth`, `handleWalletSignIn`, `handleSendCode`, `handleVerifyCode`, `bridgeToBackend`, the session effect, checkout handlers, onboarding handlers, or modal step JSX.

- [ ] **Step 4: Run the contract test and verify GREEN**

Run: `npm test -- --run src/landing-auth-contract.test.ts`

Expected: 2 tests pass.

### Task 4: Apply the approved cosmic visual system

**Files:**
- Create: `frontend/src/cosmic-landing.css`
- Modify: `frontend/src/main.tsx:13-15`

- [ ] **Step 1: Write a failing stylesheet contract test**

Append to `frontend/src/landing-auth-contract.test.ts`:

```ts
it("loads the scoped cosmic visual system after the base landing styles", () => {
  const main = readFileSync(new URL("./main.tsx", import.meta.url), "utf8");
  const css = readFileSync(new URL("./cosmic-landing.css", import.meta.url), "utf8");
  expect(main.indexOf("./cosmic-landing.css")).toBeGreaterThan(main.indexOf("./landing.css"));
  expect(css).toContain("#salar-landing .cosmic-intelligence");
  expect(css).toContain("prefers-reduced-motion");
  expect(css).toContain("@media (max-width: 760px)");
});
```

- [ ] **Step 2: Run the contract test and verify RED**

Run: `npm test -- --run src/landing-auth-contract.test.ts`

Expected: FAIL because `cosmic-landing.css` and its import do not exist.

- [ ] **Step 3: Create the scoped stylesheet and import it last**

Add after `import './landing.css'` in `main.tsx`:

```ts
import './cosmic-landing.css'
```

Create `cosmic-landing.css` with all public rules scoped under `#salar-landing`. It must:

- Override the canvas to `#050308` and text to near-white.
- Fix the canvas behind content and keep it pointer-transparent.
- Use violet, magenta, electric cyan, and restrained gold glows.
- Give each narrative chapter at least one viewport of scroll distance.
- Use large responsive type, sparse navigation, and minimal glass surfaces.
- Keep buttons and links visibly focusable.
- Keep the existing modal above the canvas with readable light surfaces.
- Preserve the same composition on mobile, changing layout rather than removing visual layers.
- Disable continuous movement under `prefers-reduced-motion` without hiding content.

- [ ] **Step 4: Run the contract test and verify GREEN**

Run: `npm test -- --run src/landing-auth-contract.test.ts`

Expected: all landing/auth/style contract tests pass.

### Task 5: Integrate, refine, and verify

**Files:**
- Modify if required: `frontend/src/components/CosmicIntelligence.tsx`
- Modify if required: `frontend/src/components/SalaarLanding.tsx`
- Modify if required: `frontend/src/cosmic-landing.css`
- Verify: `frontend/src/lib/supabase.test.ts`

- [ ] **Step 1: Run the complete frontend test suite**

Run: `npm test`

Expected: all tests pass, including the four auth URL-cleanup tests.

- [ ] **Step 2: Run the production build**

Run: `npm run build`

Expected: TypeScript and Vite exit 0. Record any non-blocking bundle-size warning rather than calling the output warning-free.

- [ ] **Step 3: Run source and diff checks**

Run:

```powershell
git diff --check
git status --short
git diff --name-only -- preview
```

Expected: no whitespace errors, intended frontend files only for this implementation, and no changed tracked files under `preview`.

- [ ] **Step 4: Perform desktop visual and auth QA**

Run the main frontend with `npm run dev -- --host 127.0.0.1`, open the assigned Vite URL, and verify at 1440x900:

- Hero core is immediately visible and animated.
- Scrolling transitions in order from intelligence to voice to command.
- Pricing, privacy, and final CTA are readable.
- Signup opens the existing auth modal.
- Google, GitHub, Microsoft, wallet, and email controls remain present.
- No console errors occur.

- [ ] **Step 5: Perform mobile and reduced-motion QA**

At 390x844 and with reduced motion enabled, verify:

- The same particle core and three-scene narrative remain present.
- Text and CTAs do not overlap or clip.
- Navigation and auth modal remain usable.
- The reduced-motion presentation is static or restrained rather than blank.

- [ ] **Step 6: Review the final diff against the spec**

Confirm the implementation covers all visual, narrative, responsive, accessibility, fallback, auth-protection, testing, and scope requirements in `docs/superpowers/specs/2026-08-10-salar-cosmic-intelligence-landing-design.md`.
