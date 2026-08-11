# SALAR Capability Platform Design

**Date:** 2026-08-11  
**Status:** Approved architecture  
**Product surfaces:** SALAR backend, web/PWA, Windows Tauri desktop, WhatsApp

## Purpose

Expand SALAR from a conversational assistant into a guarded personal-automation platform with seven connected capabilities:

1. durable background jobs;
2. cloud and local model flexibility;
3. screen understanding;
4. clipboard history and smart paste;
5. record-and-replay RPA-lite;
6. a WhatsApp mini-CRM;
7. per-user learning from explicit feedback.

These are delivered as one continuous program, but each phase is independently testable, releasable, committed, and pushed. Shared foundations are implemented once and reused instead of building seven unrelated subsystems.

## Product principles

- **Guarded automation:** A user approves a recipe once. Routine steps may replay unattended, but payments, outbound messages, deletion, privilege elevation, credential entry, and unexpected screen states pause for confirmation.
- **Truthful state:** Prepared, queued, running, waiting, completed, partial, failed, cancelled, and expired are distinct. SALAR never reports an action completed without terminal evidence.
- **Local-first privacy where practical:** Screen images, clipboard items, recordings, and local-model prompts stay on the device unless the user explicitly selects cloud processing.
- **One user boundary everywhere:** Jobs, workflows, recordings, leads, feedback, screenshots, clipboard entries, and model settings are scoped by authenticated user and workspace.
- **Explicit permissions:** Desktop capabilities are disabled until granted individually. Permissions can be revoked and are checked at execution time, not only when a recipe is created.
- **Recoverable automation:** Long work survives restarts, has bounded retries, and is protected from duplicate execution with leases and idempotency keys.

## Chosen architecture

SALAR uses a unified capability platform rather than feature-specific schedulers and audit systems.

```text
Web / PWA / Tauri / WhatsApp
            |
     Capability APIs
            |
  Permission + Policy Gate
            |
      Durable Job Engine
       /      |       \
 Model Router |    Desktop Relay
              |       /   |   \
         CRM/Feedback Screen Clip RPA
            |
    Audit + Evidence Ledger
```

The existing `AgentRun` ledger continues to represent hidden AI-specialist work. A new durable `Job` subsystem represents user-visible, resumable work. Existing `Workflow` rows become definitions that enqueue jobs; they no longer claim success without executing actions.

## Phase 1: Durable background jobs

### Responsibilities

The job engine is the foundation for schedules, RPA replay, CRM follow-ups, long document work, and model fallback. It owns:

- enqueueing and idempotency;
- priority and scheduled time;
- leasing and heartbeat renewal;
- progress and structured status events;
- bounded retry with exponential backoff;
- cancellation and pause-for-approval;
- recovery of abandoned leases;
- user/workspace isolation;
- safe result and error summaries.

### Data model

New tables are introduced without altering existing production tables destructively:

- `jobs`: owner, workspace, kind, status, priority, input/result JSON, progress, scheduled time, lease token/expiry, attempt counters, idempotency key, cancellation request, timestamps.
- `job_events`: ordered immutable status/progress/evidence events.
- `job_approvals`: requested consequential action, redacted preview, status, approver, expiry, decision time.
- `job_schedules`: timezone-aware interval or cron definition, next-run time, enabled state, and last enqueue outcome.

The unique owner/idempotency-key constraint prevents duplicate submission. Lease acquisition and terminal claims use compare-and-set database updates. Workers never retain synchronous database sessions across network or desktop awaits.

### Execution

One worker loop is started by the backend in the initial release. It claims due jobs with a bounded lease, renews while work runs, and records each transition. The contract remains compatible with moving workers into a separate process later. Job handlers are registered by stable kind names and receive a cancellation token, progress reporter, and approval requester.

Existing workflows enqueue jobs. `WorkflowRun` becomes a compatibility view of the corresponding job outcome until the legacy run model can be retired safely.

## Phase 2: Model flexibility

### Provider contract

All text-generation paths depend on a `ModelProvider` interface rather than `GeminiClient` directly:

- `generate`;
- `stream`;
- tool-capable generation;
- vision capability when supported;
- health/capability discovery;
- bounded timeout and normalized provider errors.

Initial providers:

- **Gemini:** primary cloud provider and current Live provider.
- **Ollama:** local text/vision provider for privacy mode, with model discovery and an explicit unavailable response.
- **Fallback chain:** optional secondary cloud provider may be configured later through the same contract. OpenAI Realtime remains isolated to its existing live fallback until explicitly selected.

### Routing policy

Users choose one of:

- `balanced`: Gemini first, local fallback when cloud is unavailable and the task is supported;
- `privacy`: Ollama first; cloud requires per-request approval when local capability is insufficient;
- `quality`: strongest configured provider first;
- `manual`: fixed provider and model.

Routing considers required modalities, tool support, context size, latency class, privacy classification, provider health, and retry history. Provider fallback is recorded in job/agent evidence. Prompts are not silently sent to a less-private provider.

### Configuration

