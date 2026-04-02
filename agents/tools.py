"""
agents/tools.py

Zentrale Tool-Registry für alle Agenten-Tools.

Jedes Tool hat:
- schema:   Anthropic-kompatible Tool-Definition (wird an die API gesendet)
- handler:  Python-Funktion die das Tool ausführt
- live:     True = sofort aktiv, False = noch nicht konfiguriert (zeigt Hinweis)

Agenten deklarieren ihre Tools als Klassenvariable `tools: list[str]`.
BaseAgent lädt beim Init nur die Tools die der Agent benötigt.
"""
from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from pathlib import Path

import msal
import requests

from config import settings

logger = logging.getLogger(__name__)


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def _workspace_path(filename: str) -> Path:
    """Gibt den vollständigen Pfad für eine workspace-Datei zurück."""
    return settings.workspace_dir / filename


# ── Tool-Handler ───────────────────────────────────────────────────────────────

def handle_workspace_write(filename: str, content: str) -> str:
    """Schreibt eine Datei in den workspace/-Ordner."""
    # Dateiname bereinigen und Datum voranstellen wenn noch keins da ist
    if not filename.startswith(datetime.now().strftime("%Y")):
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_prefix}_{filename}"

    path = _workspace_path(filename)
    path.write_text(content, encoding="utf-8")
    logger.info("workspace_write: %s (%d Zeichen)", filename, len(content))
    return f"✓ Datei gespeichert: workspace/{filename}"


def handle_file_read(path: str) -> str:
    """Liest eine beliebige Datei (für CDO/CTO: Code-Dateien lesen)."""
    file_path = Path(path)
    if not file_path.exists():
        return f"Fehler: Datei nicht gefunden: {path}"
    try:
        content = file_path.read_text(encoding="utf-8")
        logger.info("file_read: %s (%d Zeichen)", path, len(content))
        # Bei sehr großen Dateien: kürzen um Token zu sparen
        if len(content) > 15000:
            content = content[:15000] + f"\n\n[... Datei gekürzt, {len(content)} Zeichen gesamt]"
        return content
    except Exception as e:
        return f"Fehler beim Lesen: {e}"


def handle_web_search(query: str, max_results: int = 5) -> str:
    """Führt eine Web-Suche via Tavily API durch."""
    if not settings.is_search_configured():
        return "[web_search: TAVILY_API_KEY fehlt in .env — Suche nicht verfügbar]"

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(query=query, max_results=max_results)
        results = response.get("results", [])
        if not results:
            return "Keine Ergebnisse gefunden."

        output = f"Suchergebnisse für: '{query}'\n\n"
        for i, r in enumerate(results, 1):
            output += f"{i}. **{r.get('title', 'Kein Titel')}**\n"
            output += f"   {r.get('url', '')}\n"
            output += f"   {r.get('content', '')[:300]}\n\n"
        return output
    except Exception as e:
        logger.error("web_search Fehler: %s", e)
        return f"[web_search Fehler: {e}]"


def _get_msgraph_token() -> str:
    """Holt MS Graph Access Token via MSAL (gleiche Logik wie Donna)."""
    app = msal.ConfidentialClientApplication(
        client_id=settings.ms_client_id,
        client_credential=settings.ms_client_secret,
        authority=f"https://login.microsoftonline.com/{settings.ms_tenant_id}",
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise RuntimeError(
            f"MS Graph Token-Fehler: {result.get('error')}: {result.get('error_description')}"
        )
    return result["access_token"]


def handle_email_send(to: str, subject: str, body: str, html: bool = True) -> str:
    """Sendet eine E-Mail via Microsoft Graph API (gleiche Implementierung wie Donna)."""
    if not settings.is_email_configured():
        return "[email_send: MS Graph Credentials fehlen in .env (MS_CLIENT_ID, MS_CLIENT_SECRET, MS_TENANT_ID)]"

    try:
        token = _get_msgraph_token()
        sender = settings.ms_sender_email

        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML" if html else "Text",
                    "content": body,
                },
                "toRecipients": [{"emailAddress": {"address": to}}],
                "from": {"emailAddress": {"address": sender, "name": "DIRESO GmbH"}},
            },
            "saveToSentItems": "true",
        }

        response = requests.post(
            f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload),
        )

        if response.status_code == 202:
            logger.info("email_send: E-Mail an %s gesendet", to)
            return f"✓ E-Mail gesendet an {to} (Betreff: '{subject}')"
        else:
            return f"[email_send Fehler {response.status_code}: {response.text}]"
    except Exception as e:
        logger.error("email_send Fehler: %s", e)
        return f"[email_send Fehler: {e}]"


