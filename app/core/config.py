"""
Configuration management for omni-ai-mcp.
Centralizes all environment variables and settings.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Config:
    """
    Central configuration for omni-ai-mcp.

    All settings are loaded from environment variables with sensible defaults.
    """

    # Version
    version: str = "4.6.3"

    # API Configuration
    api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))

    # Model IDs. These are STATIC FALLBACKS: at runtime the model registry
    # auto-detects the newest matching model the API exposes (v4.6.0), unless
    # the corresponding GEMINI_MODEL_* variable is set explicitly (env wins).
    model_autodetect: bool = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_AUTODETECT", "true").lower() == "true"
    )
    # Text Generation Models
    model_pro: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_PRO", "gemini-3.1-pro-preview")
    )
    model_flash: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_FLASH", "gemini-3.8-flash")
    )
    model_flash_lite: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_FLASH_LITE", "gemini-3.5-flash-lite")
    )
    # Image Models
    model_image_pro: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_IMAGE_PRO", "gemini-3-pro-image")
    )
    model_image_flash: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_IMAGE_FLASH", "gemini-3.1-flash-image")
    )
    # Video Models (Veo 3.0 / 2.0 were removed upstream — no longer configurable)
    model_veo31: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_VEO31", "veo-3.1-generate-preview")
    )
    model_veo31_fast: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_VEO31_FAST", "veo-3.1-fast-generate-preview")
    )
    model_veo31_lite: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_VEO31_LITE", "veo-3.1-lite-generate-preview")
    )
    # TTS Models
    model_tts_flash: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_TTS_FLASH", "gemini-3.1-flash-tts-preview")
    )
    model_tts_pro: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_TTS_PRO", "gemini-2.5-pro-preview-tts")
    )
    # Research Agent
    model_deep_research: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_DEEP_RESEARCH", "deep-research-preview-04-2026")
    )

    # OpenRouter (optional multi-provider support)
    openrouter_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", "")
    )
    openrouter_default_model: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4o")
    )
    openrouter_timeout: int = field(
        default_factory=lambda: int(os.environ.get("OPENROUTER_TIMEOUT", "120"))
    )

    # Conversation Memory
    conversation_ttl_hours: int = field(
        default_factory=lambda: int(os.environ.get("GEMINI_CONVERSATION_TTL_HOURS", "3"))
    )
    conversation_max_turns: int = field(
        default_factory=lambda: int(os.environ.get("GEMINI_CONVERSATION_MAX_TURNS", "50"))
    )

    # Security - Sandboxing
    sandbox_root: str = field(
        default_factory=lambda: os.environ.get("GEMINI_SANDBOX_ROOT", os.getcwd())
    )
    sandbox_enabled: bool = field(
        default_factory=lambda: os.environ.get("GEMINI_SANDBOX_ENABLED", "true").lower() == "true"
    )
    max_file_size_bytes: int = field(
        default_factory=lambda: int(os.environ.get("GEMINI_MAX_FILE_SIZE", str(100 * 1024)))
    )

    # Activity Logging
    activity_log_enabled: bool = field(
        default_factory=lambda: os.environ.get("GEMINI_ACTIVITY_LOG", "true").lower() == "true"
    )
    log_dir: str = field(
        default_factory=lambda: os.environ.get("GEMINI_LOG_DIR", os.path.expanduser("~/.omni-ai-mcp"))
    )
    log_max_bytes: int = field(
        default_factory=lambda: int(os.environ.get("GEMINI_LOG_MAX_BYTES", str(10 * 1024 * 1024)))
    )
    log_backup_count: int = field(
        default_factory=lambda: int(os.environ.get("GEMINI_LOG_BACKUP_COUNT", "5"))
    )
    log_format: str = field(
        default_factory=lambda: os.environ.get("GEMINI_LOG_FORMAT", "text").lower()
    )

    # Tool Management
    disabled_tools: List[str] = field(
        default_factory=lambda: [
            t.strip() for t in os.environ.get("GEMINI_DISABLED_TOOLS", "").split(",") if t.strip()
        ]
    )

    # Limits
    mcp_prompt_size_limit: int = 60_000  # characters

    @property
    def conversation_cleanup_interval(self) -> int:
        """Calculate cleanup interval based on TTL."""
        return max(300, (self.conversation_ttl_hours * 3600) // 10)

    def validate(self) -> Optional[str]:
        """
        Validate configuration.

        Returns:
            Error message if invalid, None if valid.
        """
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            return "Please set GEMINI_API_KEY environment variable"
        return None


# Global config instance
config = Config()
