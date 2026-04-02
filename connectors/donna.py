"""
connectors/donna.py

Donna-Connector — Anbindung an das interne Django-CRM/ERP "Donna".

Status: Stub (Donna-API noch in Entwicklung)

Wenn Donna-API fertig:
  1. DONNA_API_URL und DONNA_API_KEY in .env setzen
  2. get_context() mit echten API-Calls befüllen
  3. is_available() gibt True zurück wenn API erreichbar

Donna-Endpunkte die später relevant sein werden:
  GET /crm/projects/        → Aktuelle Projekte für CSO/COO
  GET /crm/accounts/        → Kunden/Kontakte für CSO
  GET /crm/invoices/        → Rechnungen für CFO
  GET /worktrack/           → Zeiterfassung für COO/CFO
  GET /crm/kanban/          → Pipeline-Status für CSO
"""
from __future__ import annotations

import logging

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class DonnaConnector(BaseConnector):
    """Connector für Donna — internes CRM, ERP, Zeiterfassung."""

    name = "donna"

    def get_context(self, query: str) -> str:
        """
        Holt Kontext aus Donna.
        TODO: Implementieren wenn Donna-REST-API fertig ist.
        """
        logger.debug("DonnaConnector.get_context() aufgerufen (Stub): %s", query)
        return (
            "[Donna-Daten noch nicht verfügbar — API in Entwicklung]\n"
            "Verfügbar wenn Donna-API fertig: Projekte, Kunden, Rechnungen, Zeiterfassung."
        )

    def is_available(self) -> bool:
        # TODO: Ping Donna API Health-Endpoint
        return False

    # ── Zukünftige Methoden (Platzhalter) ─────────────────────────────────────

    def get_projects(self) -> list[dict]:
        """TODO: GET /crm/projects/ — Aktuelle Projekte."""
        return []

    def get_accounts(self) -> list[dict]:
        """TODO: GET /crm/accounts/ — Kunden und Kontakte."""
        return []

    def get_invoices(self) -> list[dict]:
        """TODO: GET /crm/invoices/ — Offene und bezahlte Rechnungen."""
        return []

    def get_pipeline(self) -> list[dict]:
        """TODO: GET /crm/kanban/ — Sales Pipeline Status."""
        return []


# Singleton
donna = DonnaConnector()
