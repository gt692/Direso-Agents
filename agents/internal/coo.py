"""agents/internal/coo.py — COO: Operative Prozesse, Ressourcen, Effizienz."""
from agents.base import BaseAgent


class COOAgent(BaseAgent):
    name = "coo"
    category = "internal"
    tools = ["workspace_write", "web_search"]
