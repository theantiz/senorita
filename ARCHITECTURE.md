# Señorita — Architecture

> Deep technical reference for the system design, data model, agent flow, worker topology, and integration boundaries.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Component Map](#2-component-map)
3. [Backend Internals](#3-backend-internals)
4. [Agent Orchestrator](#4-agent-orchestrator)
5. [Memory System](#5-memory-system)
6. [Background Workers](#6-background-workers)
7. [Desktop Shell](#7-desktop-shell)
8. [Frontend](#8-frontend)
9. [OS Integration (Always-On)](#9-os-integration-always-on)
10. [Data Model](#10-data-model)
11. [API Surface](#11-api-surface)
12. [Security & Auth](#12-security--auth)
13. [Key Design Decisions](#13-key-design-decisions)
14. [Phase 2 Integration Boundaries](#14-phase-2-integration-boundaries)

---

## 1. System Overview

```
┌───────────────────────────────────────────────────────────────┐
│  User surfaces                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ Tauri Desktop│  │  Next.js Web │  │  Voice (browser  │    │
│  │ + System Tray│  │  Dashboard   │  │  MediaRecorder)  │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘    │
└─────────┼─────────────────┼───────────────────┼──────────────┘
          │                 │                   │
          └─────────────────┼───────────────────┘
                            │ HTTP/REST (port 8000)
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  FastAPI Backend                                              │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  API Routes │  │  AI Agent    │  │  Background Workers  │ │
│  │  (14 routers│  │  Orchestrator│  │  APScheduler         │ │
│  │   + auth)   │  │  + Gemini    │  │  ├ Reminder Scheduler│ │
│  └──────┬──────┘  └──────┬───────┘  │  ├ Proactive Engine  │ │
│         │                │          │  └ Memory Capture    │ │
│         └────────┬────────┘          └──────────┬───────────┘ │
│                  │                              │             │
│                  ▼                              ▼             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  PostgreSQL 17 + pgvector                              │  │
│  │  11 tables · vector(3072) embeddings · JSONB payloads  │  │
│  └────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
          │
          ▼
┌───────────────────────────────────────────────────────────────┐
│  OS Layer                                                     │
│  macOS: launchd LaunchAgent (KeepAlive=true, RunAtLoad=true)  │
│  Windows: NSSM Windows Service (restart-on-failure)           │
└───────────────────────────────────────────────────────────────┘
```

---

## 2. Component Map

| Component | Path | Language | Purpose |
|---|---|---|---|
| FastAPI Backend | `backend/` | Python 3.12 | REST API, agent orchestration, workers |
| Next.js Frontend | `frontend/` | TypeScript | Dashboard, chat, memory, tasks UI |
| Tauri Shell | `desktop/` | Rust + TypeScript | Native desktop wrapper, system tray |
| PostgreSQL | (Docker / managed) | SQL | Persistent storage |
| Alembic | `database/migrations/` | Python | Schema versioning |
| launchd Agent | `infrastructure/macos/` | XML + Bash | macOS auto-start |
| NSSM Service | `infrastructure/windows/` | XML + PowerShell | Windows auto-start |

---

## 3. Backend Internals

```
backend/
├── main.py               ← FastAPI app, lifespan (starts APScheduler)
├── core/
│   ├── config.py         ← pydantic-settings: env vars, all tunables
│   ├── security.py       ← JWT creation/validation, get_current_user dep
│   └── state.py          ← global is_paused flag (Module 7)
├── db/
│   ├── base.py           ← SQLAlchemy declarative base
│   ├── session.py        ← async engine + async_session_factory
│   └── models/           ← 11 ORM model files + __init__.py
├── api/
│   ├── routes_auth.py    ← POST /auth/setup
│   ├── routes_chat.py    ← POST /chat, POST /chat/voice
│   ├── routes_tasks.py   ← /tasks CRUD
│   ├── routes_reminders.py
│   ├── routes_calendar.py
│   ├── routes_memory.py
│   ├── routes_contacts.py
│   ├── routes_activity.py
│   ├── routes_health.py  ← GET /healthz
│   └── routes_system.py  ← PATCH /system/pause, /resume, GET /status
├── agents/
│   ├── gemini_client.py  ← get_client(), call_model()
│   ├── orchestrator.py   ← handle_message() — single entry for all chat
│   ├── tool_registry.py  ← Gemini function declarations
│   └── prompts.py        ← System prompt construction
├── memory/
│   └── embeddings.py     ← embed_text() via Gemini text-embedding-004
├── workers/
│   ├── reminders/
│   │   └── scheduler.py  ← APScheduler job: check_reminders every 60s
│   ├── monitoring/
│   │   └── proactive_engine.py  ← APScheduler job: proactive_check every 15min
│   ├── memory_capture/
│   │   └── capture.py    ← LLM importance scoring on every conversation turn
│   └── notifications/
│       └── dispatch.py   ← Single dispatch function (stub → Tauri bridge)
└── requirements.txt
```

### Startup Sequence

```
uvicorn main:app
  └─ lifespan()
       ├─ Base.metadata.create_all()     # idempotent table creation
       ├─ start_scheduler_in_background()
       │    ├─ scheduler.add_job(check_reminders, interval=60s)
       │    └─ scheduler.start()  →  returns scheduler instance
       └─ start_proactive_engine(scheduler)
            └─ scheduler.add_job(proactive_check, interval=900s)
```

---

## 4. Agent Orchestrator

`backend/agents/orchestrator.py` — **single entry point for all user messages**, whether originated from text chat or voice transcription. No forked logic between input modalities.

```
handle_message(session, user, text)
       │
       ├─ 1. embed_text(text)  →  query_embedding (3072-dim)
       │
       ├─ 2. semantic search memory_entries
       │      WHERE user_id = ? AND status = 'active'
       │      ORDER BY embedding <-> query_embedding LIMIT 5
       │
       ├─ 3. load recent conversation history
       │
       ├─ 4. build system prompt
       │      (user profile + retrieved memories + conversation history)
       │
       ├─ 5. call_model(prompt, tools=tool_registry.declarations)
       │      → Gemini 2.0 Flash
       │
       ├─ 6. if response contains tool_call:
       │         execute_tool(name, args)  →  DB write or side-effect
       │         call_model again with tool result
       │
       ├─ 7. memory_capture.evaluate(text, response)
       │      → score importance → write MemoryEntry if above threshold
       │
       ├─ 8. persist conversation turn to conversations table
       │
       └─ 9. return response_text  →  caller returns {"response": ...}
```

### Tool Registry

Tools exposed to Gemini (function calling):

| Tool | Action |
|---|---|
| `create_reminder` | Insert into `reminders` |
| `create_task` | Insert into `tasks` |
| `save_memory` | Insert into `memory_entries` |
| `delete_memory` | Soft-delete/hard-delete memory entry |
| `get_tasks` | Query pending tasks |
| `get_reminders` | Query active reminders |
| `get_calendar` | Query upcoming events |
| `get_contacts` | Query relationship graph |

---

## 5. Memory System

### Storage

- **Table:** `memory_entries`
- **Embedding column:** `embedding vector(3072)` via `pgvector`
- **Embedding model:** `text-embedding-004` (Google)

### Categories

| Category | Examples |
|---|---|
| `person` | "Rahul is my business partner at Coderz" |
| `preference` | "Jay prefers window seats on flights" |
| `date` | "Mom's birthday is August 12, she loves vintage scarves" |
| `promise` | "Told Disha I'd send the contract by Friday" |
| `context` | "Working on a fintech MVP, deadline end of month" |

### Retrieval

```sql
SELECT content, category, importance_score
FROM memory_entries
WHERE user_id = $1 AND status = 'active' AND locked = false
ORDER BY embedding <-> $2          -- pgvector cosine/L2 distance
LIMIT 5;
```

### Implicit Capture (Module 4 / 8)

Every conversation turn is evaluated:
```
LLM prompt: "Does this text contain a durable fact worth remembering?
             Rate importance 0.0–1.0. If > threshold, extract the fact."
threshold: conservative=0.6, proactive=0.4, off=disabled
```

The `memory_capture_sensitivity` field on `User` controls the per-user threshold.

---

## 6. Background Workers

All workers share one `AsyncIOScheduler` instance (started in `main.py` lifespan).  
All workers **check `get_pause_state()` first** and return immediately if the system is paused.

### 6.1 Reminder Scheduler (`workers/reminders/scheduler.py`)

```
Interval: 60 seconds

For each Reminder WHERE status = 'active':
  Resolve user timezone
  Parse trigger_payload.datetime (ISO 8601)
  If now >= trigger_dt:
    reminder.status = 'fired'
    dispatch_notification(title, message, payload)
commit()
```

### 6.2 Proactive Engine (`workers/monitoring/proactive_engine.py`)

```
Interval: PROACTIVE_CHECK_INTERVAL_SECONDS (default 900s = 15 min)

For each User:
  daily_count = COUNT(notification_log WHERE user_id AND today)
  remaining   = DAILY_NOTIFICATION_CAP − daily_count
  if remaining <= 0: skip

  candidates = []
  candidates += check_memory_dates(user)    # Check A
  candidates += check_stalled_tasks(user)   # Check B
  candidates += check_calendar_conflicts(user)  # Check C

  Sort candidates by importance_score DESC
  For top `remaining` candidates:
    compose_notification(trigger_type, context)   ← Gemini call
    INSERT notification_log(user_id, trigger_type, message)
    dispatch_notification(title, message, payload)
    if post_fn: post_fn()   # e.g. mark calendar event surfaced=true

  Skipped candidates: NOT marked processed → re-surface tomorrow
commit()
```

**Check A — Memory Dates:**
```
SELECT * FROM memory_entries
WHERE user_id = ? AND category = 'date'
  AND locked = false AND importance_score >= 0.3
  AND status = 'active';
→ For each: Gemini extracts date from content text
→ Include if now ≤ date ≤ now + PROACTIVE_WINDOW_DAYS
```

**Check B — Stalled Tasks:**
```
SELECT * FROM tasks
WHERE user_id = ? AND status = 'pending'
  AND due_at BETWEEN now AND now + 24h;
→ Cross-reference action_log: any entries in last 3 days?
→ If none: candidate with importance from priority mapping
```

**Check C — Calendar Conflicts:**
```
SELECT * FROM calendar_events
WHERE user_id = ? AND surfaced = false
  AND conflict_flags != '[]';
→ Candidate at fixed importance 0.85
→ Post-dispatch: mark surfaced = true
```

### 6.3 Memory Capture (`workers/memory_capture/`)

Called inline by `orchestrator.handle_message()` after every conversation turn:
```
evaluate(session, user, conversation_text)
→ LLM importance scoring
→ if score >= user.threshold:
     embed(extracted_fact) → INSERT memory_entries
```

### 6.4 Unified Notification Dispatch (`workers/notifications/dispatch.py`)

Single function used by **both** the reminder scheduler and the proactive engine:
```python
async def dispatch_notification(title: str, message: str, payload: dict | None = None):
    logger.info(f"DISPATCH | {title} | {message}")
    print(f"[NOTIFICATION DISPATCHED] {title}: {message}")
    # Phase 2: bridge to Tauri's notification API via IPC
```

---

## 7. Desktop Shell

**Path:** `desktop/src-tauri/`  
**Language:** Rust (Tauri 2.x)

### `main.rs`

- Builds the Tauri application and sets up the event loop.
- Spawns a background `std::thread` that polls `http://localhost:8000/healthz` every **10 seconds** using `reqwest::blocking`.
- Updates a "Status" tray menu item dynamically:
  - `● System: Online` — HTTP 200
  - `◐ System: Degraded` — HTTP non-200
  - `○ System: Offline` — connection error

### `tray.rs`

Custom tray menu with items:

```
● System: Online          ← dynamic, updated by health-poll thread
─────────────────────────
  Ask Señorita
  Open Dashboard
─────────────────────────
  Today's Briefing
  Handled Today
─────────────────────────
  Tasks
  Calendar
  Memory
  Connections
  Activity
─────────────────────────
  ⏸ Pause Assistant      ← PATCH /system/pause
  ▶ Resume Assistant     ← PATCH /system/resume
─────────────────────────
  Settings
  Quit
```

Tray clicks emit a `navigate` Tauri event consumed by the frontend router — no hard page reloads.

---

## 8. Frontend

**Path:** `frontend/`  
**Framework:** Next.js 14 + TypeScript + Vanilla CSS

### Route Map

| Route | Component | Description |
|---|---|---|
| `/` | Dashboard | Greeting, today's schedule, stats |
| `/chat` | Chat | AI text + voice interface |
| `/tasks` | Tasks | Task list with due dates and priorities |
| `/memory` | Memory | Memory browser with lock/delete |
| `/calendar` | Calendar | Event list with conflict indicators |
| `/activity` | Activity | Action audit log |

### Design Tokens

```css
--bg-primary:     #070b14;
--border:         rgba(255,255,255,0.09);
--glass-surface:  rgba(255,255,255,0.05);
--font-sans:      'Inter', sans-serif;
--font-display:   'Plus Jakarta Sans', sans-serif;
--font-mono:      'Geist Mono', monospace;
--radius:         0;   /* sharp corners everywhere */
```

### Voice Input Flow

```
[MIC button] pressed
  └─ navigator.mediaDevices.getUserMedia({ audio: true })
  └─ new MediaRecorder(stream)
  └─ recorder.start()

[STOP button] pressed
  └─ recorder.stop() → onstop fires
  └─ Blob(chunks, { type: 'audio/webm' })
  └─ FormData.append('audio', blob, 'voice.webm')
  └─ POST /chat/voice

Backend:
  └─ types.Part.from_bytes(audio_bytes, mime_type)
  └─ models.generate_content([audio_part, transcription_prompt])
  └─ if "UNCLEAR_AUDIO": return clarification request
  └─ else: orchestrator.handle_message(transcribed_text)
  └─ return { response, transcription }

Frontend:
  └─ update last user bubble text: "[Voice] {transcription}"
  └─ append assistant bubble: response
```

---

## 9. OS Integration (Always-On)

### macOS — launchd

**File:** `infrastructure/macos/com.senorita.backend.plist`  
**Type:** User LaunchAgent (`~/Library/LaunchAgents/`)

Key plist keys:

| Key | Value | Effect |
|---|---|---|
| `RunAtLoad` | `true` | Starts on user login |
| `KeepAlive` | `true` | Respawns on crash |
| `ProgramArguments` | `[".venv/bin/python", "main.py"]` | Exact process launched |
| `StandardErrorPath` | `/tmp/com.senorita.backend.err` | Crash log destination |

```bash
# Install
./infrastructure/macos/install.sh

# Uninstall
launchctl unload ~/Library/LaunchAgents/com.senorita.backend.plist
```

### Windows — NSSM

**File:** `infrastructure/windows/senorita-service.xml`  
**Install:** `infrastructure/windows/install.ps1` (run as Administrator)

```powershell
nssm install senorita-backend python.exe
nssm set senorita-backend AppParameters main.py
nssm set senorita-backend AppRestartDelay 5000
```

> **Note:** The Windows path is written-but-unverified (developed on macOS). Test before deploying to Windows.

---

## 10. Data Model

### Entity Relationships

```
users
  ├── contacts          (1:N)
  ├── memory_entries    (1:N)  ← embedding vector(3072)
  ├── tasks             (1:N)
  ├── reminders         (1:N)
  ├── calendar_events   (1:N)
  ├── action_log        (1:N)
  ├── conversations     (1:N)
  ├── notification_log  (1:N)
  └── auth_tokens       (1:N)

tasks
  ├── contacts          (N:1, optional)
  └── reminders         (N:1, optional)
```

### Key Tables

#### `memory_entries`
```sql
id               UUID PRIMARY KEY
user_id          UUID REFERENCES users
content          TEXT NOT NULL
category         TEXT CHECK IN ('person','preference','date','promise','context')
source_ref       TEXT             -- which conversation/channel
confidence       FLOAT
importance_score FLOAT            -- 0.0–1.0
locked           BOOLEAN DEFAULT false
status           TEXT DEFAULT 'active'
embedding        vector(3072)     -- pgvector
created_at       TIMESTAMPTZ
```

#### `notification_log`
```sql
id           UUID PRIMARY KEY
user_id      UUID REFERENCES users
trigger_type TEXT NOT NULL        -- 'memory_date' | 'stalled_task' | 'calendar_conflict'
message      TEXT NOT NULL        -- full notification body with explicit trigger reason
created_at   TIMESTAMPTZ
```

#### `calendar_events`
```sql
surfaced     BOOLEAN DEFAULT false   -- set true after proactive engine dispatches
conflict_flags JSONB DEFAULT '[]'    -- populated by calendar sync
```

---

## 11. API Surface

### Authentication

All protected routes require:
```
Authorization: Bearer <JWT>
```

JWT issued by `POST /auth/setup` (name + timezone → user upsert + token).

### Routes

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/healthz` | ❌ | `{"status":"ok"}` |
| POST | `/auth/setup` | ❌ | Upsert user, return JWT |
| GET | `/tasks` | ✅ | List user tasks |
| POST | `/tasks` | ✅ | Create task |
| GET | `/reminders` | ✅ | List reminders |
| POST | `/reminders` | ✅ | Create reminder |
| GET | `/calendar` | ✅ | List events |
| POST | `/calendar` | ✅ | Create event |
| GET | `/contacts` | ✅ | List contacts |
| GET | `/memory` | ✅ | List memory entries |
| DELETE | `/memory/{id}` | ✅ | Hard-delete memory entry |
| PATCH | `/memory/{id}/lock` | ✅ | Toggle locked flag |
| GET | `/activity` | ✅ | List action log |
| POST | `/chat` | ✅ | Text message → orchestrator |
| POST | `/chat/voice` | ✅ | Audio file → STT → orchestrator |
| PATCH | `/system/pause` | ✅ | Pause all workers |
| PATCH | `/system/resume` | ✅ | Resume all workers |
| GET | `/system/status` | ✅ | Current pause state |

---

## 12. Security & Auth

- **Transport:** All traffic on `localhost` in Phase 1; HTTPS required for production deployment.
- **Auth:** `python-jose` JWT, 24-hour expiry, signed with `SECRET_KEY`.
- **Passwords:** Not stored — Phase 1 uses name+timezone identity; Phase 2+ adds OAuth 2.0.
- **Sensitive memory:** `locked=true` entries excluded from proactive surfacing and from all LLM context injection.
- **Pause state:** In-memory only. Resets to `False` on process restart. Phase 2 will persist to DB.
- **API keys:** Stored in `backend/.env`; never committed to version control.

---

## 13. Key Design Decisions

| Decision | Rationale |
|---|---|
| Single `orchestrator.handle_message()` for text and voice | The voice endpoint does STT then passes plain text here — no forked orchestration logic |
| APScheduler (not Celery) | Lower ops overhead for Phase 1; Celery available in Phase 2+ if distributed workers are needed |
| `google-genai` 1.0.0 pinned | The `interactions` API requires ≥ 2.3.0, which is not yet in the pinned venv; STT uses `models.generate_content` with a multimodal audio Part |
| Unified dispatch at `workers/notifications/dispatch.py` | Both the reminder scheduler and proactive engine call the same function; Phase 2 replaces the stub with a real Tauri IPC bridge without touching callers |
| Alembic under `database/migrations/`, not `backend/` | Keeps DB concerns separate from app code; `env.py` adds `backend/` to `sys.path` at runtime |
| `surfaced` boolean on `CalendarEvent` | Prevents re-dispatching the same conflict notification across successive proactive cycles |
| Importance-first cap enforcement | When cap is hit mid-cycle, *lowest-importance* candidates are skipped — highest-value alerts always dispatch first |