Secrets remain server-side. Local Ollama URLs must be loopback or explicitly allow-listed. Model settings are stored per user without API keys. The global configuration defines available providers and safe defaults.

## Phase 3: Screen understanding

### Desktop capture

Screen capture is a Tauri-only capability. Web and mobile can inspect images the user uploads but cannot silently capture a device screen.

The desktop bridge exposes narrowly scoped commands:

- enumerate displays/windows with redacted metadata;
- capture one display, window, or user-selected region;
- return a short-lived local artifact reference;
- delete the artifact after analysis or user retention expiry.

No continuous recording is enabled by default. Each capture shows a visible indicator. Password fields, protected windows, and configured applications are blocked or redacted where the OS exposes that information.

### Analysis

The model router selects local vision in privacy mode or an approved cloud vision provider. The request carries the user question and image, not unrelated clipboard/history data. Results include extracted text, detected error/total/document facts, confidence, and source coordinates when available.

Supported first-release intents:

- explain the visible error;
- extract a value or text;
- summarize an open document/image;
- identify a UI control for a guarded RPA step.

Screen content is untrusted evidence. Instructions visible on screen never override SALAR policy.

## Phase 4: Clipboard history and smart paste

Clipboard monitoring is opt-in and desktop-only. Users choose retention count/time and may pause collection globally or per application.

Clipboard entries store encrypted local payloads and minimal backend metadata only when sync is enabled. Sensitive patterns such as passwords, private keys, one-time codes, and payment-card data are excluded by default. Applications on the deny list never enter history.

Supported actions:

- search and reuse an entry;
- translate, reformat, summarize, or extract structured fields;
- create a task, note, document, or CRM lead;
- smart paste a transformed value after preview.

Writing to another application requires a desktop permission and uses the same policy gate as RPA. The original entry remains unchanged; transformations create derived entries with lineage.

## Phase 5: RPA-lite

### Recording

The desktop recorder captures semantic steps rather than raw coordinates whenever possible:

- application/window identity;
- accessible control role/name;
- user-entered value represented as a variable or secret reference;
- file operation with resolved paths;
- expected screen checkpoint before and after the action.

Raw coordinates are a last-resort fallback and are marked fragile. Keystrokes in password fields are never recorded. The user reviews and names the recipe before it can run.

### Recipe model

A recipe contains versioned steps, variables, required permissions, allowed applications/path roots, checkpoints, timeout, retry policy, and consequential-action markers. A published recipe is immutable; editing creates a new version.

### Replay

Each replay is a durable job. The desktop device claims it, verifies recipe signature/version and current permissions, then executes one step at a time. Before each step it validates the expected application and checkpoint. A mismatch pauses the job instead of guessing.

The following always request approval at execution time:

- payment or checkout submission;
- outbound message/email/social post;
- deletion or destructive overwrite;
- privilege elevation or security-setting changes;
- credential or secret use not already authorized for that recipe;
- a step outside the approved app/path scope.

Schedules enqueue recipe jobs through the shared scheduler. Device offline state becomes `waiting_for_device`, not failure. Every action produces redacted evidence.

## Phase 6: WhatsApp mini-CRM

The current one-time-introduction and per-contact history become the communications layer of a small CRM pipeline.

### Data model

- `crm_contacts`: owner-scoped WhatsApp JID, normalized name, labels, consent and last-contact state.
- `crm_leads`: source, stage, qualification fields, assigned workspace, value/currency when supplied, next action, timestamps.
- `crm_conversations`: contact/thread state and rolling summary; raw WhatsApp storage follows a defined retention policy.
- `crm_events`: inbound message, response, qualification, FAQ answer, escalation, order enquiry, task creation, and stage changes.
- `crm_faq_sources`: links to approved knowledge documents/workspaces.

### Behavior

Inbound messages are classified as FAQ, enquiry, order intent, support issue, pass-to-JD, spam, or unsupported. SALAR answers only from approved knowledge plus verified business settings. Missing facts trigger a focused question or escalation rather than fabrication.

Qualification rules are configurable. A lead is created or updated idempotently from the WhatsApp message identifier. Escalation creates a task and a concise notification for JD only when configured conditions are met. SALAR introduces itself once, then speaks naturally as JD's assistant without pretending to be JD.

The mini-CRM never charges a customer, promises inventory, changes an order, or sends sensitive information without an integrated verified system and the appropriate approval.

## Phase 7: Learning from feedback

Every assistant answer may receive thumbs up/down and an optional reason or corrected answer. Feedback is immutable and scoped to the user, conversation, message, model/provider, prompt-policy version, tools used, and evidence/run identifiers.

Learning is preference adaptation, not silent model training. A deterministic preference service derives bounded settings:

- concise vs detailed answers;
- formal vs conversational tone;
- preferred language and formatting;
- whether to ask clarifying questions earlier;
- tool/provider preference among equally safe options.

Preferences change only after sufficient consistent signals, have maximum bounds, show the user what changed, and can be reset. Negative feedback never grants additional permissions or weakens safety. Raw private content is not exported for training.

