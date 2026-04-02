"""
orchestrator/router.py

TaskRouter — nutzt Claude um zu entscheiden welche Agenten für eine Aufgabe
zuständig sind. Gibt strukturiertes JSON zurück.

Routing-Logik:
  1. Aufgabe + Orchestrator-Prompt → Claude API
  2. Claude gibt JSON zurück: {category, agents, workflow, reasoning}
  3. Router validiert und gibt RouteResult zurück
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from config import settings

logger = logging.getLogger(__name__)

ORCHESTRATOR_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "orchestrator_system.txt"


@dataclass
class RouteResult:
    """Ergebnis des Routings."""
    category: str               # "internal" | "external"
    agents: list[str]           # Liste der zu verwendenden Agenten
    workflow: str               # "single" | "sequential"
    reasoning: str              # Begründung für das Routing
    raw_response: str = ""      # Rohe Claude-Antwort (für Debug)


class TaskRouter:
    """
    Nutzt Claude um Aufgaben den richtigen Agenten zuzuordnen.
    Kleiner, schneller Aufruf — nur zur Klassifizierung.
    """

    # Bekannte Agent-Namen zur Validierung
    VALID_INTERNAL = {"ceo", "cfo", "coo", "cmo", "cso", "cdo", "cto", "legal", "hr", "ir", "customer_success"}
    VALID_EXTERNAL = {"portfolio_assistant", "report_generator"}
    VALID_ALL = VALID_INTERNAL | VALID_EXTERNAL

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.system_prompt = ORCHESTRATOR_PROMPT_PATH.read_text(encoding="utf-8").strip()

    def route(self, task: str) -> RouteResult:
        """
        Bestimmt welche Agenten für eine Aufgabe zuständig sind.

        Args:
            task: Die Aufgabe des Nutzers

        Returns:
            RouteResult mit Agenten-Liste und Workflow-Typ
        """
        logger.info("Routing Aufgabe: %s", task[:80])

        response = self.client.messages.create(
            model=settings.anthropic_model,
            max_tokens=300,  # Routing braucht wenig Tokens
            system=self.system_prompt,
            messages=[{"role": "user", "content": task}],
        )

        raw = response.content[0].text.strip()
        logger.debug("Router Raw Response: %s", raw)

        return self._parse_route(raw, task)

    def _parse_route(self, raw: str, original_task: str) -> RouteResult:
        """Parst die JSON-Antwort des Routers."""
        try:
            # Markdown-Codeblock entfernen falls vorhanden
            text = raw
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)

            category = data.get("category", "internal")
            agents = data.get("agents", [])
            workflow = data.get("workflow", "single")
            reasoning = data.get("reasoning", "")

            # Validierung: Nur bekannte Agenten durchlassen
            valid_agents = [a for a in agents if a in self.VALID_ALL]
            if not valid_agents:
                logger.warning("Router: Keine gültigen Agenten gefunden, Fallback auf CEO")
                valid_agents = ["ceo"]

            # Workflow anpassen
            if len(valid_agents) == 1:
                workflow = "single"
            elif workflow not in ("single", "sequential"):
                workflow = "sequential"

            result = RouteResult(
                category=category,
                agents=valid_agents,
                workflow=workflow,
                reasoning=reasoning,
                raw_response=raw,
            )

            logger.info(
                "Route: %s → %s (%s) — %s",
                category,
                valid_agents,
                workflow,
                reasoning[:60],
            )
            return result

        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Router JSON-Parsing fehlgeschlagen: %s | Raw: %s", e, raw[:200])
            # Fallback: CEO für interne Aufgaben
            return RouteResult(
                category="internal",
                agents=["ceo"],
                workflow="single",
                reasoning=f"Fallback (Parsing-Fehler): {e}",
                raw_response=raw,
            )
