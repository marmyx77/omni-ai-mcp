"""
omni-ai-mcp v4.0.0
FastMCP-based MCP server for Google Gemini AI integration.

This server provides access to Gemini's unique capabilities:
- 1M+ token context window for codebase analysis
- Native video/audio processing
- Google Search grounding
- Image generation (Imagen)
- Video generation (Veo)
- Multi-speaker text-to-speech
- RAG with File Search
- Deep Research Agent (Interactions API)
- Conversation management with local/cloud storage

Usage:
    python -m app.server
    # or
    python run.py
"""

import os
import sys
import asyncio
from typing import Optional, List
from functools import partial

# Import MCP SDK
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: mcp package not installed. Run: pip install 'mcp[cli]'", file=sys.stderr)
    sys.exit(1)

from .core import config, structured_logger
from .core.security import secure_read_file, validate_path

# Initialize FastMCP server
mcp = FastMCP(
    name="omni-ai-mcp",
)


# =============================================================================
# Import existing tool implementations
# =============================================================================

# These imports register tools with the legacy registry, but we'll wrap them
# for FastMCP compatibility
from .services.gemini import (
    client, types, MODELS, IMAGE_MODELS, VIDEO_MODELS, TTS_MODELS, TTS_VOICES,
    generate_with_fallback, is_available, get_error
)

# Import tool functions directly
from .tools.code.analyze_codebase import analyze_codebase
from .tools.code.generate_code import generate_code
from .tools.media.analyze_image import analyze_image
from .tools.web.web_search import web_search
from .tools.web.deep_research import deep_research
from .tools.media.generate_image import generate_image
from .tools.media.generate_video import generate_video
from .tools.media.text_to_speech import text_to_speech
from .tools.rag.file_search import file_search
from .tools.rag.file_store import create_file_store, upload_file, list_file_stores
from .tools.text.ask_gemini import ask_gemini
from .tools.text.code_review import code_review
from .tools.text.brainstorm import brainstorm
from .tools.text.challenge import challenge
from .tools.text.conversations import list_conversations, delete_conversation
from .tools.text.models import list_models
from .tools.text.ask_model import ask_model


# =============================================================================
# TOOL: Codebase Analysis (Gemini's 1M+ token advantage)
# =============================================================================

@mcp.tool()
def gemini_analyze_codebase(
    prompt: str,
    files: List[str],
    analysis_type: str = "general",
    model: str = "pro",
    continuation_id: Optional[str] = None
) -> str:
    """
    Analyze large codebases using Gemini's 1M token context window.
    Perfect for architecture analysis, cross-file review, and understanding complex projects.

    Args:
        prompt: Analysis task (e.g., "Explain the architecture", "Find security issues")
        files: File paths or glob patterns (e.g., ["src/**/*.py", "tests/*.py"])
        analysis_type: Focus area - architecture|security|refactoring|documentation|dependencies|general
        model: pro (default, best for analysis) or flash (faster)
        continuation_id: Thread ID to continue iterative analysis

    Returns:
        Detailed analysis of the codebase
    """
    return analyze_codebase(
        prompt=prompt,
        files=files,
        analysis_type=analysis_type,
        model=model,
        continuation_id=continuation_id
    )


# =============================================================================
# TOOL: Image Analysis (Vision)
# =============================================================================

@mcp.tool()
def gemini_analyze_image(
    image_path: str,
    prompt: str = "Describe this image in detail",
    model: str = "flash"
) -> str:
    """
    Analyze images using Gemini vision capabilities.
    Describe, extract text (OCR), identify objects, or answer questions about images.

    Args:
        image_path: Path to image file (PNG, JPG, JPEG, GIF, WEBP)
        prompt: What to analyze - "describe", "extract text", or a specific question
        model: flash (default, reliable) or pro (experimental)

    Returns:
        Image analysis response
    """
    return analyze_image(
        image_path=image_path,
        prompt=prompt,
        model=model
    )


# =============================================================================
# TOOL: Web Search (Google Grounding - unique)
# =============================================================================

@mcp.tool()
def gemini_web_search(
    query: str,
    model: str = "flash"
) -> str:
    """
    Search the web using Gemini with Google Search grounding.
    Returns answers with citations from authoritative sources.

    Args:
        query: Search query
        model: flash (default, faster) or pro (better synthesis)

    Returns:
        Search results with source citations
    """
    return web_search(query=query, model=model)


# =============================================================================
# TOOL: Deep Research (Interactions API)
# =============================================================================

