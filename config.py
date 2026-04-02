"""
config.py

Lädt alle Umgebungsvariablen aus .env und stellt ein typisiertes
Settings-Objekt bereit. Alle anderen Module importieren nur `settings`.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Anthropic ──────────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-sonnet-4-6", alias="ANTHROPIC_MODEL")
    anthropic_max_tokens: int = Field(4096, alias="ANTHROPIC_MAX_TOKENS")

    # ── Web-Suche ──────────────────────────────────────────────────────────────
    tavily_api_key: str = Field("", alias="TAVILY_API_KEY")

    # ── Microsoft Graph (E-Mail) ───────────────────────────────────────────────
    ms_client_id: str = Field("", alias="MS_CLIENT_ID")
    ms_client_secret: str = Field("", alias="MS_CLIENT_SECRET")
    ms_tenant_id: str = Field("", alias="MS_TENANT_ID")
    ms_sender_email: str = Field("info@direso.de", alias="MS_SENDER_EMAIL")

    # ── Social Media ───────────────────────────────────────────────────────────
    linkedin_access_token: str = Field("", alias="LINKEDIN_ACCESS_TOKEN")
    meta_access_token: str = Field("", alias="META_ACCESS_TOKEN")
    meta_page_id: str = Field("", alias="META_PAGE_ID")

    # ── Paths ──────────────────────────────────────────────────────────────────
    workspace_dir: Path = Field(Path("./workspace"), alias="WORKSPACE_DIR")
    astro_project_path: Path = Field(
        Path("/Users/fredericzoll/Desktop/Entwicklung/Astro direso"),
        alias="ASTRO_PROJECT_PATH",
    )

    def is_email_configured(self) -> bool:
        return bool(self.ms_client_id and self.ms_client_secret and self.ms_tenant_id)

    def is_social_configured(self) -> bool:
        return bool(self.linkedin_access_token or self.meta_access_token)

    def is_search_configured(self) -> bool:
        return bool(self.tavily_api_key)


# Singleton — alle Module importieren dieses Objekt
settings = Settings()

# Workspace-Verzeichnis sicherstellen
settings.workspace_dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print(f"Model:     {settings.anthropic_model}")
    print(f"Workspace: {settings.workspace_dir.resolve()}")
    print(f"Email:     {'✓ konfiguriert' if settings.is_email_configured() else '✗ fehlt'}")
    print(f"Search:    {'✓ konfiguriert' if settings.is_search_configured() else '✗ fehlt'}")
    print(f"Social:    {'✓ konfiguriert' if settings.is_social_configured() else '✗ fehlt'}")
