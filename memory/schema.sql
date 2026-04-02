-- DIRESO Agenten-System: SQLite Schema
-- Erstellt beim ersten Start automatisch via store.py

-- ── Sessions ──────────────────────────────────────────────────────────────────
-- Eine Session = ein Gespräch oder ein Aufgaben-Kontext
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,          -- UUID4
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    label       TEXT DEFAULT '',           -- Optionaler Name (z.B. "CEO-Gespräch KW14")
    agent_name  TEXT DEFAULT ''            -- Haupt-Agent der Session
);

-- ── Messages ──────────────────────────────────────────────────────────────────
-- Jede Nachricht eines Gesprächsverlaufs
CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,          -- UUID4
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,             -- "user" | "assistant"
    agent_name  TEXT DEFAULT '',           -- Welcher Agent hat geantwortet?
    content     TEXT NOT NULL,
    tool_calls  TEXT DEFAULT '[]',         -- JSON-Array der Tool-Calls
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- ── Board Briefings ───────────────────────────────────────────────────────────
-- CEO-Briefings die an andere Agenten weitergeleitet werden
CREATE TABLE IF NOT EXISTS board_briefings (
    id              TEXT PRIMARY KEY,      -- UUID4
    session_id      TEXT,
    decision        TEXT NOT NULL,         -- Kern-Entscheidung
    rationale       TEXT DEFAULT '',       -- Begründung
    actions_json    TEXT DEFAULT '{}',     -- JSON: {"cfo": "Aufgabe", ...}
    priority        TEXT DEFAULT 'normal', -- "low" | "normal" | "high" | "urgent"
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- ── Workspace Artifacts ───────────────────────────────────────────────────────
-- Tracking von workspace/-Dateien die Agenten erstellt haben
CREATE TABLE IF NOT EXISTS workspace_artifacts (
    id          TEXT PRIMARY KEY,          -- UUID4
    session_id  TEXT,
    agent_name  TEXT NOT NULL,
    filename    TEXT NOT NULL,             -- z.B. "2026-04-01_cmo_linkedin_post.md"
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- ── Tasks (Background Queue) ─────────────────────────────────────────────────
-- Tasks die vom Worker-Prozess unabhängig vom Browser ausgeführt werden
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,          -- UUID4
    session_id      TEXT,
    agent_name      TEXT DEFAULT '',           -- Leer = Auto/Orchestrator
    task_text       TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',    -- pending | running | done | failed
    result_text     TEXT DEFAULT '',
    agents_used     TEXT DEFAULT '[]',         -- JSON
    tool_calls      TEXT DEFAULT '[]',         -- JSON
    workspace_files TEXT DEFAULT '[]',         -- JSON
    trace           TEXT DEFAULT '[]',         -- JSON
    error           TEXT DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- ── Indizes für Performance ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_briefings_session ON board_briefings(session_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_agent ON workspace_artifacts(agent_name);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id);