@mcp.tool()
def gemini_deep_research(
    query: str,
    max_wait_minutes: int = 30,
    continuation_id: Optional[str] = None
) -> str:
    """
    Execute comprehensive research using Google's Deep Research Agent.
    Autonomously conducts multi-step web searches and synthesizes findings.

    The agent:
    - Plans and executes research strategy
    - Conducts multiple targeted web searches
    - Synthesizes findings into comprehensive reports
    - Provides citations and sources

    Use for: Market research, technical deep dives, literature reviews,
    trend analysis, competitive analysis, or any topic requiring thorough investigation.

    Note: Research typically takes 5-30 minutes depending on complexity.

    Args:
        query: Research topic or question. Be specific for best results.
        max_wait_minutes: Maximum wait time (5-60 minutes, default: 30)
        continuation_id: Optional interaction ID to continue previous research

    Returns:
        Comprehensive research report with citations
    """
    return deep_research(
        query=query,
        max_wait_minutes=max_wait_minutes,
        continuation_id=continuation_id
    )


# =============================================================================
# TOOL: Image Generation (Imagen)
# =============================================================================

@mcp.tool()
def gemini_generate_image(
    prompt: str,
    output_path: Optional[str] = None,
    aspect_ratio: str = "1:1",
    model: str = "pro",
    image_size: str = "2K"
) -> str:
    """
    Generate images using Gemini/Imagen native image generation.
    Use descriptive prompts (not keywords) for best results.

    Args:
        prompt: Detailed image description (e.g., "A photorealistic portrait of...")
        output_path: Path to save image (optional, returns base64 preview if not provided)
        aspect_ratio: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9
        model: pro (default, 4K quality) or flash (faster, 1K)
        image_size: Resolution for pro model - 1K, 2K, or 4K

    Returns:
        Path to generated image or generation status
    """
    return generate_image(
        prompt=prompt,
        output_path=output_path,
        aspect_ratio=aspect_ratio,
        model=model,
        image_size=image_size
    )


# =============================================================================
# TOOL: Video Generation (Veo - unique)
# =============================================================================

@mcp.tool()
def gemini_generate_video(
    prompt: str,
    output_path: Optional[str] = None,
    duration: int = 8,
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    model: str = "veo31",
    negative_prompt: Optional[str] = None
) -> str:
    """
    Generate videos using Google Veo 3.1 with native audio.
    Creates 4-8 second videos with realistic motion, dialogue, and sound effects.

    Args:
        prompt: Video description including subject, action, style, camera motion, sounds
        output_path: Path to save video (.mp4), saves to /tmp if not provided
        duration: 4, 6, or 8 seconds (8s required for 1080p)
        resolution: 720p (default) or 1080p (Veo 3.1 only, requires 8s)
        aspect_ratio: 16:9 (landscape) or 9:16 (portrait)
        model: veo31 (best), veo31_fast, veo3, veo3_fast, veo2 (legacy)
        negative_prompt: What NOT to include (avoid "no" or "don't")

    Returns:
        Path to generated video
    """
    return generate_video(
        prompt=prompt,
        output_path=output_path,
        duration=duration,
        resolution=resolution,
        aspect_ratio=aspect_ratio,
        model=model,
        negative_prompt=negative_prompt
    )


# =============================================================================
# TOOL: Text-to-Speech (Multi-speaker - unique)
# =============================================================================

@mcp.tool()
def gemini_text_to_speech(
    text: str,
    voice: str = "Kore",
    output_path: Optional[str] = None,
    speakers: Optional[List[dict]] = None,
    model: str = "flash"
) -> str:
    """
    Convert text to speech with 30 voice options.
    Supports single and multi-speaker (up to 2) audio.

    Args:
        text: Text to speak. For multi-speaker, use "Speaker1: text\\nSpeaker2: text"
        voice: Single speaker voice - Kore (Firm), Puck (Upbeat), Charon (Informative), etc.
        output_path: Path to save audio (.wav), saves to /tmp if not provided
        speakers: Multi-speaker config [{"name": "Speaker1", "voice": "Kore"}]
        model: flash (default, fast) or pro (higher quality)

    Returns:
        Path to generated audio file
    """
    return text_to_speech(
        text=text,
        voice=voice,
        output_path=output_path,
        speakers=speakers,
        model=model
    )


# =============================================================================
# TOOL: RAG File Search
# =============================================================================

@mcp.tool()
def gemini_file_search(
    question: str,
    store_name: str
) -> str:
    """
    Query documents in a File Search Store using RAG.
    Ask questions about uploaded documents with citations.

    Args:
        question: Question to ask about the documents
        store_name: Name of the file store to search

    Returns:
        Answer with citations from documents
    """
    return file_search(question=question, store_name=store_name)


