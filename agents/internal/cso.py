"""agents/internal/cso.py — CSO: Sales, Lead-Qualifikation, CRM, Follow-ups."""
from agents.base import BaseAgent


class CSOAgent(BaseAgent):
    name = "cso"
    category = "internal"
    tools = ["workspace_write", "web_search", "email_send"]
