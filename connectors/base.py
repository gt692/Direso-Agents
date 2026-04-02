"""
connectors/base.py

BaseConnector — abstrakte Basis für alle Datenquellen-Anbindungen.

Jeder Connector stellt get_context() bereit — damit können Agenten
strukturierte Echtdaten als Kontext erhalten.
"""
from __future__ import annotations


class BaseConnector:
    """Abstrakte Basis für Donna, DIRESO Plattform und zukünftige Quellen."""

    name: str = "base"

    def get_context(self, query: str) -> str:
        """
        Holt relevanten Kontext für eine Abfrage.

        Args:
            query: Was der Agent wissen möchte (z.B. "aktuelle Projekte", "offene Leads")

        Returns:
            Formatierter Kontext-String der in den Agenten-Call injiziert wird.
        """
        raise NotImplementedError(f"Connector '{self.name}' hat get_context() nicht implementiert.")

    def is_available(self) -> bool:
        """Prüft ob die Datenquelle erreichbar ist."""
        return False
