"""
memory/store.py

MemoryStore — SQLite-basierte Persistenz für Sessions, Messages,
Board-Briefings und Workspace-Artifacts.

Alle anderen Module importieren nur die `store`-Singleton-Instanz.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Pfad zur SQLite-Datenbank und Schema-Datei
DB_PATH = Path(__file__).parent.parent / "direso_agents.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class MemoryStore:
    """Einfache SQLite-Abstraktion für den Agenten-Memory-Layer."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Zugriff per Spaltenname
        return conn

    def _init_db(self) -> None:
        """Erstellt alle Tabellen aus schema.sql falls noch nicht vorhanden."""
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema)
        logger.info("MemoryStore initialisiert: %s", self.db_path)

    # ── Sessions ───────────────────────────────────────────────────────────────

    def create_session(self, label: str = "", agent_name: str = "") -> str:
        """Erstellt eine neue Session und gibt die ID zurück."""
        session_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, label, agent_name) VALUES (?, ?, ?)",
                (session_id, label, agent_name),
            )
        return session_id

    def get_sessions(self, limit: int = 20) -> list[dict]:
        """Gibt die letzten N Sessions zurück."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Messages ───────────────────────────────────────────────────────────────

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent_name: str = "",
        tool_calls: Optional[list] = None,
    ) -> str:
        """Speichert eine Nachricht und gibt die Message-ID zurück."""
        msg_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO messages (id, session_id, role, agent_name, content, tool_calls)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    msg_id,
                    session_id,
                    role,
                    agent_name,
                    content,
                    json.dumps(tool_calls or [], ensure_ascii=False),
                ),
            )
        return msg_id

    def get_history(self, session_id: str) -> list[dict]:
        """Gibt den vollständigen Gesprächsverlauf einer Session zurück."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tool_calls"] = json.loads(d.get("tool_calls", "[]"))
            result.append(d)
        return result

    def get_history_for_agent(self, session_id: str) -> list[dict]:
        """
        Gibt die History im Anthropic-Messages-Format zurück.
        Nützlich um den Konversations-Kontext an den Agenten weiterzugeben.
        """
        history = self.get_history(session_id)
        return [{"role": h["role"], "content": h["content"]} for h in history]

    # ── Board Briefings ────────────────────────────────────────────────────────

    def save_briefing(
        self,
        decision: str,
        rationale: str = "",
        actions: Optional[dict] = None,
        priority: str = "normal",
        session_id: Optional[str] = None,
    ) -> str:
        """Speichert ein Board-Briefing und gibt die ID zurück."""
        briefing_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO board_briefings
                   (id, session_id, decision, rationale, actions_json, priority)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    briefing_id,
                    session_id,
                    decision,
                    rationale,
                    json.dumps(actions or {}, ensure_ascii=False),
                    priority,
                ),
            )
        return briefing_id

    def get_latest_briefing(self) -> Optional[dict]:
        """Gibt das neueste Board-Briefing zurück (für Kontext-Inject)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM board_briefings ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["actions"] = json.loads(d.get("actions_json", "{}"))
        return d

    def get_briefings(self, limit: int = 10) -> list[dict]:
        """Gibt die letzten N Briefings zurück."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM board_briefings ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["actions"] = json.loads(d.get("actions_json", "{}"))
            result.append(d)
        return result

    # ── Workspace Artifacts ────────────────────────────────────────────────────

    def save_artifact(self, agent_name: str, filename: str, session_id: Optional[str] = None) -> str:
        """Trackt eine neu erstellte workspace/-Datei."""
        artifact_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO workspace_artifacts (id, session_id, agent_name, filename) VALUES (?, ?, ?, ?)",
                (artifact_id, session_id, agent_name, filename),
            )
        return artifact_id

    def get_recent_artifacts(self, limit: int = 20) -> list[dict]:
        """Gibt die zuletzt erstellten workspace/-Dateien zurück."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workspace_artifacts ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_artifact(self, filename: str) -> None:
        """Entfernt einen workspace_artifacts-Eintrag anhand des Dateinamens."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM workspace_artifacts WHERE filename = ? OR filename LIKE ?",
                (filename, f"%{filename}"),
            )

    def cleanup_old_artifacts(self, days: int = 30) -> int:
        """Löscht workspace_artifact-Einträge älter als N Tage. Gibt Anzahl zurück."""
        with self._connect() as conn:
            deleted = conn.execute(
                "DELETE FROM workspace_artifacts WHERE created_at < datetime('now', ? || ' days')",
                (f"-{days}",),
            ).rowcount
        return deleted

    def get_artifacts_by_agent(self, agent_name: str) -> list[dict]:
        """Gibt alle workspace/-Dateien eines bestimmten Agenten zurück."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workspace_artifacts WHERE agent_name = ? ORDER BY created_at DESC",
                (agent_name,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Task Queue ─────────────────────────────────────────────────────────────

    def enqueue_task(
        self,
        task_text: str,
        session_id: Optional[str] = None,
        agent_name: str = "",
    ) -> str:
        """Stellt einen neuen Task in die Queue und gibt die Task-ID zurück."""
        task_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO tasks (id, session_id, agent_name, task_text)
                   VALUES (?, ?, ?, ?)""",
                (task_id, session_id, agent_name, task_text),
            )
        logger.info("Task eingestellt: %s", task_id[:8])
        return task_id

    def get_next_pending_task(self) -> Optional[dict]:
        """Holt den nächsten pending Task (FIFO). Atomares Claim via UPDATE."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE status = 'pending' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            # Atomares Status-Update: nur übernehmen wenn noch pending
            updated = conn.execute(
                "UPDATE tasks SET status='running', started_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND status='pending'",
                (row["id"],),
            ).rowcount
        if updated == 0:
            return None  # Race condition — anderer Worker hat den Task
        return dict(row)

    def complete_task(
        self,
        task_id: str,
        result_text: str,
        agents_used: list[str],
        tool_calls: list[dict],
        workspace_files: list[str],
        trace: list[dict],
    ) -> None:
        """Markiert einen Task als abgeschlossen und speichert das Ergebnis."""
        with self._connect() as conn:
            conn.execute(
                """UPDATE tasks SET
                   status='done',
                   result_text=?,
                   agents_used=?,
                   tool_calls=?,
                   workspace_files=?,
                   trace=?,
                   completed_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (
                    result_text,
                    json.dumps(agents_used, ensure_ascii=False),
                    json.dumps(tool_calls, ensure_ascii=False),
                    json.dumps(workspace_files, ensure_ascii=False),
                    json.dumps(trace, ensure_ascii=False),
                    task_id,
                ),
            )

    def fail_task(self, task_id: str, error: str) -> None:
        """Markiert einen Task als fehlgeschlagen."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status='failed', error=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (error, task_id),
            )

    def get_task(self, task_id: str) -> Optional[dict]:
        """Gibt einen Task anhand der ID zurück."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for field in ("agents_used", "tool_calls", "workspace_files", "trace"):
            d[field] = json.loads(d.get(field) or "[]")
        return d

    def reclaim_stuck_tasks(self, timeout_minutes: int = 10) -> int:
        """Markiert Tasks die > timeout_minutes im Status 'running' feststecken als failed."""
        with self._connect() as conn:
            updated = conn.execute(
                """UPDATE tasks SET status='failed', error='Worker-Timeout: Task feststeckend',
                   completed_at=CURRENT_TIMESTAMP
                   WHERE status='running'
                   AND started_at < datetime('now', ? || ' minutes')""",
                (f"-{timeout_minutes}",),
            ).rowcount
        if updated:
            logger.warning("Stuck Tasks zurückgeclaimt: %d", updated)
        return updated

    def get_recent_tasks(self, session_id: str, limit: int = 20) -> list[dict]:
        """Gibt die letzten Tasks einer Session zurück."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for field in ("agents_used", "tool_calls", "workspace_files", "trace"):
                d[field] = json.loads(d.get(field) or "[]")
            result.append(d)
        return result


# Singleton
store = MemoryStore()
