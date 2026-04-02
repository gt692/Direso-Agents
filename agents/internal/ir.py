"""agents/internal/ir.py — IR: Investor Relations, Pitch Decks, VC-Kommunikation."""
from agents.base import BaseAgent


class IRAgent(BaseAgent):
    name = "ir"
    category = "internal"
    tools = ["workspace_write", "web_search", "email_send"]