## Unified interfaces

The existing workspace UI gains focused surfaces rather than a second dashboard:

- **Jobs:** queued/running/waiting/completed work, progress, cancel, retry, approvals.
- **Models:** mode, selected provider/model, local availability, last fallback.
- **Screen:** capture target and ask field, recent temporary analyses.
- **Clipboard:** searchable local history and transformation actions.
- **Automations:** record recipe, review steps/permissions, test, schedule, run history.
- **Leads:** pipeline stages, contact timeline, escalation/task state.
- **Feedback:** thumbs controls on answers and a preference summary/reset.

Desktop-only controls are clearly unavailable on web/PWA rather than shown as broken actions. Mobile receives job/lead status and approvals but does not record desktop RPA.

## Security and privacy

- Consequential actions require policy approval at execution time.
- Desktop commands use allow-listed typed schemas; arbitrary shell commands are not introduced.
- Paths are canonicalized and checked against recipe/user-approved roots.
- Screen/clipboard artifacts have short retention and explicit cloud-transfer consent.
- Provider requests are classified and logged without storing secrets or full sensitive payloads.
- WhatsApp and CRM webhook processing remains idempotent and owner-scoped.
- Job and RPA leases use heartbeat renewal and token fencing before external actions.
- External actions use idempotency keys where the provider supports them.
- Logs and API errors are sanitized; protected diagnostics never return to models or clients.
- Audit records identify what happened, which permission allowed it, and the evidence of completion.

## Failure handling

- Provider failure routes through the configured fallback policy and records the change.
- Desktop offline jobs wait with an expiry and user-visible reason.
- Screen/RPA checkpoint mismatch pauses for review.
- Scheduler/worker restart recovers expired leases without duplicating terminal actions.
- WhatsApp contention remains serialized by database leases; deferred messages are visible rather than silently lost.
- Approval expiry leaves the job waiting/expired and performs no action.
- Ambiguous external outcomes enter `needs_verification`; SALAR checks evidence before retrying.

## Testing strategy

Each phase requires focused tests plus the complete relevant suite before push.

- **Jobs:** lease contention, restart recovery, cancellation, retries, idempotency, schedules/timezones, user isolation.
- **Models:** capability routing, privacy rules, fallback evidence, streaming parity, unavailable local model, secret isolation.
- **Screen/clipboard:** Tauri permission tests, capture scope, redaction, retention, cloud-consent boundary, local-only behavior.
- **RPA:** semantic recording, permission revocation, checkpoint mismatch, consequential pause, offline device, idempotent replay.
- **CRM:** webhook idempotency, FAQ grounding, lead transitions, escalation, owner isolation, retention, no repeated introduction.
- **Feedback:** ownership, preference thresholds/bounds/reset, no permission impact, provider/tool attribution.
- **Cross-platform:** backend pytest/compile, frontend Vitest/build, mobile TypeScript/protocol tests, Rust unit tests and desktop build for desktop phases.

Adversarial tests cover prompt injection in screen/clipboard/WhatsApp content, unsafe paths, secret leakage, lease stealing, lost commit acknowledgements, duplicate webhooks, and ambiguous external actions.

## Delivery and push policy

Implementation is divided into the following independently pushed milestones:

1. Job schema, store, worker, API, and UI status.
2. Model-provider contract, Gemini adapter, Ollama adapter, router, and settings UI.
3. Tauri screen capture plus vision analysis.
4. Clipboard history and smart transformations.
5. RPA recording, guarded replay, approvals, and schedules.
6. WhatsApp CRM data model, classification, FAQ, leads, escalation, and UI.
7. Feedback capture, preference derivation, and answer integration.
8. Final cross-feature hardening, desktop installer rebuild, and release verification.

For every milestone: tests run first, changes are reviewed, one or more focused commits are made, and verified `main` is pushed before the next milestone starts. Hostinger/static website deployment and desktop installer publication remain separate release actions with their own verification.

## Explicit non-goals for the first program

- unrestricted shell or arbitrary script recording;
- unattended payments, purchasing, or destructive actions;
- silent continuous screen recording;
- collection of passwords, private keys, one-time codes, or denied-app clipboard data;
- training foundation models on private user content;
- pretending WhatsApp messages were written personally by JD;
- replacing Gemini Live during these phases unless a separately verified live provider supports equivalent realtime audio.

## Acceptance criteria

- Long-running work is resumable, observable, cancellable, idempotent, and user-isolated.
- Users can choose Gemini or local Ollama under an explicit privacy/fallback policy.
- Desktop users can ask about a deliberately captured screen and safely reuse clipboard history.
- Users can record, review, schedule, and replay guarded desktop recipes with checkpoint and approval enforcement.
- WhatsApp enquiries become grounded answers, leads, tasks, and escalations without repeated introductions or fabricated business facts.
- Feedback changes bounded personal preferences and is visible/resettable.
- Every external or desktop action has permission, audit, and terminal evidence.
- Every milestone is verified, committed, and pushed before the next begins.
