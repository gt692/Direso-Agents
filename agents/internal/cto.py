"""agents/internal/cto.py — CTO: Architektur, Code-Reviews, liest C#/Python-Code."""
from agents.base import BaseAgent


class CTOAgent(BaseAgent):
    name = "cto"
    category = "internal"
    tools = ["workspace_write", "web_search", "file_read"]
