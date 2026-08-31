# SALAR Phase 2: Projects, Memory, Artifacts — Implementation Plan

**Date:** 2026-08-29/30
**Status:** Planning
**Related Specs:** 
- `docs/superpowers/specs/2026-08-13-salar-master-roadmap.md`
- `docs/superpowers/specs/2026-08-11-salar-capability-platform-design.md`
- `docs/superpowers/specs/2026-08-11-salar-agent-platform-design.md`

## Feature Breakdown

### 1. Artifacts — Media Analysis & Attachments

**Purpose:** Enable conversation-bound uploads, extraction, and analysis of files.

**UI Components:**
- `frontend/src/workspace/ArtifactUploader.tsx` — attachment chip previews pre-send
- `frontend/src/components/MediaPreview.tsx` — image/PDF preview thumbnails
- `frontend/src/components/FileAttachment.tsx` — drag-and-drop zone in composer

**API Endpoints:**
- `backend/app/api/attachments.py`:
  - `POST /attachments/upload` — validate, store, extract metadata
  - `GET /attachments/{id}` — deliver analysis result
  - `DELETE /attachments/{id}` — cleanup
  - Support: image (eval), PDF (text/pdf), DOCX (text), txt, md, json, code files

**Data Model:**
```python
class Attachment(Base):
    id: UUID
    user_id: UUID
    conversation_id: UUID | None
    filename: str
    size: int
    mime_type: str
    local_path: str
    analysis: dict | None
    created_at: datetime
```

**Implementation Order:**
1. Upload endpoint with validation
2. Extraction handlers (PDF, DOCX, images)
3. Composer UI integration
4. Analysis context in chat responses

### 2. Memory — Graph + Categories

**Purpose:** Persistent memory system with typed categories and relationships.

**Memory Types (from roadmap Phase 3):**
- `short-term`: last 24h, auto-expire
- `long-term`: user-pinned, searchable
- `project`: scoped to project/workspace
- `personal`: user preferences, patterns
- `vault`: sensitive data, encrypted

**UI Components:**
- `frontend/src/workspace/MemorySidebar.tsx` — memory timeline in sidebar
- `frontend/src/components/MemoryCard.tsx` — individual memory display
- `frontend/src/views/MemoryView.tsx` — full memory browsing/search

**API Endpoints:**
- `backend/app/api/memos.py`:
  - `GET /memories` — query with filters (type, project, tag)
  - `POST /memories` — create memory with relation-links
  - `PUT /memories/{id}` — update content/tags
  - Graph queries: `GET /memories/graph?node={id}` and `--link` params

**Data Model:**
```python
class Memory(Base):
    id: UUID
    user_id: UUID
    type: str  # short-term, long-term, project, personal, vault
    project_id: UUID | None
    content: str
    tags: list[str]
    related_to: list[UUID]  # links to other memories
    strength: float  # relevance score
    expires_at: datetime | None
    encrypted: bool = False
    created_at: datetime
```

### 3. Projects — Workspace-Level Containers

**Purpose:** Project "spaces" as persisted containers for files, chats, tools.

**UI Components:**
- `frontend/src/workspace/ProjectList.tsx` — project sidebar rail item
- `frontend/src/views/ProjectsView.tsx` — project dashboard
- `frontend/src/components/ProjectCard.tsx` — project summary tile

**API Endpoints:**
- `backend/app/api/projects.py`:
  - `GET /projects` — list all accessible projects
  - `POST /projects` — create new project
  - `GET /projects/{id}` — get project details
  - `PATCH /projects/{id}` — update metadata

**Data Model:**
```python
class Project(Base):
    id: UUID
    user_id: UUID
    name: str
    description: str | None
    icon: str  # emoji or tint
    created_at: datetime
    updated_at: datetime
```

## Dependencies

- **Artifacts** can be built first (self-contained in composer)
- **Memory** needs artifacts as source material
- **Projects** integrates both but could ship independently

## Test Plan

