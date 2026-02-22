# Weeek API Reference (Gifty Integration)

This document describes the Weeek API integration used in Gifty to provide live implementation status in the documentation.

## Base URL
`https://api.weeek.net/public/v1`

## Authentication
Bearer Token in `Authorization` header.
Token is managed via `WEEEK_API_TOKEN` environment variable.

## Used Endpoints

### Task Management (TM)

#### [GET] `/tm/tasks`
- **Purpose**: Fetch tasks for a project/board/tags.
- **Gifty Proxy**: `GET /api/v1/integrations/weeek/tasks`

#### [GET] `/tm/tasks/:id`
- **Purpose**: Fetch a single task detail.

#### [POST] `/tm/tasks`
- **Purpose**: Create a new task.

#### [PUT] `/tm/tasks/:id`
- **Purpose**: Update an existing task.

#### [DELETE] `/tm/tasks/:id`
- **Purpose**: Delete a task.

#### [POST] `/tm/tasks/:id/complete`
- **Purpose**: Mark a task as completed.

#### [POST] `/tm/tasks/:id/un-complete`
- **Purpose**: Mark a task as incomplete.

#### [POST] `/tm/tasks/:id/board`
- **Purpose**: Move task to another board.

#### [POST] `/tm/tasks/:id/board-column`
- **Purpose**: Move task to another column.

#### [POST/DELETE] `/tm/tasks/:id/assignees`
- **Purpose**: Manage task assignees.

### Board & Column Management

#### [GET] `/tm/boards`
- **Purpose**: List boards (supports `projectId` filter).

#### [POST] `/tm/boards`
- **Purpose**: Create a new board.

#### [DELETE] `/tm/boards/:id`
- **Purpose**: Delete a board.

#### [GET] `/tm/board-columns`
- **Purpose**: List columns for a board.

#### [POST/PUT/DELETE] `/tm/board-columns`
- **Purpose**: Manage columns within a board.

### Workspace & Tags (WS)

#### [GET] `/ws/tags`
- **Purpose**: List all workspace tags.

#### [POST] `/ws/tags`
- **Purpose**: Create a new tag.

## Gifty Integration Logic

### Backend Proxy (`app/routes/integrations.py`)
To avoid exposing the API key to the frontend, all documentation requests are proxied through our backend.

### Cleanup Script (`scripts/cleanup_weeek.py`)
A maintenance script to remove duplicate boards and maintain workspace hygiene.

### Frontend Widget (`docs/javascripts/weeek.js`)
A lightweight JS component that scans for `<div class="weeek-tracker">` and renders a live status list.
It supports:
- `data-project-id`
- `data-tags` (by ID)
- `data-tag-names` (by name, resolved on backend)
