# SALAR Cosmic Intelligence Landing Page Design

## Objective

Replace the current public SALAR landing experience with a high-impact futuristic AI presentation inspired by the supplied ARIIA reference: deep black space, dense luminous particles, a central intelligence core, and one continuous visual language from hero to final call to action.

The implementation belongs only in the main `frontend`. The `preview` project is out of scope. Existing Supabase login, signup, OAuth, OTP, wallet, onboarding, backend handoff, and URL-cleanup behavior must remain functional.

## Selected Direction

Use a hybrid rendering approach:

- A live interactive particle universe provides the hero and persistent atmospheric layer.
- Scroll progress transforms that universe between distinct narrative states.
- DOM content remains semantic, accessible, selectable, and independent of the visual renderer.
- Adaptive rendering preserves the same composition, color, motion language, and perceived quality on the website, desktop application, and mobile. Adaptation may change particle count or pixel density for stable frame rates, but must not replace the experience with a simpler visual design.

This approach was selected over a fully pre-rendered camera film, which would be less interactive and introduce paid rendering and heavier media delivery, and over a purely decorative WebGL background, which would not create enough narrative progression.

## Visual System

The page uses a near-black canvas with violet, magenta, electric cyan, and restrained warm-gold energy. The memorable centerpiece is a luminous particle intelligence that feels alive rather than ornamental.

The visual language includes:

- Concentric particle rings, orbital paths, sparks, and depth layers.
- A high-energy central core with bloom-like light and cursor parallax.
- Scroll-driven morphs between an intelligence sphere, a voice waveform, and an interconnected command network.
- Sparse glass and hairline chrome only where interface controls need a surface.
- Large, confident typography with generous negative space and no generic dashboard-card composition.
- Motion that remains continuous across sections, with reduced-motion behavior for visitors who request it.

## Narrative and Page Structure

### 1. Remember, reason, and act

The opening viewport introduces SALAR as one intelligence that remembers, reasons, and acts for the user. The particle core dominates the composition. Primary actions open the existing signup/sign-in flow; secondary navigation scrolls into the product story.

### 2. Voice-first AI companion

As the user scrolls, the intelligence core stretches into a responsive waveform and voice field. Copy explains natural conversation, live mode, continuity, and proactive assistance. The motion should imply listening and response without requiring microphone permission on the public page.

### 3. Private digital command center

The waveform reorganizes into an orbital network representing memory, knowledge, calendar, tasks, automations, and connected devices. Copy emphasizes privacy, user control, and coordinated action across the user's digital life.

### 4. Plans and trust

Existing pricing choices remain available in a visual treatment consistent with the cosmic system. Trust, privacy, and permission language are presented before purchase or signup decisions.

### 5. Final invitation

The particle network reconverges into the SALAR core and a focused final signup call to action. Footer links remain legible and conventional.

## Component Architecture

### `SalaarLanding`

Remains responsible for the public-page composition and existing authentication state. Authentication handlers are preserved rather than rewritten.

### `CosmicIntelligence`

A new isolated visual component owns the canvas/WebGL particle renderer, pointer response, scroll progress input, resize handling, quality adaptation, and teardown. It receives presentation state only and has no access to Supabase, API clients, authentication state, or pricing mutations.

### Narrative sections

Small semantic section components provide headings, body copy, feature labels, and calls to action. They report visibility or normalized scroll progress to the visual layer through a narrow interface.

### Authentication surface

The existing modal, provider actions, OTP steps, wallet connection, onboarding transitions, backend session bridge, and redirect cleanup remain the source of truth. Landing CTAs call the same handlers already used by the current page.

## Data and Interaction Flow

1. The browser renders accessible DOM content immediately.
2. `CosmicIntelligence` initializes after mount and chooses a rendering configuration from measured device capability.
3. A single passive scroll pipeline calculates normalized page and section progress.
4. The renderer interpolates between the three visual states without triggering React renders on every frame.
5. Authentication CTAs update the existing React auth state and open the existing modal.
6. Supabase processes redirect/session data exactly as it does now; successful session handoff and URL cleanup remain independent of the visual layer.

## Responsive and Performance Requirements

- Preserve the same narrative, core visual, colors, lighting, and transformations at all supported sizes.
- Use device pixel ratio caps, particle-level-of-detail, and dynamic resolution to maintain responsiveness without presenting a different design.
- Avoid loading a separate reduced-quality mobile asset chain.
- Pause or reduce background work when the page is hidden.
- Dispose of animation frames, observers, listeners, and graphics resources on unmount.
- Keep text and auth controls usable if WebGL is unavailable.

## Accessibility

- The canvas is decorative and excluded from the accessibility tree.
- All content and calls to action exist as semantic DOM elements.
- Keyboard focus, visible focus indicators, sufficient contrast, and logical heading order are required.
- `prefers-reduced-motion` presents the same visual composition with restrained or paused motion.
- Authentication remains fully keyboard accessible.

## Error Handling and Fallbacks

- Renderer initialization failure must not block content, navigation, pricing, or authentication.
- A CSS-rendered atmospheric fallback preserves the black, violet, magenta, cyan, and gold visual identity.
- Authentication and API errors continue to use the existing user-facing feedback paths.
- No authentication token or transient redirect error may remain visible in the query string or hash after Supabase has processed the redirect.

## Verification

- Add focused tests that protect the authentication entry points and ensure visual refactoring does not remove provider, OTP, wallet, or signup flows.
- Retain the auth redirect-cleanup tests covering query strings, hashes, safe parameters, and anchors.
- Add small unit tests for pure scroll-state interpolation or quality-selection helpers introduced by the visual component.
- Run the complete frontend Vitest suite and production build.
- Perform desktop and mobile visual checks in the main `frontend`, including reduced motion, resize behavior, CTA visibility, auth modal operation, and console errors.
- Confirm no files under `preview` changed.

## Scope Boundaries

- Do not change backend authentication contracts, Supabase project configuration, provider setup, or onboarding semantics.
- Do not modify the `preview` project.
- Do not add crypto, tokenomics, roadmap, or community content from the visual reference.
- Do not incur external image or video rendering costs for this implementation.
