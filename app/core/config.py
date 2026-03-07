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
    version: str = "4.0.0"

    # API Configuration
    api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))

    # Model Versions (can be overridden via environment variables)
    # Text Generation Models
    model_pro: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_PRO", "gemini-3.1-pro-preview")
    )
    model_flash: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_FLASH", "gemini-2.5-flash")
    )
    # Image Models
    model_image_pro: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_IMAGE_PRO", "gemini-3.1-pro-image-preview")
    )
    model_image_flash: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_IMAGE_FLASH", "gemini-2.5-flash-image")
    )
    # Video Models
    model_veo31: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_VEO31", "veo-3.1-generate-preview")
    )
    model_veo31_fast: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_VEO31_FAST", "veo-3.1-fast-generate-preview")
    )
    model_veo3: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_VEO3", "veo-3.0-generate-001")
    )
    model_veo3_fast: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_VEO3_FAST", "veo-3.0-fast-generate-001")
    )
    model_veo2: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_VEO2", "veo-2.0-generate-001")
    )
    # TTS Models
    model_tts_flash: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_TTS_FLASH", "gemini-2.5-flash-preview-tts")
    )
    model_tts_pro: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_TTS_PRO", "gemini-2.5-pro-preview-tts")
    )
    # Research Agent
    model_deep_research: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_DEEP_RESEARCH", "deep-research-pro-preview")
    )

    # OpenRouter (optional multi-provider support)
    openrouter_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", "")
    )
    openrouter_default_model: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4o")
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
