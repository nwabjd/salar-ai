# SALAR conversational companion preview

## Objective

Create a separate, production-quality redesign preview that connects to SALAR's current backend without changing the existing web, Tauri, or Expo interfaces. The preview should make SALAR feel like a warm, perceptive conversational companion: it opens with a useful personal briefing, keeps conversation at the center, and reveals the product's many tools only when they become relevant.

The preview is an adoption candidate, not a production migration. The existing SALAR interface remains untouched until the user explicitly approves the preview.

## Confirmed product direction

- SALAR is a conversational companion, not a dashboard or collection of mini-apps.
- SALAR opens with a personal briefing assembled from live backend data.
- The personality is warm, attentive, calm, and concise.
- The preview connects to the live SALAR backend through its own session and configuration.
- The SALAR name and icon remain. Typography, wordmark treatment, colors, motion, navigation, layout, and interface language are redesigned.
- The first preview covers responsive web and desktop-sized layouts. Native Expo adaptation follows only after preview approval.

## Approaches considered

### Hearth Companion — selected

A warm, dark conversational canvas with a personal briefing, persistent composer, restrained navigation, and contextual action surfaces. It best matches the confirmed personality and keeps complex capabilities available without presenting SALAR as a control panel.

### Obsidian Instrument

A highly precise dark interface built around an operational rail, inspector, and calibrated status motion. This would communicate power well, but it risks making SALAR feel cold and technical.

### Living Archive

An editorial, paper-inspired personal knowledge environment. This would give memory and documents a distinctive identity, but it would pull attention away from real-time conversation and require a larger departure from the existing dark product identity.

## Experience model

### Primary navigation

The preview has four primary destinations:

1. **Briefing** — the opening view and attention layer.
2. **Conversations** — current conversation, history, new conversation, and Live mode.
3. **Library** — unified access to memory, documents, knowledge, and files.
4. **More** — grouped Plan, Communications, Automations, System, Devices, Code, and Settings capabilities.

This replaces the current fifteen peer-level destinations. Workspace selection remains a global context control, but the preview does not imply workspace filtering where the backend does not support it.

Desktop uses a compact labeled rail, a centered content canvas, and an optional contextual inspector. Mobile uses a top identity bar, a bottom four-item dock, a full-width conversation stream, and bottom sheets for contextual detail. Live remains a prominent global action on every primary surface.

### Personal briefing

The briefing begins with a natural greeting and a short summary rather than a grid of metrics. It draws from available live endpoints:

- today's and upcoming calendar events;
- active and overdue reminders;
- current tasks and priorities;
- unread or recently active communications;
- WhatsApp handoff messages;
- triggered alerts;
- device and backend connection health;
- recent conversations and activity.

Information is grouped into three conversational sections:

- **Today** — time-sensitive agenda and priorities;
- **Needs you** — approvals, overdue items, warnings, and unanswered communication;
- **In motion** — recent or ongoing work, conversations, and automations.

Every item has one clear next action. Selecting an item either performs a safe reversible update, opens a contextual detail sheet, or starts a conversation with the relevant context attached.

Partial integration failures do not collapse the briefing. Each source reports its own state, and SALAR explains what is unavailable in plain language.

### Conversations

Conversation becomes the dominant working surface.

- The preview exposes conversation history instead of silently reopening only the latest thread.
- Users can create and resume conversations in one action.
- Streaming responses, tool use, partial completion, interruption, offline recovery, and errors have distinct states.
- Tool results appear inline as readable action cards, not raw database panels.
- The composer supports text, Live mode, attachments where the backend already supports them, and contextual prompts.
- A contextual inspector shows sources, memory used, actions taken, and approval state only when relevant.
- Consequential actions show target, scope, expected effect, and a confirmation step before execution.

### Live mode

Live mode becomes a warm, breathing presence rather than a permanent neon spectacle.

- Listening, thinking, acting, and speaking have visibly different but calm states.
- The existing magenta/cyan ring identity may appear as a subtle secondary accent.
- Transcript history and typed fallback remain available.
- Microphone denial, playback failure, backend loss, interruption, and reduced-motion behavior are designed as first-class states.
- Focus moves into Live when it opens, stays contained, and returns to the triggering control when it closes.

