# SALAR Conversational Companion Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated, responsive SALAR redesign preview that opens with a live personal briefing, centers conversation and voice, exposes every current capability through progressive disclosure, and leaves all production interfaces unchanged.

**Architecture:** Add a standalone `preview/` React/Vite package in an isolated `codex/salar-redesign-preview` worktree. UI code depends on a typed `SalarGateway`; `LiveGateway` connects to the existing FastAPI API with preview-only session storage, while `FixtureGateway` provides deterministic tests and visual scenarios. The current `frontend/`, `desktop/`, `mobile/`, backend models, and release scripts are not modified.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, Playwright, axe-core, Lucide icons, CSS custom properties, existing FastAPI REST/SSE endpoints, browser MediaRecorder/Web Audio.

---

## Locked file structure

```text
preview/
  .env.example
  .gitignore
  README.md
  index.html
  package.json
  package-lock.json
  playwright.config.ts
  tsconfig.json
  vite.config.ts
  src/
    main.tsx
    app/
      PreviewApp.tsx
      routes.ts
    access/
      AccessGate.tsx
      previewSession.ts
    contracts/
      gateway.ts
      models.ts
      normalize.ts
    data/
      FixtureGateway.ts
      LiveGateway.ts
      fixtures.ts
    design/
      global.css
      tokens.css
    shell/
      CompanionShell.tsx
      ContextDrawer.tsx
      PrimaryNav.tsx
    components/
      ActionCard.tsx
      ApprovalDialog.tsx
      EmptyState.tsx
      Field.tsx
      IconButton.tsx
      Skeleton.tsx
      StatusMessage.tsx
    features/
      briefing/Briefing.tsx
      briefing/loadBriefing.ts
      conversations/ConversationWorkspace.tsx
      conversations/useConversation.ts
      live/LiveCompanion.tsx
      library/Library.tsx
      more/MoreHub.tsx
      more/PlanPanel.tsx
      more/CommunicationsPanel.tsx
      more/AutomationsPanel.tsx
      more/SystemPanel.tsx
    test/
      setup.ts
  e2e/
    accessibility.spec.ts
    navigation.spec.ts
    safety.spec.ts
    visual.spec.ts
```

Each file has one responsibility. Feature files may be split further when they exceed roughly 250 lines, but production source must not be imported to save time.

### Task 1: Create the isolated worktree and preview scaffold

**Files:**
- Create: `preview/package.json`
- Create: `preview/tsconfig.json`
- Create: `preview/vite.config.ts`
- Create: `preview/index.html`
- Create: `preview/.env.example`
- Create: `preview/.gitignore`
- Create: `preview/src/main.tsx`
- Create: `preview/src/test/setup.ts`

- [ ] **Step 1: Create the implementation worktree**

Run from the repository root:

```powershell
$previewWorktree = 'C:\Users\JD\Documents\SALAR AI-preview'
git worktree add -b codex/salar-redesign-preview $previewWorktree HEAD
```

Expected: a clean sibling worktree on `codex/salar-redesign-preview`. Do not stash, reset, clean, or stage the existing dirty tree.

- [ ] **Step 2: Write a failing scaffold smoke test**

