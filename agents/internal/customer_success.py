"""agents/internal/customer_success.py — Customer Success: Onboarding, Churn, NPS."""
from agents.base import BaseAgent


class CustomerSuccessAgent(BaseAgent):
    name = "customer_success"
    category = "internal"
    tools = ["workspace_write", "web_search", "email_send"]
