"""agents/internal/cmo.py — CMO: Marketing, Content, Kampagnen, Social Media."""
from agents.base import BaseAgent


class CMOAgent(BaseAgent):
    name = "cmo"
    category = "internal"
    tools = ["workspace_write", "web_search", "email_send", "social_post"]
