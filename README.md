<div align="center">

# Señorita

**Personal AI Chief of Staff**

*Remember what matters. Handle what doesn't.*

[![Phase 1](https://img.shields.io/badge/Phase-1%20Complete-brightgreen?style=flat-square)](#roadmap)
[![Stack](https://img.shields.io/badge/Stack-Tauri%20%7C%20Next.js%20%7C%20FastAPI%20%7C%20Gemini-blue?style=flat-square)](#tech-stack)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-lightgrey?style=flat-square)](#getting-started)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## What is Señorita?

Señorita is a personal AI that knows your context, remembers your life, anticipates what you need, and takes action on your behalf. It is **not** a chatbot, not a to-do app, not a reminder tool. It sits above your communication, calendar, tasks, relationships, and commitments — and continuously builds an understanding of your life so you manage less of it manually.

```
                    SEÑORITA
                       │
          ┌────────────┼────────────┐
          │            │            │
       REMEMBER     ANTICIPATE      ACT
          │            │            │
          ▼            ▼            ▼
       Context      Timing         Tools
       People       Events         Messages
       History      Changes        Bookings
       Preferences  Deadlines      Payments
       Promises     Opportunities  Drafts
```

> **North star:** the user says "Señorita, handle it" — and Señorita resolves the ambiguous "it" from context, memory, and recent conversation.

---

## Features (Built)

| Module | Feature |
|---|---|
| ✅ Always-On Service | Auto-start on login (launchd / NSSM), auto-restart on crash, health check |
| ✅ Desktop Shell | Tauri system tray with live status, routing shortcuts, Pause/Resume |
| ✅ AI Chat | Natural-language interface backed by Gemini + long-term memory retrieval |
| ✅ Voice Input | Microphone button → STT → same orchestrator as text — no forked logic |
| ✅ Long-Term Memory | Semantic vector search via pgvector; categories: person, preference, date, promise, context |
| ✅ Implicit Memory Capture | Background LLM evaluator on every conversation, sensitivity-controlled |
| ✅ Task Management | CRUD with due dates, priorities, contact links, reminder bindings |
| ✅ Reminder System | Time/date/recurring reminders; APScheduler polling; desktop tray dispatch |
| ✅ Calendar | Event storage, conflict detection, conflict surfacing |
| ✅ Proactive Engine | 15-min polling cycle; date-memory, stalled-task, calendar-conflict checks; daily cap |
| ✅ Notifications Log | Audit trail of every proactive dispatch with trigger type and message |
| ✅ Dashboard UI | JARVIS-aesthetic Next.js frontend; glassmorphism + sharp-corner HUD design |
| ✅ Pause / Resume | Global pause flag that halts all background workers without killing the process |
| ✅ Activity Log | Every action recorded with type, payload, result, and confirmation status |

---

## Architecture

> Deep technical reference for the system design, data model, agent flow, worker topology, and integration boundaries.

### System Overview

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

### 4.2 Component Map

| Component | Path | Language | Purpose |
|---|---|---|---|
| FastAPI Backend | `backend/` | Python 3.12 | REST API, agent orchestration, workers |
| Next.js Frontend | `frontend/` | TypeScript | Dashboard, chat, memory, tasks UI |
| Tauri Shell | `desktop/` | Rust + TypeScript | Native desktop wrapper, system tray |
| PostgreSQL | (Docker / managed) | SQL | Persistent storage |
| Alembic | `database/migrations/` | Python | Schema versioning |
| launchd Agent | `infrastructure/macos/` | XML + Bash | macOS auto-start |
| NSSM Service | `infrastructure/windows/` | XML + PowerShell | Windows auto-start |

### 4.3 Repository Layout

```
senorita/
├── backend/
│   ├── agents/              # Gemini client, orchestrator, tool registry, prompts
│   ├── api/                 # FastAPI route handlers (14 routers)
│   ├── core/                # Config (pydantic-settings), security, global state
│   ├── db/
│   │   ├── models/          # SQLAlchemy ORM models (11 tables)
│   │   └── session.py       # Async engine + session factory
│   ├── memory/              # Embedding helpers (pgvector)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic layer
│   └── workers/
│       ├── memory_capture/  # Implicit memory background evaluator
│       ├── monitoring/      # Proactive engine
│       ├── notifications/   # Unified dispatch stub → Tauri bridge
│       └── reminders/       # APScheduler reminder poller
├── database/
│   └── migrations/          # Alembic (env.py + versions/)
├── desktop/
│   └── src-tauri/
│       ├── src/
│       │   ├── main.rs      # App entry, health-poll thread, tray event loop
│       │   └── tray.rs      # System tray menu, navigate events, status indicator
│       └── Cargo.toml
├── frontend/
│   └── app/
│       ├── chat/            # AI chat UI with voice mic button (MediaRecorder)
│       ├── tasks/           # Task management view
│       ├── memory/          # Memory browser
│       ├── calendar/        # Calendar view
│       ├── activity/        # Audit log view
│       └── components/      # AuthContext, SectionReveal animation, shared UI
├── infrastructure/
│   ├── macos/
│   │   ├── com.senorita.backend.plist  # launchd LaunchAgent
│   │   └── install.sh                  # Copies + loads the plist
│   └── windows/
│       ├── senorita-service.xml         # NSSM service descriptor
│       └── install.ps1                  # Registers as Windows Service
└── docker-compose.yml       # PostgreSQL + pgvector (dev)
```

### 4.4 Backend Internals

```
backend/
├── main.py               ← FastAPI app, lifespan (starts APScheduler)
├── core/
│   ├── config.py         ← pydantic-settings: env vars, all tunables
│   ├── security.py       ← JWT creation/validation, get_current_user dep
│   └── state.py          ← global is_paused flag
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

#### Startup Sequence

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

### 4.5 Agent Orchestrator

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

#### Tool Registry

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

### 4.6 Memory System

#### Storage

- **Table:** `memory_entries`
- **Embedding column:** `embedding vector(3072)` via `pgvector`
- **Embedding model:** `text-embedding-004` (Google)

#### Categories

| Category | Examples |
|---|---|
| `person` | "Rahul is my business partner at Coderz" |
| `preference` | "Jay prefers window seats on flights" |
| `date` | "Mom's birthday is August 12, she loves vintage scarves" |
| `promise` | "Told Disha I'd send the contract by Friday" |
| `context` | "Working on a fintech MVP, deadline end of month" |

#### Retrieval

```sql
SELECT content, category, importance_score
FROM memory_entries
WHERE user_id = $1 AND status = 'active' AND locked = false
ORDER BY embedding <-> $2          -- pgvector cosine/L2 distance
LIMIT 5;
```

#### Implicit Capture

Every conversation turn is evaluated:

```
LLM prompt: "Does this text contain a durable fact worth remembering?
             Rate importance 0.0–1.0. If > threshold, extract the fact."
threshold: conservative=0.6, proactive=0.4, off=disabled
```

The `memory_capture_sensitivity` field on `User` controls the per-user threshold.

### 4.7 Background Workers

All workers share one `AsyncIOScheduler` instance (started in `main.py` lifespan). All workers **check `get_pause_state()` first** and return immediately if the system is paused.

| Worker | Schedule | Checks |
|---|---|---|
| **Reminder Scheduler** | Every 60s | Fire time/date reminders past due |
| **Proactive Engine** | Every 15 min (configurable) | Memory dates, stalled tasks, calendar conflicts |
| **Memory Capture** | Per conversation | Evaluate implicit memory candidates |

#### 4.7.1 Reminder Scheduler (`workers/reminders/scheduler.py`)

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

#### 4.7.2 Proactive Engine (`workers/monitoring/proactive_engine.py`)

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
```sql
SELECT * FROM memory_entries
WHERE user_id = ? AND category = 'date'
  AND locked = false AND importance_score >= 0.3
  AND status = 'active';
→ For each: Gemini extracts date from content text
→ Include if now ≤ date ≤ now + PROACTIVE_WINDOW_DAYS
```

**Check B — Stalled Tasks:**
```sql
SELECT * FROM tasks
WHERE user_id = ? AND status = 'pending'
  AND due_at BETWEEN now AND now + 24h;
→ Cross-reference action_log: any entries in last 3 days?
→ If none: candidate with importance from priority mapping
```

**Check C — Calendar Conflicts:**
```sql
SELECT * FROM calendar_events
WHERE user_id = ? AND surfaced = false
  AND conflict_flags != '[]';
→ Candidate at fixed importance 0.85
→ Post-dispatch: mark surfaced = true
```

#### 4.7.3 Memory Capture (`workers/memory_capture/`)

Called inline by `orchestrator.handle_message()` after every conversation turn:

```
evaluate(session, user, conversation_text)
→ LLM importance scoring
→ if score >= user.threshold:
     embed(extracted_fact) → INSERT memory_entries
```

#### 4.7.4 Unified Notification Dispatch (`workers/notifications/dispatch.py`)

Single function used by **both** the reminder scheduler and the proactive engine:

```python
async def dispatch_notification(title: str, message: str, payload: dict | None = None):
    logger.info(f"DISPATCH | {title} | {message}")
    print(f"[NOTIFICATION DISPATCHED] {title}: {message}")
    # Phase 2: bridge to Tauri's notification API via IPC
```

### 4.8 Desktop Shell

**Path:** `desktop/src-tauri/`  
**Language:** Rust (Tauri 2.x)

#### `main.rs`

- Builds the Tauri application and sets up the event loop.
- Spawns a background `std::thread` that polls `http://localhost:8000/healthz` every **10 seconds** using `reqwest::blocking`.
- Updates a "Status" tray menu item dynamically:
  - `● System: Online` — HTTP 200
  - `◐ System: Degraded` — HTTP non-200
  - `○ System: Offline` — connection error

#### `tray.rs`

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

### 4.9 Frontend

**Path:** `frontend/`  
**Framework:** Next.js 14 + TypeScript + Vanilla CSS

#### Route Map

| Route | Component | Description |
|---|---|---|
| `/` | Dashboard | Greeting, today's schedule, stats |
| `/chat` | Chat | AI text + voice interface |
| `/tasks` | Tasks | Task list with due dates and priorities |
| `/memory` | Memory | Memory browser with lock/delete |
| `/calendar` | Calendar | Event list with conflict indicators |
| `/activity` | Activity | Action audit log |

#### Design Tokens

```css
--bg-primary:     #070b14;
--border:         rgba(255,255,255,0.09);
--glass-surface:  rgba(255,255,255,0.05);
--font-sans:      'Inter', sans-serif;
--font-display:   'Plus Jakarta Sans', sans-serif;
--font-mono:      'Geist Mono', monospace;
--radius:         0;   /* sharp corners everywhere */
```

#### Voice Input Flow

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

### 4.10 OS Integration (Always-On)

#### macOS — launchd

**File:** `infrastructure/macos/com.senorita.backend.plist`  
**Type:** User LaunchAgent (`~/Library/LaunchAgents/`)

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

#### Windows — NSSM

**File:** `infrastructure/windows/senorita-service.xml`  
**Install:** `infrastructure/windows/install.ps1` (run as Administrator)

```powershell
nssm install senorita-backend python.exe
nssm set senorita-backend AppParameters main.py
nssm set senorita-backend AppRestartDelay 5000
```

> **Note:** The Windows path is written-but-unverified (developed on macOS). Test before deploying to Windows.

### 4.11 Data Model

#### Entity Relationships

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

#### Key Tables

| Table | Key Columns |
|---|---|
| `users` | id, name, timezone, autonomy_level, style_profile, memory_capture_sensitivity |
| `contacts` | id, user_id, name, relationship_type, channels, last_discussed_topic |
| `memory_entries` | id, user_id, content, category, source_ref, confidence, importance_score, locked, embedding `vector(3072)` |
| `tasks` | id, user_id, title, description, due_at, priority, status, project, contact_id, reminder_id |
| `reminders` | id, user_id, type, trigger_payload (JSONB), status |
| `calendar_events` | id, user_id, title, start_at, end_at, attendees, conflict_flags, surfaced |
| `action_log` | id, user_id, action_type, payload, result, confirmed_by_user |
| `conversations` | id, user_id, messages (JSONB), created_at |
| `notification_log` | id, user_id, trigger_type, message, created_at |
| `auth_tokens` | id, user_id, token, expires_at |

#### `memory_entries` DDL

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

#### `notification_log` DDL

```sql
id           UUID PRIMARY KEY
user_id      UUID REFERENCES users
trigger_type TEXT NOT NULL        -- 'memory_date' | 'stalled_task' | 'calendar_conflict'
message      TEXT NOT NULL        -- full notification body with explicit trigger reason
created_at   TIMESTAMPTZ
```

#### `calendar_events` DDL (additional)

```sql
surfaced     BOOLEAN DEFAULT false   -- set true after proactive engine dispatches
conflict_flags JSONB DEFAULT '[]'    -- populated by calendar sync
```

### 4.12 API Surface

#### Authentication

All protected routes require:

```
Authorization: Bearer <JWT>
```

JWT issued by `POST /auth/setup` (name + timezone → user upsert + token).

#### Routes

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

### 4.13 Security & Auth

- **Transport:** All traffic on `localhost` in Phase 1; HTTPS required for production deployment.
- **Auth:** `python-jose` JWT, 24-hour expiry, signed with `SECRET_KEY`.
- **Passwords:** Not stored — Phase 1 uses name+timezone identity; Phase 2+ adds OAuth 2.0.
- **Sensitive memory:** `locked=true` entries excluded from proactive surfacing and from all LLM context injection.
- **Pause state:** In-memory only. Resets to `False` on process restart. Phase 2 will persist to DB.
- **API keys:** Stored in `backend/.env`; never committed to version control.

### 4.14 Key Design Decisions

| Decision | Rationale |
|---|---|
| Single `orchestrator.handle_message()` for text and voice | The voice endpoint does STT then passes plain text here — no forked orchestration logic |
| APScheduler (not Celery) | Lower ops overhead for Phase 1; Celery available in Phase 2+ if distributed workers are needed |
| `google-genai` 1.0.0 pinned | The `interactions` API requires ≥ 2.3.0, which is not yet in the pinned venv; STT uses `models.generate_content` with a multimodal audio Part |
| Unified dispatch at `workers/notifications/dispatch.py` | Both the reminder scheduler and proactive engine call the same function; Phase 2 replaces the stub with a real Tauri IPC bridge without touching callers |
| Alembic under `database/migrations/`, not `backend/` | Keeps DB concerns separate from app code; `env.py` adds `backend/` to `sys.path` at runtime |
| `surfaced` boolean on `CalendarEvent` | Prevents re-dispatching the same conflict notification across successive proactive cycles |
| Importance-first cap enforcement | When cap is hit mid-cycle, *lowest-importance* candidates are skipped — highest-value alerts always dispatch first |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop shell | [Tauri](https://tauri.app/) (Rust) |
| Frontend | [Next.js](https://nextjs.org/) 14 + TypeScript |
| Backend | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12) |
| AI | Google Gemini (`google-genai` 1.0.0) |
| Database | PostgreSQL 17 + [pgvector](https://github.com/pgvector/pgvector) |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Background jobs | APScheduler 3.10 |
| Auth | JWT (python-jose) + Bearer tokens |
| Styling | Vanilla CSS — JARVIS/HUD aesthetic; Inter + Plus Jakarta Sans + Geist Mono |
| OS integration | macOS launchd · Windows NSSM |

---

## Getting Started

### Prerequisites

- **macOS** or **Windows**
- Python 3.12, Node.js 18+, Rust (for Tauri)
- PostgreSQL 17 with the pgvector extension **or** Docker

### 1. Start the Database

```bash
docker compose up -d db
```

Or point `DATABASE_URL` in `backend/.env` at an existing Postgres 17 + pgvector instance.

### 2. Configure Environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env — at minimum set GEMINI_API_KEY
```

Key variables:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | **Required.** Google Gemini API key |
| `DATABASE_URL` | `postgresql+asyncpg://senorita:senorita@localhost:5432/senorita` | Async DB URL |
| `SECRET_KEY` | `change-me` | JWT signing secret |
| `PORT` | `8000` | Backend listen port |
| `PROACTIVE_CHECK_INTERVAL_SECONDS` | `900` | Proactive engine poll interval (15 min) |
| `PROACTIVE_WINDOW_DAYS` | `21` | Memory date look-ahead window |
| `DAILY_NOTIFICATION_CAP` | `5` | Max proactive notifications per user per day |

### 3. Backend

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Apply DB migrations
cd ../database/migrations && alembic upgrade head
# Start
cd ../../backend && uvicorn main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

### 5. Desktop (Tauri)

```bash
cd desktop
npm install
npm run tauri dev
```

The Tauri shell polls `http://localhost:8000/healthz` every 10 seconds and updates the tray status indicator (● Online / ◐ Degraded / ○ Offline).

### 6. Always-On Setup (macOS)

```bash
cd infrastructure/macos
chmod +x install.sh && ./install.sh
```

This copies the launchd plist to `~/Library/LaunchAgents/` and loads it. The backend will now auto-start on login and auto-restart on crash.

**Windows** — run `infrastructure/windows/install.ps1` as Administrator (requires [NSSM](https://nssm.cc/)).

---

## Design System

The UI follows a **JARVIS/HUD aesthetic**:

- **Background:** `#070b14`
- **Border:** `rgba(255,255,255,0.09)`
- **Glass surface:** `rgba(255,255,255,0.05)`
- **Border radius:** `0` everywhere — sharp corners throughout
- **Fonts:** Inter (body) · Plus Jakarta Sans (headings) · Geist Mono (monospace/labels)
- **Clip paths:** angled `polygon()` cuts on cards, buttons, and message bubbles
- **Motion:** `SectionReveal` — `fadeScale` with blur + y + scale entrance on page load

---

## Autonomy Levels

| Level | Name | Behavior |
|---|---|---|
| 1 | Passive | Only answers when asked |
| **2** | **Helpful** | **Proactively surfaces reminders ← default** |
| 3 | Proactive | Drafts actions automatically for review |
| 4 | Trusted | Auto-executes pre-approved action types |
| 5 | Autonomous | Handles entire predefined categories independently |

---

## License

MIT © Jay D. Chothiyawala