Create `preview/src/app/PreviewApp.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PreviewApp } from './PreviewApp'

describe('PreviewApp', () => {
  it('renders the SALAR companion landmark', () => {
    render(<PreviewApp />)
    expect(screen.getByRole('main', { name: 'SALAR companion' })).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run the test and verify the expected failure**

Run:

```powershell
cd preview
npm test -- --run
```

Expected: failure because the package and `PreviewApp` do not exist.

- [ ] **Step 4: Create the package with pinned dependencies**

Create `preview/package.json`:

```json
{
  "name": "salar-redesign-preview",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1 --port 4174",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "build": "tsc --noEmit && vite build",
    "e2e": "playwright test",
    "verify": "npm run typecheck && npm test && npm run build && npm run e2e"
  },
  "dependencies": {
    "lucide-react": "1.25.0",
    "react": "19.2.7",
    "react-dom": "19.2.7"
  },
  "devDependencies": {
    "@playwright/test": "1.55.0",
    "@testing-library/jest-dom": "6.8.0",
    "@testing-library/react": "16.3.0",
    "@types/react": "19.2.14",
    "@types/react-dom": "19.2.3",
    "@vitejs/plugin-react": "6.0.3",
    "axe-core": "4.10.3",
    "jsdom": "26.1.0",
    "typescript": "7.0.2",
    "vite": "8.1.5",
    "vitest": "4.1.10"
  }
}
```

Run `npm install` in `preview/` and commit the generated lockfile. If npm reports an unavailable exact version, use `npm view <package> version` and pin the returned registry version before proceeding.

- [ ] **Step 5: Add TypeScript, Vite, HTML, and test setup**

Create `preview/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "vite.config.ts"]
}
```

Create `preview/vite.config.ts`:

```ts
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 4174 },
  build: { target: 'es2022', outDir: 'dist' },
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' },
})
```

Create `preview/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
```

Create `preview/index.html` with viewport zoom enabled, a theme color, favicon reference, description, and `<div id="root"></div>`. Do not add a manifest or service worker.

- [ ] **Step 6: Implement the minimal app**

Create `preview/src/app/PreviewApp.tsx`:

```tsx
export function PreviewApp() {
  return <main aria-label="SALAR companion">SALAR preview</main>
}
```

Create `preview/src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { PreviewApp } from './app/PreviewApp'

createRoot(document.getElementById('root')!).render(
  <StrictMode><PreviewApp /></StrictMode>,
)
```

- [ ] **Step 7: Verify and commit**

Run:

```powershell
npm run typecheck
npm test
npm run build
```

Expected: all commands exit 0.

Commit:

```powershell
git add preview
git commit -m "feat(preview): scaffold isolated SALAR redesign"
```

### Task 2: Define normalized contracts and fixture/live gateways

**Files:**
- Create: `preview/src/contracts/models.ts`
- Create: `preview/src/contracts/gateway.ts`
- Create: `preview/src/contracts/normalize.ts`
- Create: `preview/src/contracts/normalize.test.ts`
- Create: `preview/src/data/fixtures.ts`
- Create: `preview/src/data/FixtureGateway.ts`
- Create: `preview/src/data/LiveGateway.ts`
- Create: `preview/src/data/LiveGateway.test.ts`

- [ ] **Step 1: Write failing normalizer and safety tests**

Create tests asserting:

```ts
import { describe, expect, it } from 'vitest'
import { normalizeTask } from './normalize'