1. Unit tests for API endpoints (backend)
2. Vitest for frontend components (memory, projects, file upload)
3. Contract tests for data schemas
4. E2E flow: attach file → memory → project

## Rough Effort Estimate

| Feature | Frontend | Backend | Tests |
|---------|----------|---------|-------|
| Artifacts | 4d | 3d | 2d |
| Memory | 5d | 4d | 3d |
| Projects | 3d | 2d | 2d |

**Total:** ~16 days dev + 9 days testing (staggered across phases)

## Runner Tasks

Phase 2 tasks can now be dispatched. Run Phase 2 planning via `to-issues` to create tickets.

---

## Phase 2 Implementation Tickets

### Ticket 1: Artifact Upload API Endpoint
- **Frontend:** none (backend-first for API-first design)
- **Backend:** Create `backend/app/api/attachments.py`
  - `POST /attachments/upload` — validate, store to `data/uploads/`, extract metadata
  - Types: images (store as-is), PDF/DOCX (extract text via PyPDF), txt/md/json (parse)
  - Security: validate MIME, limit 20MB, sanitize filename
  - Return: `{id, filename, size, mime_type, preview_url?}`
- **Tests:** pytest unit tests for validation, extraction

### Ticket 2: Composer Attachment UI
- **Frontend:** `frontend/src/workspace/AttachmentPicker.tsx`
  - Button opens file browser, camera for images
  - Shows upload chips with progress, filename, size
  - Handles cancel/retry
- **Integration:** `frontend/src/workspace/Composer.tsx`
  - Add attachment button next to textbox
  - Show chip previews when files selected
  - Send files array with message
- **Tests:** vitest for chips, upload state

### Ticket 3: Memory Table Schema
- **Backend:** `backend/app/models/memory.py`
  - SQLAlchemy model with fields: id, user_id, type, content, tags, related_to, strength, expires_at, encrypted, created_at
  - Migration to add table (no data loss since new table)
- **Tests:** alembic migration test, model tests

### Ticket 4: Memory API Endpoints
- **Backend:** `backend/app/api/memos.py`
  - `GET /memories` with query params: type, project_id, search, limit, offset
  - `POST /memories` — create with content, tags, relations
  - `GET /memories/{id}` — get single memory + linked memories
  - `PUT /memories/{id}` — update
  - Graph endpoint: `GET /memories/graph?node={id}` returning connected memories
- **Tests:** fastapi testclient + contract tests

### Ticket 5: Memory Cache Service
- **Backend:** `backend/app/services/memory_service.py`
  - SQLite primary store, ChromaDB semantic fallback for search
  - Ranking function based on recency, tags, strength
- **Tests:** integration tests for search

### Ticket 6: Memory Sidebar Component
- **Frontend:** `frontend/src/workspace/MemorySidebar.tsx`
  - Collapsible section in workspace rail
  - Shows recent memories with icons per type
  - Quick search input
- **Styles:** Add to `workspace.css`

### Ticket 7: Projects CRUD API
- **Backend:** `backend/app/api/projects.py`
  - `GET /projects` — list user's projects
  - `POST /projects` — create with name, description, icon
  - `GET /projects/{id}` — details including member count
  - `PATCH /projects/{id}` — update
  - `DELETE /projects/{id}` — soft delete
- **Tests:** endpoint tests

### Ticket 8: Projects View
- **Frontend:** `frontend/src/views/ProjectsView.tsx`
  - Grid of project cards with cover image, name, last activity
  - FAB to create new project
- **Sidebar:** Add Projects nav item in workspace rail

### Ticket 9: Artifacts Analysis Integration
- **Backend:** Add to attachment upload
  - For images: send to vision model for description
  - For text: extract key points
  - Store analysis result in memory as "artifact-metadata" memory
- **Frontend:** In chat, show "Analyzed with:" message after upload

### Ticket 10: Memory-Project Linking
- **Frontend:** Add "Save to project" option on memory/actions
- **Backend:** Update memory create to accept project_id
- **API:** Project detail includes memories count/list

---

*Estimated: 10 tickets, ~34 dev days + testing*