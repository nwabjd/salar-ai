# SALAR Master Feature Roadmap

## Already Built
- Mission Mode (planner + runner + approval + API)
- Intel system (email watch, morning brief, background jobs)
- 60+ agent tools
- Workspaces, Workflows
- Live mode (STT/TTS), WhatsApp bridge, Code interpreter, Monitor

---

## Phase 1 — Core UX Foundation
Unlocks every downstream feature. Build first.
1. **Permission Center** — granular tool permissions + approval levels (Observe/Suggest/Ask/Autonomous) per tool category
2. **Action Replay + Undo** — every tool call records before/after; rollback support for files/moves/edits
3. **Salaar Guardian** — security agent: flags dangerous commands, monitors network, audits tool calls
4. **Intelligent Model Router** — selects model per task (simple→Flash, code→coding model, vision→Gemini Pro, reasoning→Pro, creative→image/video)
5. **Thought Stream** — real-time operational stream (Request → Research Agent → Sources Checked → File Created → Done)
6. **Memory Graph** — Memory model upgraded: type (short-term/long-term/project/personal/vault), connections between memories, graph API
7. **Universal Search** — one search across files, conversations, email, calendar, tasks, memory, knowledge
8. **Command Center** — single dashboard: missions, tasks, calendar, email, device status, AI activity, system health

## Phase 2 — Intelligence Layer
9. **AI Agent Swarm** — mission/planner spawns specialized temporary agents (Researcher, Coder, Browser, FileManager, Email, Calendar, System) with tool subsets
10. **Deep Research Mode** — multi-agent research: multiple independent agents research, cross-check, debate, produce verified answer
11. **Proactive Intelligence** — detect and alert: low storage, upcoming deadlines, unfinished work, important email, failed processes
12. **End-of-Day Memory** — daily auto-summary: completed, pending, suggested tomorrow
13. **Predictive Actions** — pattern detection: "You normally open VS Code at this time"
14. **Decision Simulator** — "what if A vs B?" with scenario modeling
15. **Contact Intelligence** — people profiles: conversations, meetings, projects, important dates, follow-ups

## Phase 3 — Vision & Screen
16. **Computer Vision Mode** — screenshot understanding via vision model
17. **Live Screen Copilot** — floating orb overlay with contextual help
18. **Screenshot Intelligence** — hotkey → select region → ask about it
19. **Clipboard Intelligence** — understand copied content, suggest actions
20. **Universal Context Menu** — right-click anywhere in Windows → SALAR actions
21. **Visual UI Builder** — screenshot → analyze → generate implementation changes
22. **Browser Intelligence** — summarize tabs, fill forms, extract research

## Phase 4 — Voice & Conversation
23. **Wake Word** — "Hey SALAR" with local VAD
24. **Natural Voice** — emotions, styles, whisper mode, interruption support

## Phase 5 — Memory & Knowledge
25. **Memory Categories** — short-term/long-term/project/personal/vault separation
26. **Project Spaces** — persistent workspaces: files, chats, agents, objectives per project
27. **Personal Knowledge Base** — documents + websites + notes + conversations → searchable knowledge
28. **Learning Mode** — interactive teaching, tracks what user already knows
29. **Digital Twin** — learns user patterns: writing style, priorities, routine decisions

## Phase 6 — Automation & Files
30. **Workflow Recorder** — observe user action → repeatable workflow
31. **Automation Builder** — natural language triggers: "every Friday, organize invoices"
32. **File Intelligence** — right-click file → Summarize/Explain/Rewrite/Convert/Analyze
33. **Semantic File Search** — search by meaning, not filename
34. **Smart File Manager** — auto-categorize files

## Phase 7 — System & Hardware
35. **Computer Health Intelligence** — live CPU/GPU/RAM/storage/network/temp/process stats
36. **AI Performance Optimizer** — auto CPU/GPU offloading, quantization, context sizing
37. **Local AI Control Center** — installed models, RAM/VRAM, tokens/sec, context windows
38. **Model Hot-Swap** — switch models without restart
39. **Self-Diagnostics** — inspect own services, agents, API connections
40. **Self-Healing** — detect + restart failed services

## Phase 8 — Privacy & Security
41. **Local-First Privacy Mode** — Local Only / Hybrid / Cloud toggle
42. **Privacy Shield** — detect passwords/financial/IDs before cloud sends
43. **Private AI Vault** — encrypted storage, explicit auth required

## Phase 9 — Developer
44. **Developer Mode** — terminal, GitHub, code editor, logs, builds in one workspace
45. **Autonomous Coding Agent** — inspect project, plan, modify, test, iterate

## Phase 10 — Multi-Device
46. **Phone Companion** — mobile → desktop remote control
47. **Cross-Device Continuity** — start on Windows, continue on iPhone
48. **Remote PC Control** — phone command → Windows executes
49. **Device Mesh** — connected device visualization

## Phase 11 — Plugins
50. **Plugin Marketplace** — install capability packs
51. **Skill Creator** — natural language → reusable workflow

## Phase 12 — Creative & Visual
52. **Salaar Presence** — 3D entity (listening/thinking/researching/acting/sleeping)
53. **AI Core Visualization** — animated neural sphere
54. **Ambient Mode** — minimal desktop visualization when idle
55. **AI Canvas Workspace** — infinite spatial workspace
56. **Creation Studio** — image/video/voice/music/scripts workspace
57. **Adaptive Interface** — context-aware dashboard
58. **Emotion-Aware Interface** — respond to urgency/frustration cues

## Phase 13 — Ecosystem & Local Intelligence
Net-new items that extend the shipped local-brain stack (Gemma 4 E2B/E4B) and the multi-device footprint.

59. **MCP Server + Client** ✅ built — SALAR's agent tool set exposed as a Model Context Protocol stdio server (any MCP client can drive SALAR: OpenCode, Claude Desktop, Cursor, OpenClaw), plus SALAR agent tools `mcp_tools`/`mcp_call` that call external MCP servers configured via `SALAR_MCP_SERVERS`.
60. **Consensus Dual-Brain Mode** — run the same prompt on E2B + E4B in parallel, compare tool-call plans, synthesize one answer with a confidence note (both models already ship installed).
61. **Local-Only Document RAG** — index the user's files with a local embedding model; answer questions exclusively from those documents with zero cloud uploads (privacy flagship; rides OneDrive-aware file layer).
62. **Model A/B Tester** — productize `tools/nim-diagnostic`: pick two models, same prompt, side-by-side results + voting, inside the app.
63. **Voice-Note Ingestion (WhatsApp)** — user sends a voice note to SALAR on WhatsApp; local STT transcribes, tool-calling acts, reply flows back to the chat.
64. **Meeting Huddle Bot** — join a call, live notes, extracted action items routed to WhatsApp/email/tasks.
65. **Hotkey Launcher** — Ctrl+Space opens a SALAR prompt from anywhere (Spotlight-style; complements Universal Search + Context Menu).
66. **Phone-as-Confirmation Device** — sensitive actions (delete, send, pay) require OK from the user's phone, not just an in-app dialog (gives Android APK a concrete role).
67. **Agent Handoff** — SALAR pushes a task to another agent (OpenClaw/OpenCode/Claude) with a context summary and ingests the result.
68. **One-Click Diagnostic Bundle** — system info + recent SALAR logs + config as a shareable snapshot for support.