### Library

Library presents memories, legacy documents, indexed knowledge, and files as one source ecosystem while keeping their current API contracts separate.

- A unified Find or Ask entry point searches available source types and labels each result.
- Source filters distinguish Memory, Knowledge, Documents, and Files.
- Upload, indexing, processing, ready, empty, and failed states are explicit.
- Source details reveal chunks, metadata, or file information progressively.
- The preview does not pretend the duplicate backend document systems have already been migrated.

### More

Secondary capabilities are grouped by user outcome:

- **Plan:** tasks, reminders, and calendar;
- **Communications:** email and WhatsApp;
- **Automations:** workflows and run history;
- **System:** monitor, alerts, devices, files, code, security, connection, and settings.

Each group gets a coherent landing surface. Raw JSON, code execution, filesystem mutation, remote device actions, and destructive operations live under an Advanced disclosure and use explicit confirmation.

The preview represents workflow states truthfully. Existing workflow scaffolding is labeled as configured or tested; the interface does not claim an action ran unless the backend reports real execution.

## Visual system

### Tone

The visual direction is **Hearth Companion**: private, warm, quiet, and alive.

### Palette

- Canvas: warm near-black ink.
- Primary surfaces: cocoa-charcoal and softened graphite.
- Primary text: soft ivory.
- Secondary text: warm stone with WCAG AA contrast.
- Accent: muted amber/brass.
- Informational signal: restrained mineral teal.
- Destructive signal: soft coral.

Purple and magenta are reserved for legacy effect references and Live accents rather than the general interface.

### Typography

- A characterful humanist sans for controls and navigation.
- An expressive serif used sparingly for greetings, briefing statements, and important SALAR prose.
- A legible monospace for code, paths, tool logs, and tabular data.
- Body text remains at 14–16px or larger, metadata does not drop below 12px, and interaction targets are normally 40–44px.

### Surfaces and layout

- Use three stable elevation levels instead of glass on every element.
- Favor open editorial groupings and list rows over equal card grids.
- Keep primary content within a readable maximum width.
- Allow contextual sheets and inspectors to layer only when they clarify an active task.
- Use subtle grain and warm ambient light for depth, with contrast-safe opaque content surfaces.
- Avoid always-on motion behind text.

### Motion

Motion behaves like breathing, attention, and acknowledgement:

- gentle staggered entry for briefing sections;
- soft expansion for contextual detail;
- restrained state pulses for listening, thinking, and approvals;
- small tactile press and hover feedback;
- no decorative motion that competes with conversation.

All motion respects reduced-motion preferences, including canvas and JavaScript-driven effects.

## Accessibility requirements

The preview targets WCAG 2.2 AA.

- Browser zoom and text scaling remain enabled.
- All functionality is keyboard accessible.
- Every icon-only control has an accessible name.
- Active navigation, tabs, menus, toggles, streaming, and status messages expose correct semantics.
- A visible, consistent focus treatment appears on every interactive control.
- Text and UI contrast are verified against stable surfaces.
- Controls meet minimum target-size requirements.
- Skip navigation is available.
- Dialogs and Live mode manage focus correctly.
- Errors are associated with their fields and announced.
- Dynamic states use appropriate live regions without overwhelming assistive technology.
- Mobile layouts work with keyboard appearance, safe areas, landscape, and content zoom.

## Technical architecture

### Isolation

Add a new top-level `preview/` package. Do not import production frontend, Tauri, or Expo implementation files.

The package has its own:

- React and TypeScript entry point;
- Vite configuration and port `4174`;
- lockfile and pinned dependencies;
- `preview/dist/` build output;
- design tokens and component system;
- tests and browser verification;
- API gateway and preview-specific session storage.

No service worker or native Tauri capability is available in the preview. Existing production build and release scripts remain unchanged.

Because the repository contains extensive unrelated runtime and WhatsApp session changes, implementation must occur in an isolated `codex/` worktree based on the current approved commit. Only preview documentation and `preview/**` belong to this redesign.

### Backend connection

The preview has a `LiveGateway` implementing normalized frontend contracts over the existing FastAPI endpoints.

