# Phase 2 Issues — Projects, Memory, Artifacts

## Issue 1: Backend — Artifact Upload API Endpoint
**Title:** Artifact Upload API Endpoint
**Labels:** backend, api, artifacts, phase2
**Estimate:** 3d

Create file attachment API in backend.

- [ ] `POST /attachments/upload` — validate MIME, size ≤20MB, sanitize filename
- [ ] Store files to `data/uploads/` 
- [ ] Extract metadata (dimensions for images, page count for PDF)
- [ ] Return `{id, filename, size, mime_type, preview_url}`
- [ ] `GET /attachments/{id}` — return analysis
- [ ] `DELETE /attachments/{id}` — cleanup
- [ ] Tests: pytest unit tests for validation, extraction

## Issue 2: Frontend — Composer Attachment UI
**Title:** Composer Attachment Picker Component
**Labels:** frontend, ui, artifacts, phase2
**Estimate:** 4d

Add attachment handling to chat composer.

- [ ] `AttachmentPicker.tsx` — button, file browser, progress chips
- [ ] Integrate into `Composer.tsx`
- [ ] Show preview chips pre-send
- [ ] Handle cancel/retry
- [ ] Send files array with message
- [ ] Tests: vitest for chips, upload state

## Issue 3: Backend — Memory Table & Migration
**Title:** Memory Table Schema + Migration
**Labels:** backend, database, memory, phase2
**Estimate:** 2d

Create memory storage foundation.

- [ ] `backend/app/models/memory.py` — SQLAlchemy model
- [ ] Fields: id, user_id, type, content, tags, related_to, strength, expires_at, encrypted, created_at
- [ ] Alembic migration
- [ ] Tests: migration test, model validation tests

## Issue 4: Backend — Memory API Endpoints
**Title:** Memory CRUD API
**Labels:** backend, api, memory, phase2
**Estimate:** 4d

REST API for memory operations.

- [ ] `GET /memories` — query (type, project_id, search, limit, offset)
- [ ] `POST /memories` — create with content, tags, relations
- [ ] `GET /memories/{id}` — get + linked memories
- [ ] `PUT /memories/{id}` — update
- [ ] Graph: `GET /memories/graph?node={id}`
- [ ] Tests: fastapi testclient, contract tests

## Issue 5: Backend — Memory Service
**Title:** Memory Cache & Retrieval Service
**Labels:** backend, service, memory, phase2
**Estimate:** 3d

Storage and search logic.

- [ ] SQLite primary store
- [ ] ChromaDB semantic fallback for search
- [ ] Ranking: recency, tags, strength
- [ ] Tests: integration tests

## Issue 6: Frontend — Memory Sidebar
**Title:** Memory Sidebar Component
**Labels:** frontend, ui, memory, phase2
**Estimate:** 2d

Memory display in workspace rail.

- [ ] `MemorySidebar.tsx` — collapsible, recent memories
- [ ] Icons per memory type
- [ ] Quick search
- [ ] Styles in `workspace.css`

## Issue 7: Backend — Projects CRUD API
**Title:** Projects CRUD API
**Labels:** backend, api, projects, phase2
**Estimate:** 2d

Project management endpoints.

- [ ] `GET /projects` — list
- [ ] `POST /projects` — create
- [ ] `GET /projects/{id}` — details
- [ ] `PATCH /projects/{id}` — update
- [ ] `DELETE /projects/{id}` — soft delete
- [ ] Tests

## Issue 8: Frontend — Projects View
**Title:** Projects Dashboard View
**Labels:** frontend, ui, projects, phase2
**Estimate:** 3d

Project display and management.

- [ ] `ProjectsView.tsx` — grid of project cards
- [ ] FAB to create
- [ ] Add Projects to sidebar nav
- [ ] Styling with workspace.css

## Issue 9: Backend/Frontend — Artifact Analysis
**Title:** Artifact Analysis Integration
**Labels:** backend, api, frontend, artifacts, phase2
**Estimate:** 3d

AI analysis of uploaded files.

- [ ] Backend: send images to vision model
- [ ] Backend: extract key points from text
- [ ] Store as "artifact-metadata" memory
- [ ] Frontend: show "Analyzed with:" message

## Issue 10: Backend/Frontend — Memory-Project Linking
**Title:** Memory-Project Linking
**Labels:** backend, api, frontend, memory, projects, phase2
**Estimate:** 2d

Connect memories to projects.

- [ ] Backend: accept project_id in memory POST
- [ ] Frontend: "Save to project" option
- [ ] API: project detail includes memories