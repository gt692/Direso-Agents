"""agents/internal/cdo.py — CDO: Website, UX, SEO, liest Astro-Code direkt."""
from agents.base import BaseAgent


class CDOAgent(BaseAgent):
    name = "cdo"
    category = "internal"
    tools = ["workspace_write", "web_search", "file_read", "browser_capture"]