- Live mode is explicit through preview environment configuration.
- The API URL is stored under preview-specific keys.
- Authentication uses preview-specific session storage and never reads production `salar.*` storage keys.
- Pairing and recovery login are supported.
- Individual endpoint failures are normalized into typed feature states.
- The preview never infers a backend URL from the current web, Expo, or Render defaults.

A `FixtureGateway` remains available for deterministic automated tests, empty/error states, and visual review. Tests never mutate the live backend.

### Live-data safety

Normal user-requested creates and updates may use the live backend. Consequential operations require a target-and-effect confirmation surface immediately before the API call.

The following are always treated as consequential:

- sending or deleting communications;
- deleting or overwriting files, knowledge, memories, workflows, tasks, or reminders;
- running code;
- executing remote device commands;
- revoking sessions or disconnecting integrations;
- changing automation or auto-reply behavior.

Automated tests use fixtures only. Manual live verification begins with read-only endpoints and performs mutations only through explicit user actions.

## Component boundaries

- `PreviewApp` owns gateway selection, access state, primary navigation, and global overlays.
- `CompanionShell` owns responsive chrome, skip navigation, status, Live access, and contextual inspector.
- `Briefing` aggregates independent source adapters and renders resilient sections.
- `ConversationWorkspace` owns history, streaming, composer, tool activity, action cards, and conversation context.
- `LiveCompanion` owns microphone, speech recognition, TTS playback, transcript, focus, and phase state.
- `Library` owns source filters, search, upload, indexing states, and source detail.
- `MoreHub` groups Plan, Communications, Automations, and System surfaces.
- `ApprovalCenter` presents consequential actions through one shared confirmation contract.
- `LiveGateway` and `FixtureGateway` implement the same typed interface so UI behavior remains testable.

Each component exposes a narrow public contract and keeps internal loading, error, and empty-state logic local to its feature.

## Data flow

1. The preview restores only its own session and configured API URL.
2. Access validation resolves to paired, connected, expired, offline, or recovery state.
3. The briefing loads independent sources concurrently through the gateway.
4. Each source normalizes backend responses into preview contracts.
5. Conversation streaming emits token, tool-start, tool-result, completion, interruption, and error events.
6. Safe local UI updates use optimistic feedback with rollback on failure.
7. Consequential actions create an approval request before calling the gateway.
8. Live mode shares conversation contracts but owns audio capture and playback state.

## Error and state design

Every core surface includes:

- initial loading;
- empty;
- populated;
- refreshing;
- partial data;
- offline;
- permission denied;
- validation error;
- operation failure;
- success;
- reduced-motion behavior.

Errors use direct language and a recovery action. SALAR never presents a successful state when the backend only queued, configured, or simulated work.

## Verification

The preview must pass:

- TypeScript type checking;
- Vitest unit and interaction tests;
- production Vite build;
- browser tests at 1440×900, 1280×800, 768×1024, and 390×844;
- populated, empty, loading, offline, partial-failure, streaming, and confirmation scenarios;
- keyboard-only navigation and focus checks;
- reduced-motion checks;
- automated accessibility checks and manual contrast review;
- confirmation tests proving consequential requests are not sent before approval;
- fixture-mode network isolation.

Existing production frontend, backend, and Tauri tests are rerun only as regression evidence; preview implementation must not require production changes.

## Success criteria

- SALAR opens with an actionable personal briefing.
- A user can begin or resume a conversation in one action.
- No more than four primary destinations are visible at once.
- Every current frontend capability has one discoverable home.
- A briefing item can be acted on or discussed within two interactions.
- All consequential operations show target, scope, and effect before execution.
- The main experience remains usable at 200% zoom and by keyboard.
- The current SALAR interface and release outputs remain unchanged.
- The preview can connect to the live backend using its own session and can also run deterministically against fixtures.

## Out of scope

- Migrating the production frontend.
- Changing backend database models or merging Projects/Workspaces, Documents/Knowledge, or Devices/DeviceSessions.
- Rebuilding the native Expo app before preview approval.
- Shipping autonomous workflow execution the backend does not currently perform.
- Deploying the preview publicly without a separately approved origin and access model.
- Cleaning or rotating existing WhatsApp runtime credentials as part of the redesign.
