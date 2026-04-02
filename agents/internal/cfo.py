"""agents/internal/cfo.py — CFO: Finanzen, Controlling, Fördergelder (FZulG)."""
from agents.base import BaseAgent


class CFOAgent(BaseAgent):
    name = "cfo"
    category = "internal"
    tools = ["workspace_write", "web_search"]
