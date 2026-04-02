"""agents/external/report_generator.py — Kunden-Agent: Berichte, ESG-Reports, Analysen."""
from agents.base import BaseAgent


class ReportGeneratorAgent(BaseAgent):
    name = "report_generator"
    category = "external"
    tools = ["workspace_write", "web_search"]
