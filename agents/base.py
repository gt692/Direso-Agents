"""
agents/base.py

BaseAgent — gemeinsame Grundklasse für alle DIRESO-Agenten.

Jeder Agent:
  - Deklariert seinen Namen (name) und seine Tools (tools)
  - Lädt seinen System-Prompt aus prompts/<kategorie>/<name>_system.txt
  - Lädt den Shared Company Context aus company_context.json
  - Führt Claude-API-Aufrufe mit nativer Tool-Use-Schleife durch
  - Gibt ein AgentResult zurück (Text + Liste aller Tool-Calls + neue Workspace-Dateien)

Neue Agenten hinzufügen:
  1. Neue Datei in agents/internal/ oder agents/external/
  2. Klasse erbt von BaseAgent, setzt name und tools
  3. Prompt-Datei in prompts/internal/ oder prompts/external/ anlegen
  → Kein Kern-Code anfassen nötig.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import anthropic

from agents.tools import execute_tool, get_tool_schemas
from config import settings

logger = logging.getLogger(__name__)

# Pfad zu den Prompt-Dateien (relativ zu diesem File)
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
COMPANY_CONTEXT_PATH = Path(__file__).parent.parent / "company_context.json"


@dataclass
class AgentResult:
    """Rückgabeobjekt eines Agenten-Aufrufs."""
    text: str                          # Finale Antwort des Agenten
    tool_calls: list[dict] = field(default_factory=list)   # Liste aller ausgeführten Tool-Calls
    workspace_files: list[str] = field(default_factory=list)  # Neu erstellte workspace/-Dateien
    agent_name: str = ""


class BaseAgent:
    """
    Abstrakte Basis für alle DIRESO-Agenten.

    Subklassen setzen:
      name: str        — eindeutiger Name (= Prompt-Dateiname ohne _system.txt)
      category: str    — "internal" oder "external"
      tools: list[str] — Tools aus TOOL_REGISTRY die dieser Agent nutzen darf
    """

    name: str = "base"
    category: str = "internal"
    tools: list[str] = ["workspace_write", "web_search"]

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.system_prompt = self._load_system_prompt()
        self.company_context = self._load_company_context()
        self.tool_schemas = get_tool_schemas(self.tools)

    # ── Lade-Methoden ──────────────────────────────────────────────────────────

    def _load_system_prompt(self) -> str:
        """Lädt den System-Prompt aus prompts/<category>/<name>_system.txt."""
        path = PROMPTS_DIR / self.category / f"{self.name}_system.txt"
        if not path.exists():
            raise FileNotFoundError(
                f"System-Prompt fehlt: {path}\n"
                f"Bitte Datei prompts/{self.category}/{self.name}_system.txt anlegen."
            )
        return path.read_text(encoding="utf-8").strip()

    def _load_company_context(self) -> str:
        """Lädt den Shared Company Context als formatierten String."""
        if not COMPANY_CONTEXT_PATH.exists():
            return ""
        data = json.loads(COMPANY_CONTEXT_PATH.read_text(encoding="utf-8"))
        return json.dumps(data, ensure_ascii=False, indent=2)

    # ── Hauptmethode ───────────────────────────────────────────────────────────

    def run(
        self,
        task: str,
        context: str = "",
        history: Optional[list[dict]] = None,
    ) -> AgentResult:
        """
        Führt den Agenten mit einer Aufgabe aus.

        Args:
            task:    Die Aufgabe / Frage des Nutzers.
            context: Optionaler Kontext aus vorherigen Agenten (z.B. Board-Briefing).
            history: Optionale Gesprächshistorie (für CEO-Konversationsmodus).

        Returns:
            AgentResult mit Text, Tool-Calls und neuen Workspace-Dateien.
        """
        logger.info("Agent '%s' startet: %s", self.name, task[:80])

        # Vollständige User-Message zusammenbauen
        user_content = self._build_user_message(task, context)

        # Nachrichten-Liste aufbauen (mit optionaler History)
        messages: list[dict] = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_content})

        # System-Prompt mit Company Context kombinieren
        full_system = (
            f"{self.system_prompt}\n\n"
            f"## Firmen-Kontext (immer berücksichtigen)\n{self.company_context}"
        )

        result = AgentResult(text="", agent_name=self.name)

        # ── Tool-Use-Schleife ──────────────────────────────────────────────────
        # Anthropic-native: Wiederholen bis keine Tool-Calls mehr kommen
        while True:
            response = self.client.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
                system=full_system,
                messages=messages,
                tools=self.tool_schemas if self.tool_schemas else anthropic.NOT_GIVEN,
            )

            logger.debug(
                "Agent '%s' Response: stop_reason=%s, tokens=%d",
                self.name,
                response.stop_reason,
                response.usage.input_tokens + response.usage.output_tokens,
            )

            # Antwort zur Nachrichten-Liste hinzufügen (für nächste Iteration)
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Fertig — finalen Text extrahieren
                result.text = self._extract_text(response.content)
                break

            if response.stop_reason == "tool_use":
                # Tool-Calls verarbeiten
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name = block.name
                    tool_input = block.input

                    logger.info("Agent '%s' → Tool: %s(%s)", self.name, tool_name, list(tool_input.keys()))
                    tool_output = execute_tool(tool_name, tool_input)

                    # Tool-Call für Rückgabe merken
                    result.tool_calls.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "output": tool_output[:200],  # Gekürzt für Anzeige
                    })

                    # Workspace-Dateien tracken
                    if tool_name == "workspace_write" and tool_output.startswith("✓"):
                        filename = tool_input.get("filename", "")
                        result.workspace_files.append(filename)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_output,
                    })

                # Tool-Ergebnisse zurück an Claude
                messages.append({"role": "user", "content": tool_results})
                continue

            # Unerwarteter stop_reason — abbrechen
            logger.warning("Unerwarteter stop_reason: %s", response.stop_reason)
            result.text = self._extract_text(response.content) or "[Keine Antwort]"
            break

        logger.info(
            "Agent '%s' abgeschlossen. Tool-Calls: %d, Workspace-Dateien: %d",
            self.name,
            len(result.tool_calls),
            len(result.workspace_files),
        )
        return result

    # ── Hilfsmethoden ──────────────────────────────────────────────────────────

    def _build_user_message(self, task: str, context: str) -> str:
        """Baut die vollständige User-Message zusammen."""
        if context:
            return f"## Kontext aus vorherigen Schritten\n{context}\n\n## Aufgabe\n{task}"
        return task

    @staticmethod
    def _extract_text(content: list) -> str:
        """Extrahiert den Text aus einer Anthropic-Response-Content-Liste."""
        parts = []
        for block in content:
            if hasattr(block, "type") and block.type == "text":
                parts.append(block.text)
        return "\n".join(parts).strip()
