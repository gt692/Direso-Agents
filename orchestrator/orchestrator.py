"""
orchestrator/orchestrator.py

Orchestrator — koordiniert alle Agenten, führt Workflows aus,
schreibt Traces und verwaltet Board-Briefings.

Haupt-Interface: orchestrator.run(task, session_id) → OrchestratorResult
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from agents.base import AgentResult
from agents.internal.ceo import CEOAgent
from agents.internal.cfo import CFOAgent
from agents.internal.coo import COOAgent
from agents.internal.cmo import CMOAgent
from agents.internal.cso import CSOAgent
from agents.internal.cdo import CDOAgent
from agents.internal.cto import CTOAgent
from agents.internal.legal import LegalAgent
from agents.internal.hr import HRAgent
from agents.internal.ir import IRAgent
from agents.internal.customer_success import CustomerSuccessAgent
from agents.external.portfolio_assistant import PortfolioAssistantAgent
from agents.external.report_generator import ReportGeneratorAgent
from memory.store import store
from orchestrator.router import RouteResult, TaskRouter

logger = logging.getLogger(__name__)


@dataclass
class TraceStep:
    """Ein Schritt im Denkfluss einer Orchestrator-Ausführung."""
    step: int
    actor: str          # "router" | Agent-Name
    action: str         # Was wurde getan?
    output: str         # Kurzes Ergebnis (für Visualisierung)


@dataclass
class OrchestratorResult:
    """Vollständiges Ergebnis eines Orchestrator-Aufrufs."""
    final_text: str
    agents_used: list[str]
    workflow: str
    trace: list[TraceStep] = field(default_factory=list)
    workspace_files: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    session_id: str = ""
    route: Optional[RouteResult] = None


class Orchestrator:
    """
    Zentraler Koordinator des DIRESO Agenten-Systems.

    Verantwortlichkeiten:
    - Agenten-Registry verwalten
    - Aufgaben an TaskRouter weitergeben
    - Workflows ausführen (single / sequential)
    - Trace schreiben für Denkfluss-Visualisierung
    - Board-Briefings in Memory persistieren
    - Workspace-Artifacts tracken
    """

    def __init__(self) -> None:
        self.router = TaskRouter()

        # ── Agenten-Registry ───────────────────────────────────────────────────
        # Lazy initialization: Agenten werden beim ersten Aufruf instanziiert
        self._agents: dict[str, object] = {}
        self._agent_classes = {
            "ceo":              CEOAgent,
            "cfo":              CFOAgent,
            "coo":              COOAgent,
            "cmo":              CMOAgent,
            "cso":              CSOAgent,
            "cdo":              CDOAgent,
            "cto":              CTOAgent,
            "legal":            LegalAgent,
            "hr":               HRAgent,
            "ir":               IRAgent,
            "customer_success": CustomerSuccessAgent,
            "portfolio_assistant": PortfolioAssistantAgent,
            "report_generator":    ReportGeneratorAgent,
        }

    def _get_agent(self, name: str):
        """Gibt den Agenten zurück, instanziiert ihn bei Bedarf."""
        if name not in self._agents:
            if name not in self._agent_classes:
                raise ValueError(f"Unbekannter Agent: '{name}'")
            self._agents[name] = self._agent_classes[name]()
            logger.debug("Agent '%s' instanziiert", name)
        return self._agents[name]

    @property
    def available_agents(self) -> list[str]:
        """Liste aller registrierten Agenten."""
        return list(self._agent_classes.keys())

    # ── Haupt-Interface ────────────────────────────────────────────────────────

    def run(
        self,
        task: str,
        session_id: Optional[str] = None,
        agent_override: Optional[str] = None,
    ) -> OrchestratorResult:
        """
        Führt eine Aufgabe aus — vom Routing bis zum finalen Ergebnis.

        Args:
            task:           Die Aufgabe des Nutzers.
            session_id:     Bestehende Session-ID (für Konversations-Kontext).
            agent_override: Agent direkt angeben statt routen lassen.

        Returns:
            OrchestratorResult mit Text, Trace, Workspace-Dateien.
        """
        # Session anlegen falls keine vorhanden
        if not session_id:
            session_id = store.create_session(label=task[:50])

        # User-Message in Memory speichern
        store.save_message(session_id, role="user", content=task)

        trace: list[TraceStep] = []
        step = 0

        # ── Routing ────────────────────────────────────────────────────────────
        if agent_override:
            # Direkt-Aufruf: Router überspringen
            route = RouteResult(
                category="internal",
                agents=[agent_override],
                workflow="single",
                reasoning=f"Direktaufruf: {agent_override}",
            )
        else:
            route = self.router.route(task)

        step += 1
        trace.append(TraceStep(
            step=step,
            actor="router",
            action="Routing",
            output=f"{route.category} → {route.agents} ({route.workflow})",
        ))

        # ── Workflow ausführen ─────────────────────────────────────────────────
        if route.workflow == "single" or len(route.agents) == 1:
            result = self._run_single(
                task=task,
                agent_name=route.agents[0],
                session_id=session_id,
                trace=trace,
                step_offset=step,
            )
        else:
            result = self._run_sequential(
                task=task,
                agents=route.agents,
                session_id=session_id,
                trace=trace,
                step_offset=step,
            )

        result.session_id = session_id
        result.route = route

        # Antwort in Memory speichern
        store.save_message(
            session_id,
            role="assistant",
            content=result.final_text,
            agent_name=", ".join(result.agents_used),
            tool_calls=result.tool_calls,
        )

        # Workspace-Artifacts tracken
        for filename in result.workspace_files:
            store.save_artifact(
                agent_name=result.agents_used[-1] if result.agents_used else "unknown",
                filename=filename,
                session_id=session_id,
            )

        return result

    # ── Workflow-Implementierungen ─────────────────────────────────────────────

    def _run_single(
        self,
        task: str,
        agent_name: str,
        session_id: str,
        trace: list[TraceStep],
        step_offset: int,
    ) -> OrchestratorResult:
        """Führt einen einzelnen Agenten aus."""
        agent = self._get_agent(agent_name)

        # Gesprächs-History laden (für CEO-Konversationsmodus)
        history = store.get_history_for_agent(session_id) if agent_name == "ceo" else None

        # Letztes Board-Briefing als Kontext falls vorhanden
        context = self._get_briefing_context(agent_name)

        agent_result: AgentResult = agent.run(task=task, context=context, history=history)

        trace.append(TraceStep(
            step=step_offset + 1,
            actor=agent_name,
            action="Aufgabe ausführen",
            output=agent_result.text[:150] + ("..." if len(agent_result.text) > 150 else ""),
        ))

        # Tool-Call-Steps im Trace ergänzen
        for i, tc in enumerate(agent_result.tool_calls):
            trace.append(TraceStep(
                step=step_offset + 1 + i + 1,
                actor=agent_name,
                action=f"Tool: {tc['tool']}",
                output=tc["output"][:100],
            ))

        return OrchestratorResult(
            final_text=agent_result.text,
            agents_used=[agent_name],
            workflow="single",
            trace=trace,
            workspace_files=agent_result.workspace_files,
            tool_calls=agent_result.tool_calls,
        )

    def _run_sequential(
        self,
        task: str,
        agents: list[str],
        session_id: str,
        trace: list[TraceStep],
        step_offset: int,
    ) -> OrchestratorResult:
        """
        Führt mehrere Agenten sequenziell aus.
        Der Output von Agent N wird als Kontext für Agent N+1 verwendet.
        """
        all_tool_calls: list[dict] = []
        all_workspace_files: list[str] = []
        accumulated_context = ""
        current_step = step_offset
        last_text = ""

        for agent_name in agents:
            agent = self._get_agent(agent_name)
            briefing_context = self._get_briefing_context(agent_name)

            # Kontext = vorheriger Agent-Output + ggf. Board-Briefing
            full_context = ""
            if accumulated_context:
                full_context += f"Output vorheriger Schritt:\n{accumulated_context}"
            if briefing_context:
                full_context += f"\n\n{briefing_context}"

            current_step += 1
            agent_result: AgentResult = agent.run(
                task=task,
                context=full_context.strip(),
            )

            trace.append(TraceStep(
                step=current_step,
                actor=agent_name,
                action="Aufgabe ausführen",
                output=agent_result.text[:150] + ("..." if len(agent_result.text) > 150 else ""),
            ))

            for i, tc in enumerate(agent_result.tool_calls):
                trace.append(TraceStep(
                    step=current_step + i + 1,
                    actor=agent_name,
                    action=f"Tool: {tc['tool']}",
                    output=tc["output"][:100],
                ))
                current_step += 1

            # Output für nächsten Agenten merken
            accumulated_context = agent_result.text
            last_text = agent_result.text
            all_tool_calls.extend(agent_result.tool_calls)
            all_workspace_files.extend(agent_result.workspace_files)

        return OrchestratorResult(
            final_text=last_text,
            agents_used=agents,
            workflow="sequential",
            trace=trace,
            workspace_files=all_workspace_files,
            tool_calls=all_tool_calls,
        )

    # ── CEO Board-Briefing ─────────────────────────────────────────────────────

    def create_board_briefing(
        self,
        conversation_summary: str,
        session_id: Optional[str] = None,
    ) -> dict:
        """
        Erstellt ein CEO Board-Briefing und persistiert es in Memory.

        Returns:
            Dict mit decision, rationale, actions (für alle betroffenen Agenten)
        """
        ceo: CEOAgent = self._get_agent("ceo")
        briefing = ceo.create_board_briefing(conversation_summary)

        briefing_id = store.save_briefing(
            decision=briefing.decision,
            rationale=briefing.rationale,
            actions=briefing.actions,
            priority=briefing.priority,
            session_id=session_id,
        )

        logger.info(
            "Board-Briefing gespeichert (ID: %s): '%s'",
            briefing_id,
            briefing.decision[:60],
        )

        return {
            "id": briefing_id,
            "decision": briefing.decision,
            "rationale": briefing.rationale,
            "actions": briefing.actions,
            "priority": briefing.priority,
            "context_string": briefing.to_context_string(),
        }

    # ── Hilfsmethoden ──────────────────────────────────────────────────────────

    def _get_briefing_context(self, agent_name: str) -> str:
        """
        Prüft ob das neueste Board-Briefing eine Aufgabe für diesen Agenten enthält.
        Falls ja, wird das Briefing als Kontext zurückgegeben.
        """
        briefing = store.get_latest_briefing()
        if not briefing:
            return ""
        actions = briefing.get("actions", {})
        if agent_name in actions and actions[agent_name]:
            return (
                f"## Aktuelles Board-Briefing\n"
                f"**Entscheidung:** {briefing['decision']}\n"
                f"**Deine Aufgabe laut Briefing:** {actions[agent_name]}"
            )
        return ""


# Singleton
orchestrator = Orchestrator()
