# SALAR Agent Platform Expansion Design

**Date:** 2026-08-11  
**Status:** Approved design  
**Product:** SALAR web, desktop, iPhone PWA, backend, and WhatsApp assistant

## Objective

Expand SALAR into a resourceful, tool-using personal assistant that can research the web, analyze conversation attachments, prepare and place user-approved orders, present a polished iPhone Live experience, and maintain natural WhatsApp conversations without repeatedly introducing itself.

SALAR remains the only visible identity. Specialist agents operate behind the scenes and return evidence through one shared orchestration layer.

## Product principles

1. **Solve or advance.** SALAR uses an available tool, finds an alternative, or states the exact blocker and next useful action.
2. **Never fabricate completion.** Search results, file analysis, sent messages, cart state, orders, and confirmation numbers require evidence.
3. **One visible assistant.** Users never need to select or manage specialist agents.
4. **Explicit consequential approval.** SALAR may research and prepare a cart, but it cannot submit a paid order without approval tied to the exact final cart.
5. **Least context and least privilege.** Each specialist receives only the information and tools required for its assignment.
6. **Durable, recoverable work.** Long-running tasks can pause, retry safely, and resume without repeating external actions.

The “do not say no” request means SALAR must be resourceful. It does not permit illegal, unsafe, deceptive, privacy-invasive, or unauthorized actions. When such a boundary applies, SALAR explains it briefly and offers the closest safe alternative.

## System architecture

### Orchestrator Agent

The Orchestrator classifies intent, creates a task plan, selects specialists, manages dependencies, and produces the final response. It is the only component allowed to assign specialist work. It stores task state in a durable ledger and attaches evidence to every completed step.

### Research Agent

The Research Agent searches multiple web sources, opens the strongest results, checks dates, compares claims, and returns structured findings containing title, URL, publisher, publication date when available, retrieval time, excerpt summary, and confidence. Current-information requests route here automatically.

### Browser Operator

The Browser Operator navigates pages, follows links, completes non-consequential forms, and records screenshots or page evidence at important boundaries. It cannot submit payment, send a message, delete data, or perform another consequential action without an approved execution request from Orchestrator.

### Shopping Agent

The Shopping Agent collects requirements, compares products and merchants, calculates delivered cost, prepares a shortlist, and builds a cart where supported. It produces a normalized purchase plan rather than directly submitting checkout.

### Media Analyst

The Media Analyst handles images, screenshots, PDFs, Word files, text and code files, and short audio clips. Images are analyzed directly, documents are extracted and indexed, and audio is transcribed. Results are scoped to the active conversation unless the user explicitly asks to save them to long-term knowledge.

### Knowledge Agent

The Knowledge Agent retrieves relevant uploaded documents, saved memories, and previous conversation facts. It keeps user boundaries intact and marks whether information came from a current attachment, durable memory, or external research.

### Communications Agent

The Communications Agent handles WhatsApp and future email/message workflows. It receives contact-specific conversation state, follows the appropriate tone, and keeps “introduced as JD's assistant” state per owner/contact pair.

### Productivity and Device Agents

The Productivity Agent uses existing tasks, reminders, calendar, workflow, and alert tools. The Device Agent uses existing linked-device commands. Both continue through the same orchestration, evidence, and approval interfaces.

### Verifier Agent

The Verifier checks research conclusions, citations, cart details, totals, addresses, tool evidence, and external confirmation. It cannot perform actions. A task cannot be reported as completed when required verification evidence is missing.

### Recovery Agent

The Recovery Agent handles timeouts, expired sessions, unavailable pages, changed inventory, and failed tools. It can retry read-only steps, choose safe alternatives, and resume durable tasks. It cannot repeat consequential actions without an idempotency key and confirmed prior outcome.

### Preference Agent

The Preference Agent manages user-approved durable preferences such as sizes, brands, budgets, delivery choices, dietary restrictions, and communication style. Every saved preference is visible and removable by the user.

## Shared agent contracts

Each specialist assignment contains:

- Task and user identifiers.
- Intent and expected output schema.
- Minimum necessary context.
- Allowed tools and action class.
- Deadline and retry limit.
- Required evidence.
- Approval requirements.

Each result contains:

- Status: completed, partial, blocked, failed, or awaiting approval.
- Structured output.
- Evidence references.
- External changes performed.
- Remaining risks or missing information.
- Suggested next action.

The durable task ledger records step transitions so workflows can resume after browser, backend, or network interruption.

## Web research behavior

SALAR routes current, factual, comparative, recommendation, and shopping research through Research. Research uses multiple sources when the question benefits from corroboration. Verifier checks that citations support the final claims and that time-sensitive statements include retrieval context.

The user sees concise conclusions with linked sources. SALAR distinguishes sourced fact, agent inference, and uncertainty. Search failure triggers a safe alternative or a precise explanation; it never produces invented citations.

## Guarded purchase workflow

1. Collect missing requirements: item, budget, size or variant, quantity, delivery location, timing, and important preferences.
2. Research products and merchants.
3. Compare item price, shipping, taxes where available, seller reputation, returns, warranty, and delivery estimate.
4. Present a shortlist and let the user select.
5. Prepare the merchant cart.
6. Create a cart snapshot containing merchant, item, variant, quantity, unit price, shipping, taxes, total, address summary, delivery estimate, and payment-method suffix.
7. Generate a short-lived approval token bound to the cart snapshot hash.
8. Show the exact approval card and require explicit user confirmation.
9. Revalidate the cart immediately before submission. Any change invalidates approval and returns to step 8.
10. Submit checkout once with an idempotency key.
11. Verify the merchant confirmation page or confirmation number before reporting success.

