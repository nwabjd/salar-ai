# SALAR Permission Center — Design

**Feature:** Granular per-category permissions with approval levels for all tool categories.

## Data model

`PermissionProfile` table (one row per user):
- `id` PK, `user_id` FK users.id (unique, cascade)
- Category columns, each `String(16)` with default `"ask"`:
  - `files`, `camera`, `microphone`, `screen`, `browser`, `email`, `calendar`, `terminal`, `system`, `smart_home`
- Levels: `observe` (read-only, no writes) | `suggest` (propose, never execute) | `ask` (ask before acting) | `autonomous` (act freely)
- `created_at`, `updated_at`

Category mapping from tool name (module `services/permissions.py`):
- `files` → `file_*`, `list_files`, `read_file`, `search_files`, `file_write`, `write_file`, `delete_memory`, `delete_*` (file-ish)
- `camera` → camera tools
- `microphone` → stt/mic tools
- `screen` → `screenshot`, screen tools
- `browser` → `browse_page`, `browse_links`, `read_article`
- `email` → `email_send`, email tools
- `calendar` → `calendar_*`
- `terminal` → `run_command`, `code_run`
- `system` → `power_control`, `device_command`, `manage_process`, `set_volume`, `set_brightness`, `media_control`, `window_control`, `open_app`, `open_url`, `get_system_info`
- `smart_home` → smart home tools

## API
- `GET /api/permissions` → current user's profile (categories + levels)
- `PUT /api/permissions` body `{category: level, ...}` → update, return updated
- Errors: 400 on invalid category/level

## Enforcement
- `check_permission(profile, tool, args) -> level` in `services/permissions.py`
- Mission runner: when a step's tool category level is `ask` (or `suggest`/`observe` and the tool writes), the step escalates to `waiting_approval` — same gate as `dangerous`.
- `suggest`/`observe` never execute writes in missions (step denied with note).

## Tests
- Mapping: every known tool → correct category
- Levels default, validation, API GET/PUT, unauthorized access (other user), invalid level 400
- Enforcement: `ask` level gates a mission step, `autonomous` executes it
