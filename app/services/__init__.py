"""Services layer for Gemini integration."""

from .gemini import (
    client,
    types,
    MODELS,
    IMAGE_MODELS,
    VIDEO_MODELS,
    TTS_MODELS,
    TTS_VOICES,
    generate_with_fallback,
    is_available,
    get_error,
)

# Conversation memory (SQLite persistence)
from .persistence import (
    PersistentConversationMemory,
    conversation_memory,
    ConversationTurn,
    CONVERSATION_TTL_HOURS,
    CONVERSATION_MAX_TURNS,
)

# Dynamic model registry (v4.0.0)
from .model_registry import model_registry, ModelRegistry

# OpenRouter multi-provider client (v4.0.0, optional)
from .openrouter import openrouter_client, OpenRouterClient


__all__ = [
    # Gemini client
    "client",
    "types",
    "MODELS",
    "IMAGE_MODELS",
    "VIDEO_MODELS",
    "TTS_MODELS",
    "TTS_VOICES",
    "generate_with_fallback",
    "is_available",
    "get_error",
    # Conversation memory (SQLite)
    "PersistentConversationMemory",
    "conversation_memory",
    "ConversationTurn",
    "CONVERSATION_TTL_HOURS",
    "CONVERSATION_MAX_TURNS",
    # Model registry
    "model_registry",
    "ModelRegistry",
    # OpenRouter
    "openrouter_client",
    "OpenRouterClient",
]
