"""agents/internal/hr.py — HR: Personalplanung, Stellenanzeigen, Onboarding."""
from agents.base import BaseAgent


class HRAgent(BaseAgent):
    name = "hr"
    category = "internal"
    tools = ["workspace_write", "web_search", "email_send"]
