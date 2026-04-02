"""agents/internal/legal.py — Legal: DSGVO, AVV, Datenschutz, Compliance."""
from agents.base import BaseAgent


class LegalAgent(BaseAgent):
    name = "legal"
    category = "internal"
    tools = ["workspace_write", "web_search"]
