# SALAR Feature Spec — Consensus Dual-Brain Mode

- **Status:** Proposed · Roadmap Phase 13 · #60
- **Owner:** SALAR (product-native; entirely inside the SALAR experience)
- **Ships with:** default local brain `salar-gemma4-e2b` + alternative `salar-gemma4-e4b` (both installed on the user's machine)

## TL;DR

In local mode the user can run the **Consensus** setting: SALAR asks **both** installed Gemma 4 brains the same question in parallel, has the secondary brain verify the primary brain's answer (and vice-versa where useful), commits tool side-effects **only once**, and returns a single answer flagged with its level of agreement. It turns the only weak spot of the local stack — single-model tool-calling reliability (E2B ~29%, E4B ~57%) — into a strength: a second opinion on every tool call, at the cost of the slower model's latency, not the sum.

## Problem it solves

- One local brain can confidently claim a wrong file list, wrong path, or a completed action it never took.
- Users can't easily tell whether the single answer is trustworthy.
- Flipping the picker manually to compare answers on every question is tedious.

## User stories

1. As a user in local mode, I select **Consensus** in the model picker. I ask "list my desktop" — SALAR returns one answer listing all real items and tells me both brains agreed (or that they disagreed and which parts were verified).
2. The primary brain says it "deleted the file"; the verifier brain reported the file still exists. SALAR shows me the conflict instead of hiding it.
3. I ask a subjective question ("rewrite this email") — both brains answer; SALAR picks one and offers the other as a variant.
4. I'm on battery or in a hurry — I switch back to **Single (E2B)** and nothing else changes.

## Design

### Trigger & selection

- `LocalModelPicker` gains a third choice next to the two models: **Consensus (E2B + E4B)**.
- Primary brain = the current default (`salar-gemma4-e2b`); verifier = `salar-gemma4-e4b` (higher tool reliability). Order is configurable later; v1 is fixed with E4B as the verifier.

### Flow (desktop `handle_ollama_chat`)

The backend `/api/ollama/chat` route already passes `model`, `messages`, `tools`. For consensus it additionally passes `"consensus_model": "salar-gemma4-e4b"`.

In `desktop/src-tauri/src/lib.rs`, a new `handle_ollama_chat_consensus` runs two blocking threads in parallel:

| Lane | Brain | Tool execution |
|---|---|---|
| **A — primary** | `salar-gemma4-e2b` | Full existing loop — the source of truth for any side effects (write/delete/run/notify/volume…) |
| **B — verifier** | `salar-gemma4-e4b` | Same conversation, parallel; executes **read-only** tools (list_files, read_file, calculate, system_info, get_*); **mutating tools are proposed but skipped** (returned as `{"skipped_in_consensus": true}`) |

Both lanes reuse the existing `run_local_action` + tool-call loop. Latency ≈ the slower lane (they run concurrently), not the sum.

### Merge step (in the desktop handler, after both lanes finish)

1. **Tool calls:** diff lane A's executed calls vs lane B's executed calls.
   - Identical `(name, args)` on both → "verified" (the strongest signal).
   - Lane B proposed a mutating call that lane A never executed → surfaced as a warning, not hidden.
   - Lane B's read-only result differs from lane A (e.g. different file count) → surfaced as a discrepancy note. This catches the OneDrive-style wrong-folder answers and truncated lists automatically.
2. **Final answer:**
   - Both contents agree → return lane A's answer with `"agreement": "both"`.
   - Differ without conflict → return lane A's answer, include a one-line variant ("the alternate brain phrased it differently") and `"agreement": "partial"`.
   - Contracting facts (verifier contradicts a claim) → return lane A's answer but mark `"agreement": "conflict"` with the specific disagreement listed — never silently pick one.
   - Lane A errored, lane B succeeded → fall back to lane B's answer, note the switch.

### Safety rules (non-negotiable)

- **One side effect per action.** Side-effecting tools are only executed by lane A. Lane B records proposals.
- No model-initiated differences in permission handling — both lanes go through the same `run_local_action` allow-lists.
- Save/write via memory tools happens only on the merged result, never twice.

### Response metadata (backend → frontend)

The existing response shape stays; consensus adds:

```json
{
  "content": "…final answer…",
  "executed": [ …lane A only… ],
  "consensus": {
    "used": true,
    "primary": "salar-gemma4-e2b",
    "verifier": "salar-gemma4-e4b",
    "agreement": "both" | "partial" | "conflict",
    "verified_calls": 2,
    "discrepancies": ["…"]
  }
}
```

The chat UI renders a small "🧠 agreed / ⚠️ 1 discrepancy" chip under the answer.

## Out of scope (v1)

- More than two brains in one run.
- Cloud-vs-local consensus (later), cross-user or per-turn cost arbitration.
- Auto "cost-aware" routing — user still chooses the mode explicitly.

## Testing

- **Unit:** merge logic (both/partial/conflict/fallback), lane-B skip behavior for mutating tools, discrepancy extraction.
- **Integration (this dev machine):** consensus run against the installed models — prompt suite: list desktop, write a file, calculate, summarize a file. Assert single execution of mutating calls (file written exactly once), correct agreement flags, OneDrive-desktop discrepancy caught.
- **UI:** picker round-trip, chip rendering, fallback to Single mode when `consensus_model` is unset/unknown.

## Milestones

- **M1:** ✅ built — backend `consensus_model` passthrough + response metadata (`build_ollama_chat_payload`, tested).
- **M2:** ✅ built — `run_ollama_lane` + `handle_ollama_chat_consensus` two-lane execution + `consensus_merge` in `lib.rs` (8 unit tests).
- **M3:** ✅ built — picker "Consensus (E2B + E4B)" option + agreement chip appended to local answers in chat UI (`main.tsx`, `ClassicChat.tsx`, helpers in `consensus.ts`, 8 tests; 138 frontend tests pass).
- **M4:** ✅ built — release rebuilt via `build-release.ps1`; fresh NSIS installer `SALAR_1.0.0_x64-setup.exe` (SHA `a3dd3310…eecd7ac5`) staged in `dist/installer` + `dist/website/downloads` (APK restored alongside).