# =============================================================================
# RAG Management Tools
# =============================================================================

@mcp.tool()
def gemini_create_file_store(name: str) -> str:
    """
    Create a new File Search Store for RAG queries.
    Use this before uploading files for document search.

    Args:
        name: Display name for the store

    Returns:
        Store creation confirmation with store name
    """
    return create_file_store(name=name)


@mcp.tool()
def gemini_upload_file(file_path: str, store_name: str) -> str:
    """
    Upload a file to a File Search Store for RAG queries.

    Args:
        file_path: Local file path to upload
        store_name: File Search Store name (from create_file_store)

    Returns:
        Upload confirmation
    """
    return upload_file(file_path=file_path, store_name=store_name)


@mcp.tool()
def gemini_list_file_stores() -> str:
    """
    List all available File Search Stores.

    Returns:
        List of store names and details
    """
    return list_file_stores()


# =============================================================================
# TOOL: Ask Gemini (Text Generation)
# =============================================================================

@mcp.tool(name="ask_gemini")
def _ask_gemini(
    prompt: str,
    model: str = "pro",
    temperature: float = 0.5,
    thinking_level: str = "off",
    include_thoughts: bool = False,
    continuation_id: Optional[str] = None,
    mode: str = "local",
    title: Optional[str] = None
) -> str:
    """
    Ask Gemini a question with optional model selection.
    Supports multi-turn conversations via continuation_id.

    Args:
        prompt: The question or prompt
        model: pro (Gemini 3 - best reasoning), flash (2.5 - balanced), fast (2.5 - high volume)
        temperature: Temperature 0.0-1.0 (default 0.5)
        thinking_level: off, low (fast), or high (deep reasoning)
        include_thoughts: If true, returns thought summaries
        continuation_id: Thread ID to continue a previous conversation
        mode: local (SQLite, default) or cloud (Interactions API with 55-day retention)
        title: Optional title for the conversation (auto-generated if not provided)

    Returns:
        Gemini's response with optional thinking process
    """
    return ask_gemini(
        prompt=prompt,
        model=model,
        temperature=temperature,
        thinking_level=thinking_level,
        include_thoughts=include_thoughts,
        continuation_id=continuation_id,
        mode=mode,
        title=title
    )


# =============================================================================
# TOOL: List Conversations (v3.3.0)
# =============================================================================