describe('normalizeTask', () => {
  it('normalizes missing optional fields', () => {
    expect(normalizeTask({ id: 7, title: 'Prepare brief', status: 'todo' })).toEqual({
      id: '7',
      title: 'Prepare brief',
      description: '',
      status: 'todo',
      priority: 'medium',
      dueAt: null,
    })
  })
})
```

Create a `LiveGateway` test with a mocked `fetch` that asserts the gateway reads `salar-preview.apiUrl` and `salar-preview.session` only and sends `Authorization: Bearer preview-token`.

- [ ] **Step 2: Run tests and verify failure**

Run: `npm test -- src/contracts/normalize.test.ts src/data/LiveGateway.test.ts`

Expected: failure because the contracts and gateways do not exist.

- [ ] **Step 3: Define the gateway contract**

`preview/src/contracts/models.ts` must define:

```ts
export type AccessState = 'checking' | 'paired' | 'unpaired' | 'offline' | 'expired'
export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'archived'
export interface ConversationSummary { id: string; title: string; updatedAt: string }
export interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; createdAt: string }
export interface TaskItem { id: string; title: string; description: string; status: TaskStatus; priority: string; dueAt: string | null }
export interface ReminderItem { id: string; title: string; message: string; remindAt: string; overdue: boolean; done: boolean }
export interface CalendarItem { id: string; title: string; start: string; end: string | null; location: string }
export interface AttentionItem { id: string; kind: string; title: string; detail: string; severity: 'neutral' | 'info' | 'warning' | 'critical'; action?: string }
export interface SourceItem { id: string; kind: 'memory' | 'document' | 'knowledge' | 'file'; title: string; detail: string; status?: string }
export interface BriefingSnapshot {
  tasks: TaskItem[]
  reminders: ReminderItem[]
  calendar: CalendarItem[]
  attention: AttentionItem[]
  conversations: ConversationSummary[]
  unavailable: string[]
}
```

`preview/src/contracts/gateway.ts` must define an interface with access, pairing/login, conversation list/detail/create/stream, briefing sources, library sources/search/upload, task/reminder mutations, communication summaries, workflow/system summaries, and a generic confirmed-action method.

- [ ] **Step 4: Implement deterministic fixtures and live requests**

`FixtureGateway` returns fixed synthetic timestamps and realistic non-sensitive data. Mutations update an in-memory store.

`LiveGateway`:

```ts
const API_KEY = 'salar-preview.apiUrl'
const SESSION_KEY = 'salar-preview.session'

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const baseUrl = sessionStorage.getItem(API_KEY)?.replace(/\/$/, '')
  if (!baseUrl) throw new Error('Preview backend URL is not configured.')
  const headers = new Headers(init.headers)
  const token = sessionStorage.getItem(SESSION_KEY)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail || `Request failed (${response.status})`)
  }
  return response.status === 204 ? undefined as T : response.json()
}
```

Implement event-stream parsing with `fetch` and `ReadableStream.getReader()` so streaming POST requests work in modern browsers.

- [ ] **Step 5: Verify and commit**

Run: `npm run typecheck && npm test`

Expected: all tests pass.

Commit:

```powershell
git add preview/src/contracts preview/src/data
git commit -m "feat(preview): add typed SALAR data gateways"
```

### Task 3: Build access, pairing, and preview-only session handling

**Files:**
- Create: `preview/src/access/previewSession.ts`
- Create: `preview/src/access/AccessGate.tsx`
- Create: `preview/src/access/AccessGate.test.tsx`
- Modify: `preview/src/app/PreviewApp.tsx`

- [ ] **Step 1: Write failing access-state tests**

Test these exact states:

```tsx
it('shows pairing without a preview session', async () => {
  render(<AccessGate gateway={unpairedGateway}><div>Connected app</div></AccessGate>)
  expect(await screen.findByRole('heading', { name: 'Bring SALAR closer' })).toBeVisible()
})

