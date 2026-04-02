"""
connectors/direso_platform.py

DIRESO Plattform Connector — Anbindung an die C#/ASP.NET Hauptplattform auf Azure.

Status: Stub (API-Integration Phase 3)

Wenn Plattform-API fertig:
  1. DIRESO_PLATFORM_URL und DIRESO_PLATFORM_KEY in .env setzen
  2. Methoden mit echten API-Calls befüllen
  3. is_available() gibt True zurück

Geplante Endpunkte:
  GET /api/v1/portfolios/{id}      → Portfolio-Daten für externe Agenten
  GET /api/v1/properties/{id}      → Einzelne Objekte inkl. Dokumente
  GET /api/v1/esg/{portfolio_id}   → ESG-Kennzahlen
  GET /api/v1/financials/{id}      → Finanzdaten Rendite/Kosten
  GET /api/v1/documents/{id}       → Dokumente eines Objekts
"""
from __future__ import annotations

import logging

from connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class DiresoPlattformConnector(BaseConnector):
    """Connector für die DIRESO Hauptplattform (C# / Azure)."""

    name = "direso_platform"

    def get_context(self, query: str) -> str:
        """
        Holt Portfolio- und Objektdaten aus der DIRESO Plattform.
        TODO: Implementieren wenn Plattform-API fertig ist.
        """
        logger.debug("DiresoPlattformConnector.get_context() aufgerufen (Stub): %s", query)
        return (
            "[DIRESO Plattform-Daten noch nicht verfügbar — API-Integration Phase 3]\n"
            "Verfügbar wenn Plattform-API fertig: Portfolio, Objekte, ESG-Daten, Finanzen, Dokumente."
        )

    def is_available(self) -> bool:
        # TODO: Ping /api/v1/health auf der Plattform
        return False

    # ── Zukünftige Methoden ───────────────────────────────────────────────────

    def get_portfolio(self, portfolio_id: str) -> dict:
        """TODO: Vollständige Portfolio-Daten."""
        return {}

    def get_property(self, property_id: str) -> dict:
        """TODO: Einzelnes Objekt mit allen Metadaten."""
        return {}

    def get_esg_data(self, portfolio_id: str) -> dict:
        """TODO: ESG-Kennzahlen — CO₂, CRREM-Pfad, EPC-Ratings."""
        return {}

    def get_financials(self, portfolio_id: str) -> dict:
        """TODO: Mieteinnahmen, Leerstand, Rendite."""
        return {}


# Singleton
direso_platform = DiresoPlattformConnector()
