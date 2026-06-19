"""
Configuration management using pydantic-settings.
Based on docs/TRADING_SYSTEM_SPEC.md Section 6.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Google Cloud / Vertex AI ──
    GOOGLE_GENAI_USE_VERTEXAI: bool = True
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_KEY: str = ""

    # ── Anthropic (LiteLLM 경유 Claude 모델용) ──
    ANTHROPIC_API_KEY: str = ""

    # ── Agent Models ──
    # Gemini: "gemini-2.5-flash" / "gemini-2.5-pro"
    # Claude: "claude-opus-4-8" / "claude-sonnet-4-6" / "claude-haiku-4-5"
    NEWS_AGENT_MODEL: str = "gemini-2.5-flash"
    FUNDAMENTAL_AGENT_MODEL: str = "gemini-2.5-flash"
    TECHNICAL_AGENT_MODEL: str = "gemini-2.5-flash"
    EXPERT_AGENT_MODEL: str = "gemini-2.5-flash"
    RISK_AGENT_MODEL: str = "gemini-2.5-flash"
    ORCHESTRATOR_MODEL: str = "gemini-2.5-pro"

    # ── Agent Hosts (Docker service names) ──
    NEWS_AGENT_HOST: str = "news-agent"
    NEWS_AGENT_PORT: int = 8001
    FUNDAMENTAL_AGENT_HOST: str = "fundamental-agent"
    FUNDAMENTAL_AGENT_PORT: int = 8002
    TECHNICAL_AGENT_HOST: str = "technical-agent"
    TECHNICAL_AGENT_PORT: int = 8003
    EXPERT_AGENT_HOST: str = "expert-agent"
    EXPERT_AGENT_PORT: int = 8004
    RISK_AGENT_HOST: str = "risk-agent"
    RISK_AGENT_PORT: int = 8005

    # ── Toss Securities Open API ──
    TOSS_API_KEY: str = ""        # client_id (tsck_live_...)
    TOSS_SECRET_KEY: str = ""     # client_secret (tssk_live_...)
    TOSS_ACCOUNT_SEQ: str = ""    # X-Tossinvest-Account 헤더값. 비우면 /api/v1/accounts로 자동 조회

    # ── Database ──
    DATABASE_URL: str = "postgresql://trading:password@postgres:5432/trading"
    REDIS_URL: str = "redis://redis:6379/0"

    # ── Monitoring / Alerting ──
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    SLACK_WEBHOOK_URL: str = ""

    # ── Trading Limits ──
    MAX_SINGLE_STOCK_RATIO: float = 0.20  # 단일 종목 최대 20%
    MAX_RISK_PER_TRADE: float = 0.02      # 1회 거래 리스크 2%
    MAX_DAILY_TRADES: int = 10
    DRY_RUN: bool = True                   # True면 주문 미실행

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