def handle_social_post(platform: str, content: str, image_url: str = "") -> str:
    """Postet auf LinkedIn oder Instagram (nach OAuth-Setup aktiv)."""
    if not settings.is_social_configured():
        return (
            f"[social_post ({platform}): OAuth noch nicht konfiguriert. "
            f"Bitte LINKEDIN_ACCESS_TOKEN oder META_ACCESS_TOKEN in .env setzen.]"
        )

    platform = platform.lower()

    if platform == "linkedin" and settings.linkedin_access_token:
        try:
            post_body: dict = {
                "author": f"urn:li:person:{settings.linkedin_access_token[:8]}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": content},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            }
            response = requests.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers={
                    "Authorization": f"Bearer {settings.linkedin_access_token}",
                    "Content-Type": "application/json",
                },
                json=post_body,
            )
            if response.status_code in (200, 201):
                return f"✓ LinkedIn-Post veröffentlicht"
            return f"[LinkedIn Fehler {response.status_code}: {response.text}]"
        except Exception as e:
            return f"[LinkedIn Fehler: {e}]"

    if platform == "instagram" and settings.meta_access_token:
        try:
            # Schritt 1: Container erstellen
            container_response = requests.post(
                f"https://graph.facebook.com/v19.0/{settings.meta_page_id}/media",
                params={
                    "caption": content,
                    "access_token": settings.meta_access_token,
                    **({"image_url": image_url} if image_url else {}),
                },
            )
            container_id = container_response.json().get("id")
            if not container_id:
                return f"[Instagram Container-Fehler: {container_response.text}]"

            # Schritt 2: Veröffentlichen
            publish_response = requests.post(
                f"https://graph.facebook.com/v19.0/{settings.meta_page_id}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": settings.meta_access_token,
                },
            )
            if publish_response.status_code == 200:
                return f"✓ Instagram-Post veröffentlicht"
            return f"[Instagram Fehler: {publish_response.text}]"
        except Exception as e:
            return f"[Instagram Fehler: {e}]"

    return f"[social_post: Plattform '{platform}' unbekannt oder nicht konfiguriert]"


