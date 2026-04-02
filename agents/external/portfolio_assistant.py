"""agents/external/portfolio_assistant.py — Kunden-Agent: Fragen zu Immobilien & Portfolio."""
from agents.base import BaseAgent


class PortfolioAssistantAgent(BaseAgent):
    name = "portfolio_assistant"
    category = "external"
    tools = ["workspace_write", "web_search"]