@mcp.tool()
def gemini_list_conversations(
    mode: str = "all",
    search: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    List all Gemini conversations.
    Shows title, mode (local/cloud), last activity, and turn count.
    Use to find and resume previous conversations.

    Args:
        mode: Filter by mode - all (default), local (SQLite), cloud (Interactions API)
        search: Search in conversation titles and first prompts
        limit: Maximum number of results (default: 20)

    Returns:
        Formatted table of conversations with IDs
    """
    return list_conversations(mode=mode, search=search, limit=limit)


# =============================================================================
# TOOL: Delete Conversation (v3.3.0)
# =============================================================================

@mcp.tool()
def gemini_delete_conversation(
    conversation_id: Optional[str] = None,
    title: Optional[str] = None
) -> str:
    """
    Delete a Gemini conversation from history.
    Can delete by ID or title.

    Args:
        conversation_id: The conversation ID to delete (from gemini_list_conversations)
        title: Alternative - delete by title (partial match supported)

    Returns:
        Confirmation message
    """
    return delete_conversation(conversation_id=conversation_id, title=title)


# =============================================================================
# TOOL: List Models (v4.0.0)
# =============================================================================

@mcp.tool()
def gemini_list_models(include_openrouter: bool = True) -> str:
    """
    List all available AI models by category.
    Shows Gemini models (discovered via API) and OpenRouter models if configured.
    Identifies deprecated models in your config.

    Args:
        include_openrouter: Include OpenRouter models (requires OPENROUTER_API_KEY, default: true)

    Returns:
        Report of available models per category with deprecation warnings
    """
    return list_models(include_openrouter=include_openrouter)


# =============================================================================
# TOOL: Ask Model — multi-provider (v4.0.0)
# =============================================================================

@mcp.tool(name="ask_model")
def ask_model_tool(
    prompt: str,
    model: Optional[str] = None,
    provider: str = "auto",
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
) -> str:
    """
    Ask any AI model — Gemini or 400+ models via OpenRouter.
    Auto-detects provider from model name; use provider='openrouter' to force OpenRouter.
    Requires OPENROUTER_API_KEY for non-Gemini models.
    Use gemini_list_models to discover available model IDs.

    Args:
        prompt: The question or prompt to send
        model: Model ID (e.g. 'gemini-3.1-pro-preview', 'openai/gpt-4o', 'meta-llama/llama-3.3-70b')
        provider: 'auto' (default), 'gemini', or 'openrouter'
        system_prompt: Optional system message / persona
        temperature: Sampling temperature 0.0-1.0 (default: 0.7)

    Returns:
        Model response text
    """
    return ask_model(
        prompt=prompt,
        model=model,
        provider=provider,
        system_prompt=system_prompt,
        temperature=temperature,
    )


# =============================================================================
# TOOL: Code Review
# =============================================================================

@mcp.tool()
def gemini_code_review(
    code: str,
    focus: str = "general",
    model: str = "pro"
) -> str:
    """
    Have Gemini review code with specific focus.
    Uses Gemini 3 Pro for best reasoning.

    Args:
        code: Code to review (supports @file references)
        focus: security, performance, readability, bugs, or general
        model: pro (default, thorough) or flash (faster)

    Returns:
        Detailed code review with recommendations
    """
    return code_review(code=code, focus=focus, model=model)


# =============================================================================
# TOOL: Brainstorm
# =============================================================================

@mcp.tool()
def gemini_brainstorm(
    topic: str,
    methodology: str = "auto",
    domain: Optional[str] = None,
    constraints: Optional[str] = None,
    context: str = "",
    idea_count: int = 10,
    include_analysis: bool = True
) -> str:
    """
    Advanced brainstorming with multiple methodologies.
    Uses Gemini 3 Pro for creative reasoning with structured frameworks.

    Args:
        topic: Topic or challenge to brainstorm
        methodology: auto, divergent, convergent, scamper, design-thinking, lateral
        domain: software, business, creative, marketing, product, research
        constraints: Known limitations (budget, time, technical, legal)
        context: Additional context or background
        idea_count: Target number of ideas (default 10)
        include_analysis: Include feasibility, impact, innovation scores

    Returns:
        Structured brainstorming output with ideas and analysis
    """
    return brainstorm(
        topic=topic,
        methodology=methodology,
        domain=domain,
        constraints=constraints,
        context=context,
        idea_count=idea_count,
        include_analysis=include_analysis
    )


# =============================================================================
# TOOL: Challenge (Devil's Advocate)
# =============================================================================

@mcp.tool()
def gemini_challenge(
    statement: str,
    context: str = "",
    focus: str = "general"
) -> str:
    """
    Critical thinking tool - challenges ideas, plans, or code to find flaws.
    Does NOT agree with the user - actively looks for problems.
    Use this before implementing to catch issues early.

    Args:
        statement: The idea, plan, architecture, or code to critique
        context: Optional background context or constraints
        focus: general, security, performance, maintainability, scalability, cost

    Returns:
        Critical analysis with flaws, risks, assumptions, and alternatives
    """
    return challenge(statement=statement, context=context, focus=focus)


# =============================================================================
# TOOL: Generate Code
# =============================================================================

@mcp.tool()
def gemini_generate_code(
    prompt: str,
    context_files: Optional[List[str]] = None,
    language: str = "auto",
    style: str = "production",
    model: str = "pro",
    output_dir: Optional[str] = None
) -> str:
    """
    Generate code using Gemini. Returns structured output with file operations.
    Best for UI components, boilerplate, and tasks where Gemini excels.

    Args:
        prompt: What code to generate (be specific about requirements)
        context_files: Files to include as context (use @file syntax)
        language: auto, typescript, javascript, python, rust, go, java, etc.
        style: production (full types/docs), prototype (basic), minimal (bare essentials)
        model: pro (default, best quality) or flash (faster)
        output_dir: Optional directory to save files (returns summary instead of XML)

    Returns:
        Generated code in XML format or save summary if output_dir specified
    """
    return generate_code(
        prompt=prompt,
        context_files=context_files or [],
        language=language,
        style=style,
        model=model,
        output_dir=output_dir
    )


# =============================================================================
# MCP Resources (Standard pattern)
# =============================================================================

@mcp.resource("file://{path}")
def read_file_resource(path: str) -> str:
    """
    Read file contents as MCP Resource.
    Provides secure, sandboxed file access.

    Args:
        path: File path to read

    Returns:
        File contents
    """
    return secure_read_file(path)


# =============================================================================
# Entry Point
# =============================================================================

def main():
    """Run the MCP server."""
    if not is_available():
        error = get_error()
        structured_logger.error(f"Gemini client initialization failed: {error}")
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    structured_logger.info(f"Starting omni-ai-mcp v{config.version}")
    structured_logger.info(f"Tools available: 20 (including model registry and multi-provider)")

    # Run the FastMCP server
    mcp.run()


if __name__ == "__main__":
    main()
