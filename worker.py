"""
worker.py

DIRESO Background Task Worker

Läuft als eigenständiger Prozess — unabhängig vom Browser/Streamlit.
Pollt die SQLite-Datenbank nach pending Tasks und führt sie aus.
Tasks werden auch fertig gestellt wenn der Browser geschlossen wird.

Start: python worker.py
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WORKER] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 2  # Sekunden zwischen DB-Polls


def run_worker() -> None:
    # Imports hier damit der Worker auch standalone startbar ist
    from memory.store import store
    from orchestrator.orchestrator import orchestrator

    logger.info("DIRESO Worker gestartet — warte auf Tasks...")

    # PID-Datei schreiben damit UI Worker-Status prüfen kann
    _pid_file = Path(__file__).parent / "worker.pid"
    _pid_file.write_text(str(os.getpid()))
    logger.info("PID %d in %s geschrieben", os.getpid(), _pid_file)

    running = True

    def _shutdown(sig, frame):
        nonlocal running
        logger.info("Worker wird beendet (Signal %s)...", sig)
        running = False
        try:
            _pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while running:
        try:
            # Feststeckende Tasks (> 10 min running) zurückclamen
            store.reclaim_stuck_tasks(timeout_minutes=10)

            task = store.get_next_pending_task()
            if not task:
                time.sleep(POLL_INTERVAL)
                continue

            logger.info(
                "Task übernommen: %s | Agent: %s | '%s'",
                task["id"][:8],
                task["agent_name"] or "auto",
                task["task_text"][:60],
            )

            try:
                result = orchestrator.run(
                    task=task["task_text"],
                    session_id=task["session_id"],
                    agent_override=task["agent_name"] or None,
                )
                store.complete_task(
                    task_id=task["id"],
                    result_text=result.final_text,
                    agents_used=result.agents_used,
                    tool_calls=result.tool_calls,
                    workspace_files=result.workspace_files,
                    trace=[
                        {
                            "step": t.step,
                            "actor": t.actor,
                            "action": t.action,
                            "output": t.output,
                        }
                        for t in result.trace
                    ],
                )
                logger.info(
                    "Task abgeschlossen: %s | Agenten: %s",
                    task["id"][:8],
                    result.agents_used,
                )
            except Exception as exc:
                logger.error("Task fehlgeschlagen: %s — %s", task["id"][:8], exc, exc_info=True)
                store.fail_task(task["id"], error=str(exc))

        except Exception as exc:
            logger.error("Worker-Fehler: %s", exc, exc_info=True)
            time.sleep(POLL_INTERVAL)

    logger.info("Worker beendet.")


if __name__ == "__main__":
    run_worker()
