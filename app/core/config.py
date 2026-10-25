"""
Configuration management for omni-ai-mcp.
Centralizes all environment variables and settings.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


WORKSPACE_FALLBACK = os.path.join("~", "omni-ai-workspace")


def _default_sandbox_root() -> str:
    """
    GEMINI_SANDBOX_ROOT, else the directory the server was started in — unless
    that is "/" or the home folder (Claude Desktop and some clients start servers
    there), which would expose the whole disk: then ~/omni-ai-workspace.
    """
    explicit = os.environ.get("GEMINI_SANDBOX_ROOT", "").strip()
    if explicit:
        return os.path.realpath(os.path.expanduser(explicit))
    cwd = os.path.realpath(os.getcwd())
    home = os.path.realpath(os.path.expanduser("~"))
    if cwd in ("/", home) or cwd == os.path.dirname(home):
        workspace = os.path.realpath(os.path.expanduser(WORKSPACE_FALLBACK))
        try:
            os.makedirs(workspace, exist_ok=True)
        except OSError:
            pass
        return workspace
    return cwd


@dataclass
class Config:
    """
    Central configuration for omni-ai-mcp.

    All settings are loaded from environment variables with sensible defaults.
    """

    # Version
    version: str = "4.8.2"

    # API Configuration
    api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))

    # Model IDs. These are STATIC FALLBACKS: at runtime the model registry
    # auto-detects the newest matching model the API exposes (v4.6.0), unless
    # the corresponding GEMINI_MODEL_* variable is set explicitly (env wins).
    model_autodetect: bool = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_AUTODETECT", "true").lower() == "true"
    )
    # Text Generation Models ("pro" = flagship reasoning model: Gemini 4 Argon since v4.8.0)
    model_pro: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_PRO", "gemini-4-argon")
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
        default_factory=lambda: os.environ.get("GEMINI_MODEL_IMAGE_FLASH", "gemini-nano-banana-2.1")
    )
    model_image_lite: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_IMAGE_LITE", "gemini-3.1-flash-lite-image")
    )
    # Video (Veo 3.1 Preview was shut down in the Gemini API on 2026-10-22: Gemini Omni Flash replaces it)
    model_video: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_VIDEO", "gemini-omni-1.1-flash")
    )
    # TTS Models
    model_tts_flash: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_TTS_FLASH", "gemini-3.8-flash-tts")
    )
    model_tts_lite: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_TTS_LITE", "gemini-3.8-flash-lite-tts")
    )
    # Speech-to-text
    model_transcribe: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_TRANSCRIBE", "gemini-3.5-transcribe")
    )
    # Music (Lyria)
    model_music: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_MUSIC", "lyria-3.5")
    )
    model_music_clip: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_MUSIC_CLIP", "lyria-3-clip-preview")
    )
    # Research Agents
    model_deep_research: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_DEEP_RESEARCH", "deep-research-preview-04-2026")
    )
    model_deep_research_max: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_DEEP_RESEARCH_MAX", "deep-research-max-preview-04-2026")
    )
    # Managed coding/computing agent (Antigravity)
    model_agent: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_AGENT", "antigravity-preview-09-2026")
    )
    # Embeddings (multimodal)
    model_embedding: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_EMBEDDING", "gemini-embedding-2")
    )
    # Embodied / spatial reasoning
    model_robotics: str = field(
        default_factory=lambda: os.environ.get("GEMINI_MODEL_ROBOTICS", "gemini-robotics-er-2-preview")
    )
    # Output budget: thinking and answer share it on Gemini 3+ (Google recommends >= 32K; default 64K)
    max_output_tokens: int = field(
        default_factory=lambda: int(os.environ.get("GEMINI_MAX_OUTPUT_TOKENS", "65536"))
    )

    # OpenRouter (optional multi-provider support)
    openrouter_api_key: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", "")
    )
    openrouter_default_model: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_DEFAULT_MODEL", "openai/gpt-4o")
    )
    request_timeout: int = field(
        # Per-request HTTP timeout for the Gemini client, in seconds (a hung call
        # would otherwise block the MCP tool forever). Long jobs poll, so 15 min is ample.
        default_factory=lambda: int(os.environ.get("GEMINI_REQUEST_TIMEOUT", "900"))
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
    sandbox_root: str = field(default_factory=lambda: _default_sandbox_root())
    sandbox_enabled: bool = field(
        default_factory=lambda: os.environ.get("GEMINI_SANDBOX_ENABLED", "true").lower() == "true"
    )
    output_dir: str = field(
        default_factory=lambda: os.path.expanduser(os.environ.get("GEMINI_OUTPUT_DIR", "").strip())
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