def handle_workspace_list() -> str:
    """Listet alle Dateien im workspace/-Ordner mit Datum und Größe auf."""
    files = sorted(settings.workspace_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return "workspace/ ist leer — keine Dateien vorhanden."
    lines = ["Dateien im workspace/ (neueste zuerst):\n"]
    for f in files:
        if f.is_file():
            stat = f.stat()
            age_days = (datetime.now().timestamp() - stat.st_mtime) / 86400
            size_kb = stat.st_size / 1024
            lines.append(f"- {f.name}  ({size_kb:.1f} KB, {age_days:.0f} Tage alt)")
    return "\n".join(lines)


def handle_workspace_delete(filename: str) -> str:
    """Löscht eine Datei aus dem workspace/-Ordner."""
    path = settings.workspace_dir / filename
    # Glob-Fallback: Datei mit Datumspräfix suchen
    if not path.exists():
        matches = sorted(settings.workspace_dir.glob(f"*{filename}"), key=lambda p: p.stat().st_mtime, reverse=True)
        path = matches[0] if matches else path
    if not path.exists():
        return f"Datei nicht gefunden: {filename}"
    path.unlink()
    logger.info("workspace_delete: %s gelöscht", path.name)
    return f"✓ Gelöscht: workspace/{path.name}"


def handle_browser_capture(url: str) -> str:
    """Macht einen Screenshot einer Website (benötigt: playwright install chromium)."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, wait_until="networkidle", timeout=15000)

            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            path = _workspace_path(filename)
            page.screenshot(path=str(path), full_page=True)
            browser.close()

        logger.info("browser_capture: Screenshot gespeichert: %s", filename)
        return f"✓ Screenshot gespeichert: workspace/{filename}"
    except ImportError:
        return "[browser_capture: Playwright nicht installiert. Bitte: pip install playwright && playwright install chromium]"
    except Exception as e:
        return f"[browser_capture Fehler: {e}]"


# ── Tool-Registry ──────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict] = {
    "workspace_write": {
        "live": True,
        "handler": handle_workspace_write,
        "schema": {
            "name": "workspace_write",
            "description": "Schreibt eine Datei in den workspace/-Ordner. Ideal für Dokumente, Reports, Drafts, Templates und Code-Vorschläge.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Dateiname, z.B. 'cmo_linkedin_post.md' oder 'legal_avv_template.md'",
                    },
                    "content": {
                        "type": "string",
                        "description": "Der vollständige Inhalt der Datei (Markdown empfohlen).",
                    },
                },
                "required": ["filename", "content"],
            },
        },
    },
    "file_read": {
        "live": True,
        "handler": handle_file_read,
        "schema": {
            "name": "file_read",
            "description": "Liest eine beliebige Datei vom Dateisystem. Für CDO: Astro/Tailwind-Dateien lesen. Für CTO: C#/Python-Code lesen.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absoluter oder relativer Dateipfad, z.B. '/Users/fredericzoll/Desktop/Entwicklung/Astro direso/src/components/Navigation.astro'",
                    }
                },
                "required": ["path"],
            },
        },
    },
    "web_search": {
        "live": True,  # Wird aktiv sobald TAVILY_API_KEY gesetzt ist
        "handler": handle_web_search,
        "schema": {
            "name": "web_search",
            "description": "Führt eine aktuelle Web-Suche durch. Für Marktrecherchen, Gesetzestexte, Wettbewerber, Förderquellen etc.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Suchanfrage auf Deutsch oder Englisch",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Anzahl der Suchergebnisse (Standard: 5, max: 10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    "email_send": {
        "live": True,  # Wird aktiv sobald MS_CLIENT_ID etc. gesetzt sind
        "handler": handle_email_send,
        "schema": {
            "name": "email_send",
            "description": "Sendet eine E-Mail via Microsoft Graph API. Für Follow-ups, Kampagnen, Stellenanzeigen, Investor-Outreach.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "E-Mail-Adresse des Empfängers",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Betreffzeile der E-Mail",
                    },
                    "body": {
                        "type": "string",
                        "description": "E-Mail-Inhalt (HTML empfohlen für bessere Formatierung)",
                    },
                    "html": {
                        "type": "boolean",
                        "description": "True wenn body HTML enthält (Standard: True)",
                        "default": True,
                    },
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    "social_post": {
        "live": False,  # Wird aktiv nach LinkedIn/Meta OAuth-Setup
        "handler": handle_social_post,
        "schema": {
            "name": "social_post",
            "description": "Veröffentlicht einen Post auf LinkedIn oder Instagram. Für CMO: Kampagnen, Ankündigungen, Content-Marketing.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Ziel-Plattform: 'linkedin' oder 'instagram'",
                        "enum": ["linkedin", "instagram"],
                    },
                    "content": {
                        "type": "string",
                        "description": "Post-Text (LinkedIn: bis 3000 Zeichen, Instagram: bis 2200 Zeichen)",
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Optionale Bild-URL für Instagram-Posts",
                        "default": "",
                    },
                },
                "required": ["platform", "content"],
            },
        },
    },
    "workspace_list": {
        "live": True,
        "handler": handle_workspace_list,
        "schema": {
            "name": "workspace_list",
            "description": "Listet alle Dateien im workspace/-Ordner auf — mit Alter und Größe. Nutze dies um veraltete oder überflüssige Dateien zu identifizieren.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    "workspace_delete": {
        "live": True,
        "handler": handle_workspace_delete,
        "schema": {
            "name": "workspace_delete",
            "description": "Löscht eine veraltete oder überflüssige Datei aus dem workspace/-Ordner. Nutze dies um Datenmüll zu vermeiden.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Dateiname der zu löschenden Datei, z.B. 'ceo_entwurf_v1.md'",
                    }
                },
                "required": ["filename"],
            },
        },
    },
    "browser_capture": {
        "live": False,  # Wird aktiv nach: pip install playwright && playwright install chromium
        "handler": handle_browser_capture,
        "schema": {
            "name": "browser_capture",
            "description": "Macht einen Screenshot einer Website für visuelle Analyse. Für CDO: Website-Qualität und UX prüfen.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL der Website, z.B. 'https://direso.de'",
                    }
                },
                "required": ["url"],
            },
        },
    },
}


def get_tool_schemas(tool_names: list[str]) -> list[dict]:
    """Gibt die Anthropic-Schemas für eine Liste von Tool-Namen zurück."""
    return [TOOL_REGISTRY[name]["schema"] for name in tool_names if name in TOOL_REGISTRY]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Führt ein Tool aus und gibt das Ergebnis als String zurück."""
    if tool_name not in TOOL_REGISTRY:
        return f"[Unbekanntes Tool: {tool_name}]"
    handler = TOOL_REGISTRY[tool_name]["handler"]
    try:
        return handler(**tool_input)
    except TypeError as e:
        return f"[Tool-Fehler '{tool_name}': falsche Parameter — {e}]"
    except Exception as e:
        logger.error("Tool '%s' Fehler: %s", tool_name, e)
        return f"[Tool-Fehler '{tool_name}': {e}]"
