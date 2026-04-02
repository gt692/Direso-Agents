"""
agents/internal/ceo.py

CEO-Agent — Co-CEO und strategischer Partner von Frederic Zoll.

Zwei Modi:
  1. run()                   — Strategiegespräch (konversationell, mit Memory)
  2. create_board_briefing() — Strukturiertes Briefing für andere Agenten

Das Board-Briefing wird in memory/board_briefings gespeichert und dient
als Kontext-Inject für nachfolgende Agenten-Aufrufe.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from agents.base import AgentResult, BaseAgent

logger = logging.getLogger(__name__)


@dataclass
class BoardBriefing:
    """Strukturiertes Board-Briefing nach einem Strategiegespräch."""
    decision: str                            # Die getroffene Entscheidung
    rationale: str                           # Begründung
    actions: dict[str, str] = field(default_factory=dict)  # Agent → Aufgabe
    priority: str = "normal"                 # "low" | "normal" | "high" | "urgent"

    def to_context_string(self) -> str:
        """Formatiert das Briefing als Kontext-Text für andere Agenten."""
        lines = [
            "## Board-Briefing vom CEO",
            f"**Entscheidung:** {self.decision}",
            f"**Begründung:** {self.rationale}",
            f"**Priorität:** {self.priority}",
        ]
        if self.actions:
            lines.append("\n**Aufgaben:**")
            for agent, task in self.actions.items():
                lines.append(f"- {agent.upper()}: {task}")
        return "\n".join(lines)


class CEOAgent(BaseAgent):
    """
    Co-CEO Agent — strategischer Gesprächspartner und Board-Koordinator.

    Besonderheiten gegenüber anderen Agenten:
    - Unterstützt konversationellen Modus mit History (für lange Strategiegespräche)
    - Kann Board-Briefings erstellen die andere Agenten als Kontext erhalten
    - Hat keinen email_send oder social_post — kommuniziert über Board-Briefings
    """

    name = "ceo"
    category = "internal"
    tools = ["workspace_write", "workspace_list", "workspace_delete", "web_search"]

    def create_board_briefing(
        self,
        conversation_summary: str,
        target_agents: Optional[list[str]] = None,
    ) -> BoardBriefing:
        """
        Generiert ein strukturiertes Board-Briefing nach einem Strategiegespräch.

        Args:
            conversation_summary: Zusammenfassung des Gesprächs / der Entscheidung.
            target_agents: Welche Agenten sollen Aufgaben erhalten? (None = alle)

        Returns:
            BoardBriefing mit Entscheidung, Begründung und Agenten-Aufgaben.
        """
        all_agents = ["cfo", "coo", "cmo", "cso", "cdo", "cto", "legal", "hr", "ir", "cs"]
        relevant_agents = target_agents or all_agents

        briefing_task = (
            f"Basierend auf folgendem Strategiegespräch / dieser Entscheidung:\n\n"
            f"{conversation_summary}\n\n"
            f"Erstelle ein strukturiertes Board-Briefing im folgenden JSON-Format "
            f"(nur JSON, kein weiterer Text):\n\n"
            f'{{\n'
            f'  "decision": "Die Kern-Entscheidung in einem Satz",\n'
            f'  "rationale": "Begründung in 2-3 Sätzen",\n'
            f'  "priority": "normal",\n'
            f'  "actions": {{\n'
            f'    "cfo": "Konkrete Aufgabe für CFO (oder null wenn nicht relevant)",\n'
            f'    "coo": "Konkrete Aufgabe für COO (oder null wenn nicht relevant)",\n'
            f'    "cmo": "Konkrete Aufgabe für CMO (oder null wenn nicht relevant)",\n'
            f'    "cso": "Konkrete Aufgabe für CSO (oder null wenn nicht relevant)",\n'
            f'    "cdo": "Konkrete Aufgabe für CDO (oder null wenn nicht relevant)",\n'
            f'    "cto": "Konkrete Aufgabe für CTO (oder null wenn nicht relevant)",\n'
            f'    "legal": "Konkrete Aufgabe für Legal (oder null wenn nicht relevant)",\n'
            f'    "hr": "Konkrete Aufgabe für HR (oder null wenn nicht relevant)",\n'
            f'    "ir": "Konkrete Aufgabe für IR (oder null wenn nicht relevant)",\n'
            f'    "cs": "Konkrete Aufgabe für Customer Success (oder null wenn nicht relevant)"\n'
            f'  }}\n'
            f'}}'
        )

        result = self.run(task=briefing_task)

        # JSON aus der Antwort extrahieren
        try:
            text = result.text.strip()
            # Falls Claude Markdown-Codeblock verwendet
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)

            # Nur Agenten mit echten Aufgaben (nicht null/leer)
            actions = {
                k: v for k, v in data.get("actions", {}).items()
                if v and v.lower() != "null" and k in relevant_agents
            }

            briefing = BoardBriefing(
                decision=data.get("decision", "Keine Entscheidung extrahiert"),
                rationale=data.get("rationale", ""),
                actions=actions,
                priority=data.get("priority", "normal"),
            )
            logger.info(
                "Board-Briefing erstellt: '%s' — Aufgaben für: %s",
                briefing.decision[:50],
                list(briefing.actions.keys()),
            )
            return briefing

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Board-Briefing JSON-Parsing fehlgeschlagen: %s", e)
            # Fallback: einfaches Briefing mit dem Roh-Text
            return BoardBriefing(
                decision=conversation_summary[:100],
                rationale=result.text[:300],
                actions={},
                priority="normal",
            )