Credentials and payment information remain in the merchant session or an approved secure vault. They never enter LLM prompts, agent messages, memories, ordinary logs, or audit details. CAPTCHA, additional authentication, or merchant intervention pauses the workflow and gives the user a focused handoff.

## Chat attachments and media analysis

The chat composer adds one spacious attachment control with camera, photo library, file, and audio choices. Selected items appear as removable preview chips before sending. The send action can include text, attachments, or both.

Initial supported formats:

- Images and screenshots.
- PDF documents.
- Word documents.
- Plain text, Markdown, JSON, and common source-code files.
- Short audio clips.

Uploads are associated with the user, conversation, and message. The backend validates file extension, MIME type, size, and filename; stores content in user-isolated storage; extracts or analyzes it; and supplies structured attachment context to the active conversation. Temporary processing files are removed after use.

Executables and unsupported formats are not analyzed. SALAR explains the limitation and suggests a supported export format. Attachments are not promoted to long-term knowledge unless requested.

## iPhone Live interface

The iPhone PWA uses a safe-area-aware bottom control dock instead of clustered floating controls. The primary controls are close, type, and microphone/status. Every interactive target is at least 44 points, includes a visible label or accessible name, and remains above the Home indicator.

Transcript history sits above the central animation, uses a bounded scroll region, and collapses gracefully on short screens and landscape orientation. Listening, thinking, speaking, reconnecting, and awaiting-approval states retain clear hierarchy without overlapping the Dynamic Island, transcript, or controls.

The existing central visual identity remains. Performance-sensitive effects stay tuned for mobile and respect reduced-motion preferences.

## WhatsApp conversation behavior

Conversation state is stored per SALAR owner and WhatsApp contact JID. The state includes whether Communications has introduced itself, recent normalized turns, active topic, last interaction time, and pending pass-to-JD request.

On the first eligible incoming direct message, Communications may briefly identify itself as JD's assistant and ask how it can help. After the first reply is successfully sent, the introduced flag becomes permanent for that owner/contact pair. All later prompts explicitly prohibit repeating the introduction and include recent contact history so replies continue naturally.

Group messages remain excluded from automatic replies. Empty or unsupported messages are handled without fabricating content. Explicit requests to pass information to JD continue to create a separate auditable pass-message record.

## Reliability and safety

- Consequential tools require an explicit action class and approval policy.
- Cart submission, outbound messages outside established auto-reply policy, deletion, and other external changes are auditable.
- Approval tokens are short-lived, single-use, user-bound, and snapshot-bound.
- Idempotency keys prevent duplicate paid submissions.
- Specialists have timeouts and retry budgets to prevent loops.
- Partial completion is reported accurately.
- Files, histories, preferences, and tasks remain isolated by user.
- Secrets and payment data are redacted from prompts and logs.
- Failed external actions retain evidence and a resumable state.

## Delivery phases

This document is the shared platform design. Implementation planning is deliberately split into four phase-specific plans so each subsystem produces working, testable software without depending on unfinished later phases. Phase 1 is planned and executed first; each later phase receives its own reviewed plan before implementation begins.

### Phase 1: Agent foundation and WhatsApp

Add the durable task ledger, hidden-agent router, Research, Verifier, Recovery, resourceful-response policy, cited web results, permanent contact introduction state, and contact conversation history.

### Phase 2: Attachments and media analysis

Add composer attachment previews, conversation-bound uploads, image/document/audio processing, validation, cleanup, and media context in chat responses.

### Phase 3: Guarded shopping

Add product comparison, cart preparation, snapshot approval, confirmation invalidation, idempotent checkout, merchant verification, and purchase audit history. Initial merchant support uses adapters for selected reliable merchants, with browser automation as a controlled fallback.

### Phase 4: iPhone Live interface

Add the safe-area control dock, larger touch targets, transcript hierarchy, responsive state presentation, and portrait/landscape PWA checks.

## Testing strategy

Every phase includes backend unit and integration tests, frontend behavior tests where applicable, and full-suite regression verification.

Required focused coverage:

- Agent intent routing and specialist selection.
- Evidence requirements and citation support.
- Recovery without duplicated external actions.
- User isolation across tasks, files, preferences, and contact state.
- WhatsApp first-message introduction followed by natural multi-turn replies without reintroduction.
- Attachment type, size, MIME validation, extraction, image analysis, audio transcription, conversation scoping, and temporary cleanup.
- Purchase cart changes, expired approval, wrong user, changed total, unavailable inventory, network retry, and duplicate submission.
- Verifier rejection when merchant confirmation evidence is absent.
- iPhone portrait and landscape layouts, safe-area insets, 44-point targets, keyboard behavior, and reduced motion.
- Complete frontend build and backend test suites before release.

Production rollout is staged. Research and WhatsApp improvements can ship first. Attachment analysis follows after isolation tests. Shopping begins with non-transactional comparison and cart preparation, then checkout is enabled only after approval, idempotency, and audit tests pass. The Live UI ships through the existing fingerprinted static asset workflow.

## Success criteria

- Users interact with one SALAR identity while specialists work invisibly.
- Current-information answers include useful, supportable citations.
- SALAR attempts tools or provides a concrete next action instead of a generic refusal.
- Supported attachments can be added directly to chat and discussed in context.
- No paid order is submitted without exact-cart approval, and no retry creates a duplicate order.
- WhatsApp introduces itself once per contact and then continues with contact-specific conversational history.
- iPhone PWA Live controls are readable, separated, accessible, and free from safe-area collisions.
- Every claimed external action is backed by verifiable evidence and an audit record.