it('renders the app after session validation', async () => {
  render(<AccessGate gateway={pairedGateway}><div>Connected app</div></AccessGate>)
  expect(await screen.findByText('Connected app')).toBeVisible()
})
```

Add cases for invalid code, expired session, offline retry, and recovery login disclosure.

- [ ] **Step 2: Verify failure**

Run: `npm test -- src/access/AccessGate.test.tsx`

Expected: failure because `AccessGate` does not exist.

- [ ] **Step 3: Implement preview-only storage helpers**

`previewSession.ts` exports `loadPreviewConfig`, `savePreviewConfig`, and `clearPreviewSession`. It must only use `sessionStorage` keys beginning `salar-preview.`.

- [ ] **Step 4: Implement accessible pair-first access**

`AccessGate` must include:

- a labeled backend URL field;
- a six-digit pairing field with `inputMode="numeric"`;
- inline validation and `role="alert"`;
- submitting, invalid, expired, offline, and success states;
- recovery login behind a disclosure button;
- no automatic access to existing SALAR storage or Tauri APIs.

- [ ] **Step 5: Verify and commit**

Run: `npm run typecheck && npm test`

Commit:

```powershell
git add preview/src/access preview/src/app/PreviewApp.tsx
git commit -m "feat(preview): add isolated pairing and access flow"
```

### Task 4: Establish the Hearth Companion design system and accessible shell

**Files:**
- Create: `preview/src/design/tokens.css`
- Create: `preview/src/design/global.css`
- Create: `preview/src/shell/CompanionShell.tsx`
- Create: `preview/src/shell/PrimaryNav.tsx`
- Create: `preview/src/shell/ContextDrawer.tsx`
- Create: `preview/src/components/IconButton.tsx`
- Create: `preview/src/components/Field.tsx`
- Create: `preview/src/components/StatusMessage.tsx`
- Create: `preview/src/components/Skeleton.tsx`
- Create: `preview/src/components/EmptyState.tsx`
- Create: `preview/src/shell/CompanionShell.test.tsx`
- Modify: `preview/src/main.tsx`

- [ ] **Step 1: Write failing navigation and accessibility tests**

Assert that:

```tsx
expect(screen.getByRole('link', { name: 'Skip to conversation' })).toHaveAttribute('href', '#conversation')
expect(screen.getByRole('button', { name: 'Briefing' })).toHaveAttribute('aria-current', 'page')
expect(screen.getByRole('button', { name: 'Start Live conversation' })).toBeVisible()
```

At 390px layout width, assert the bottom navigation is present and the desktop rail has `hidden`.

- [ ] **Step 2: Verify failure**

Run: `npm test -- src/shell/CompanionShell.test.tsx`

- [ ] **Step 3: Add design tokens**

`tokens.css` defines:

```css
:root {
  --ink-950: #0b0908;
  --ink-900: #13100e;
  --cocoa-800: #201a17;
  --cocoa-700: #2a221e;
  --ivory-100: #f4eee4;
  --stone-300: #c8bdb0;
  --stone-500: #95887b;
  --amber-400: #c99a58;
  --teal-400: #64aaa2;
  --coral-400: #d87867;
  --focus: #edbd78;
  --radius-sm: .625rem;
  --radius-md: 1rem;
  --radius-lg: 1.5rem;
  --shadow-soft: 0 1.5rem 4rem rgba(20, 11, 7, .34);
  --content: 52rem;
  --rail: 5.25rem;
}
```

`global.css` must include enabled zoom, `color-scheme: dark`, visible `:focus-visible`, a skip link, 44px comfortable controls, semantic heading scale, safe-area padding, reduced motion, and responsive breakpoints at 1100px, 820px, and 560px.

- [ ] **Step 4: Implement the four-destination shell**

Primary destinations are `briefing`, `conversations`, `library`, and `more`. The shell includes:

- SALAR identity and connection status;
- desktop labeled rail;
- mobile bottom dock;
- persistent Live action;
- centered content canvas;
- optional context drawer;
- no animated background behind body text.

- [ ] **Step 5: Verify and commit**

Run: `npm run typecheck && npm test && npm run build`

Commit:

```powershell
git add preview/src/design preview/src/shell preview/src/components preview/src/main.tsx
git commit -m "feat(preview): build Hearth Companion shell"
```

### Task 5: Build the resilient personal briefing

**Files:**
- Create: `preview/src/features/briefing/loadBriefing.ts`
- Create: `preview/src/features/briefing/loadBriefing.test.ts`
- Create: `preview/src/features/briefing/Briefing.tsx`
- Create: `preview/src/components/ActionCard.tsx`

- [ ] **Step 1: Write failing aggregation tests**

Test successful and partial responses:

```ts
it('keeps successful sources when calendar fails', async () => {
  const snapshot = await loadBriefing(partialGateway)
  expect(snapshot.tasks).toHaveLength(2)
  expect(snapshot.unavailable).toContain('calendar')
})
```

Test ordering into Today, Needs you, and In motion.

- [ ] **Step 2: Verify failure**

Run: `npm test -- src/features/briefing/loadBriefing.test.ts`

- [ ] **Step 3: Implement independent concurrent loading**

Use `Promise.allSettled` for tasks, reminders, calendar, attention, and conversations. Convert each rejected source into an `unavailable` entry without discarding successful data.

- [ ] **Step 4: Implement the briefing UI**

Render:

- time-aware greeting;
- a concise SALAR summary;
- Today, Needs you, and In motion sections;
- skeletons while loading;
- empty and partial-failure states;
- one primary action per item;
- “Discuss with SALAR” context action;
- `aria-live="polite"` refresh status.

Use list rows and editorial groupings rather than equal-height card grids.

- [ ] **Step 5: Verify and commit**

Run: `npm run typecheck && npm test`

Commit:

```powershell
git add preview/src/features/briefing preview/src/components/ActionCard.tsx
git commit -m "feat(preview): add live personal briefing"
```

### Task 6: Build conversation history, streaming, tool states, and composer

**Files:**
- Create: `preview/src/features/conversations/useConversation.ts`
- Create: `preview/src/features/conversations/useConversation.test.tsx`
- Create: `preview/src/features/conversations/ConversationWorkspace.tsx`
- Create: `preview/src/components/ApprovalDialog.tsx`
- Create: `preview/src/components/ApprovalDialog.test.tsx`

- [ ] **Step 1: Write failing streaming state tests**

Test:

- loading history;
- new conversation;
- user message optimistic insertion;
- token accumulation;
- tool-start/tool-result transitions;
- interrupted partial response;
- offline recovery;
- focus after sending.

Use a controlled async iterator from `FixtureGateway`.

- [ ] **Step 2: Write a failing approval safety test**

```tsx
it('does not execute a consequential action before confirmation', async () => {
  const execute = vi.fn()
  render(<ApprovalDialog request={deleteRequest} onConfirm={execute} onCancel={() => {}} />)
  expect(execute).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }))
  expect(execute).toHaveBeenCalledOnce()
})
```

- [ ] **Step 3: Verify failures**

Run:

```powershell
npm test -- src/features/conversations/useConversation.test.tsx src/components/ApprovalDialog.test.tsx
```

- [ ] **Step 4: Implement conversation workspace**

Include:

- searchable history panel and new-conversation button;
- assistant and user message semantics;
- streaming status in a polite live region;
- tool activity as inline action cards;
- persistent multiline composer;
- send, attachment affordance, and Live action;
- contextual source/action inspector;
- target/scope/effect confirmation for consequential actions.

- [ ] **Step 5: Verify and commit**

Run: `npm run typecheck && npm test`

Commit:

```powershell
git add preview/src/features/conversations preview/src/components/ApprovalDialog*
git commit -m "feat(preview): add companion conversations and approvals"
```

### Task 7: Build warm Live mode with typed fallback and focus management

**Files:**
- Create: `preview/src/features/live/LiveCompanion.tsx`
- Create: `preview/src/features/live/LiveCompanion.test.tsx`
- Modify: `preview/src/design/global.css`

- [ ] **Step 1: Write failing phase and focus tests**

Test initialization, microphone denial, listening, thinking, acting, speaking, playback failure, text fallback, reduced motion, Escape close, focus containment, and focus restoration.

- [ ] **Step 2: Verify failure**

Run: `npm test -- src/features/live/LiveCompanion.test.tsx`

- [ ] **Step 3: Implement audio state machine**

Represent phases as:

```ts
type LivePhase = 'initializing' | 'listening' | 'thinking' | 'acting' | 'speaking' | 'error'
```

Use `MediaRecorder` for capture, the gateway STT/chat/TTS methods, `AudioContext` for playback, and an `AbortController` for teardown. Never accept microphone permission automatically in browser automation.

- [ ] **Step 4: Implement warm presence**

Use CSS radial layers and transforms for a breathing amber/teal halo. The halo changes amplitude and warmth by phase. Reduced motion renders a static halo plus a textual state indicator. Keep transcript history and a labeled typed fallback input visible.

- [ ] **Step 5: Verify and commit**

Run: `npm run typecheck && npm test`

Commit:

```powershell
git add preview/src/features/live preview/src/design/global.css
git commit -m "feat(preview): add accessible warm Live companion"
```

### Task 8: Build unified Library and contextual More hubs

**Files:**
- Create: `preview/src/features/library/Library.tsx`
- Create: `preview/src/features/library/Library.test.tsx`
- Create: `preview/src/features/more/MoreHub.tsx`
- Create: `preview/src/features/more/PlanPanel.tsx`
- Create: `preview/src/features/more/CommunicationsPanel.tsx`
- Create: `preview/src/features/more/AutomationsPanel.tsx`
- Create: `preview/src/features/more/SystemPanel.tsx`
- Create: `preview/src/features/more/MoreHub.test.tsx`

- [ ] **Step 1: Write failing Library tests**

Test filters for Memory, Documents, Knowledge, and Files; search results with source labels; upload processing/success/failure; empty and partial source states.

- [ ] **Step 2: Write failing More hub tests**

Assert all existing capability homes are discoverable:

```tsx
for (const name of ['Tasks', 'Reminders', 'Calendar', 'Email', 'WhatsApp', 'Workflows', 'Monitor', 'Devices', 'Files', 'Code', 'Settings']) {
  expect(screen.getByRole('button', { name })).toBeVisible()
}
```

Test that Advanced disclosures hide raw JSON, code execution, filesystem mutation, and device actions until opened.

- [ ] **Step 3: Verify failure**

Run:

```powershell
npm test -- src/features/library/Library.test.tsx src/features/more/MoreHub.test.tsx
```

- [ ] **Step 4: Implement Library**

Use one Find or Ask field with source filters. Keep backend models distinct internally and normalize them into `SourceItem`. Upload accepts backend-supported formats and displays processing/indexing state.

- [ ] **Step 5: Implement Plan and Communications**

Plan provides coherent task, reminder, and calendar views with create/update flows and explicit delete confirmation.

Communications provides Email and WhatsApp summaries, connection states, selected-message detail, compose/send confirmation, auto-reply confirmation, and handoff messages. Do not use external QR image services; render a textual pairing state unless the backend supplies a safe local QR asset.

- [ ] **Step 6: Implement Automations and System**

Automations provides workflow list, enable/disable confirmation, run status, and guided recipe presentation. Label configured/tested work truthfully.

System groups monitor, alerts, devices, files, code, connection, pairing, and security. File mutation, code execution, session revocation, and device commands all use `ApprovalDialog`.

- [ ] **Step 7: Verify and commit**

Run: `npm run typecheck && npm test`

Commit:

```powershell
git add preview/src/features/library preview/src/features/more
git commit -m "feat(preview): unify library and companion tools"
```

### Task 9: Add browser, accessibility, visual, and network-safety verification

**Files:**
- Create: `preview/playwright.config.ts`
- Create: `preview/e2e/navigation.spec.ts`
- Create: `preview/e2e/accessibility.spec.ts`
- Create: `preview/e2e/safety.spec.ts`
- Create: `preview/e2e/visual.spec.ts`
- Modify: `preview/package.json`

- [ ] **Step 1: Configure deterministic fixture E2E**

`playwright.config.ts` starts `npm run dev -- --mode fixture` and tests Chromium at:

- 1440×900;
- 1280×800;
- 768×1024;
- 390×844.

Use a single worker for stable visual output.

- [ ] **Step 2: Write failing navigation and safety tests**

Navigation must cover all four primary destinations, mobile dock, new conversation, Library filters, More groups, and Live open/close.

Safety test:

```ts
test.beforeEach(async ({ page }) => {
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    if (url.hostname !== '127.0.0.1') throw new Error(`External request blocked: ${url}`)
    return route.continue()
  })
})
```

Assert no consequential mock request occurs before the matching confirmation action.

- [ ] **Step 3: Add axe and keyboard tests**

Inject `axe-core`, run it on Briefing, Conversations, Library, More, Access, and Live fallback states, and fail on serious or critical violations. Add Tab-order, focus-visible, Escape, dialog focus, and focus-return tests.

- [ ] **Step 4: Add visual tests**

Capture fixture scenarios:

- populated;
- empty;
- loading;
- offline;
- partial failure;
- streaming;
- approval;
- reduced motion.

Use screenshot names containing viewport and scenario.

- [ ] **Step 5: Run and commit**

Run:

```powershell
npx playwright install chromium
npm run e2e
```

Expected: all browser tests pass with no external requests in fixture mode.

Commit:

```powershell
git add preview/playwright.config.ts preview/e2e preview/package.json preview/package-lock.json
git commit -m "test(preview): add visual accessibility and safety gates"
```

### Task 10: Connect and smoke-test the live backend safely

**Files:**
- Modify: `preview/.env.example`
- Create: `preview/README.md`
- Create: `preview/src/data/liveSmoke.test.ts`

- [ ] **Step 1: Document explicit live configuration**

`preview/.env.example`:

```dotenv
VITE_PREVIEW_DATA_MODE=fixture
VITE_PREVIEW_API_URL=
```

`README.md` must document:

- `npm ci`;
- fixture development;
- live development with explicit API URL;
- pair-first access;
- preview-specific session storage;
- confirmation policy;
- tests/build commands;
- statement that current SALAR is untouched.

- [ ] **Step 2: Add opt-in read-only smoke script**

`liveSmoke.test.ts` must skip unless `SALAR_PREVIEW_LIVE_SMOKE=1`. When enabled, it validates the session and reads conversations, tasks, reminders, and calendar without creating, updating, sending, deleting, executing, revoking, or acknowledging anything.

- [ ] **Step 3: Run fixture verification**

Run:

```powershell
npm run verify
```

Expected: typecheck, unit tests, build, and E2E all exit 0.

- [ ] **Step 4: Run manual live read-only smoke**

Start:

```powershell
$env:VITE_PREVIEW_DATA_MODE='live'
$env:VITE_PREVIEW_API_URL='http://127.0.0.1:8000'
npm run dev
```

Pair through the preview UI, then inspect Briefing, conversation history, Library, and More summaries. Do not trigger any consequential action during smoke verification.

- [ ] **Step 5: Confirm production isolation**

Run from the worktree root:

```powershell
git diff --name-only main...HEAD
```

Expected: only `preview/**` plus the approved design/plan documentation.

- [ ] **Step 6: Final regression evidence**

Run in the original packages without modifying them:

```powershell
npm --prefix frontend test
npm --prefix frontend run build
python -m pytest backend/tests
cargo test --manifest-path desktop/src-tauri/Cargo.toml
```

Report pre-existing failures separately from preview failures.

- [ ] **Step 7: Commit final documentation**

```powershell
git add preview/.env.example preview/README.md preview/src/data/liveSmoke.test.ts
git commit -m "docs(preview): document live SALAR companion preview"
```

## Final verification checklist

- [ ] `preview/` runs independently on port 4174.
- [ ] Production frontend, Tauri, Expo, backend models, and release scripts are unchanged.
- [ ] The preview never reads production storage keys.
- [ ] Briefing remains useful when one or more integrations fail.
- [ ] Conversation history, new conversation, streaming, tool states, and interruption are implemented.
- [ ] Live supports microphone failure, typed fallback, teardown, reduced motion, and correct focus behavior.
- [ ] Library distinguishes duplicate backend source types honestly.
- [ ] Every existing capability has one discoverable home.
- [ ] Consequential actions cannot call the gateway before confirmation.
- [ ] Keyboard, zoom, contrast, target sizes, status announcements, and responsive layouts meet the specified quality bar.
- [ ] Fixture E2E blocks external network requests.
- [ ] Live smoke testing is read-only unless the user explicitly initiates a confirmed mutation.
- [ ] Final diff contains only approved preview and documentation paths.
