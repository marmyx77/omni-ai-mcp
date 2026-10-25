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
except ImportError as exc:
    print(
        f"Error: cannot import FastMCP from the mcp package ({exc}). "
        "Run: pip install 'mcp[cli]>=1.0.0,<2'",
        file=sys.stderr,
    )
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
from .tools.media.transcribe_audio import transcribe_audio
from .tools.media.analyze_video import analyze_video
from .tools.media.generate_music import generate_music
from .tools.media.voices import list_voices, design_voice, replicate_voice
from .tools.text.embed import embed
from .tools.web.agent_task import agent_task
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
# TOOL: Image Analysis (Vision + spatial reasoning)
# =============================================================================

@mcp.tool()
def gemini_analyze_image(
    image_path: Optional[str] = None,
    prompt: str = "Describe this image in detail",
    model: str = "flash",
    image_paths: Optional[List[str]] = None,
    media_resolution: str = "medium"
) -> str:
    """
    Analyze one or more images: describe, OCR, Q&A, compare screenshots, review UI, read diagrams.
    model='robotics' (Gemini Robotics ER) does spatial reasoning: points, bounding boxes,
    trajectories as JSON with [y, x] normalized to 0-1000.

    Args:
        image_path: Path to one image (PNG, JPG, JPEG, GIF, WEBP)
        prompt: What to analyze
        model: flash (default), pro (newest flagship), flash-lite (cheapest), robotics (spatial JSON)
        image_paths: Several images to compare or analyze as a sequence (overrides image_path)
        media_resolution: low, medium (default) or high detail

    Returns:
        Image analysis response
    """
    return analyze_image(
        image_path=image_path,
        image_paths=image_paths,
        prompt=prompt,
        model=model,
        media_resolution=media_resolution
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
    query: str = "",
    max_wait_minutes: int = 30,
    continuation_id: Optional[str] = None,
    depth: str = "standard"
) -> str:
    """
    Execute comprehensive research using Google's Deep Research Agent.
    Autonomously plans, runs many web searches and writes a cited report (5-60 minutes).

    Args:
        query: Research topic or question. Leave empty with continuation_id to retrieve a previous research (e.g. after a timeout).
        max_wait_minutes: Maximum wait time (5-60 minutes, default: 30). On timeout the research keeps running: call again with continuation_id and no query.
        continuation_id: Previous interaction ID. Empty query = retrieve/resume it; with a query = follow-up research chained to it
        depth: standard (default, fast and efficient) or max (Deep Research Max: maximum comprehensiveness, slower and pricier)

    Returns:
        Comprehensive research report with citations
    """
    return deep_research(
        query=query,
        max_wait_minutes=max_wait_minutes,
        continuation_id=continuation_id,
        depth=depth
    )


# =============================================================================
# TOOL: Image Generation (Nano Banana family)
# =============================================================================

@mcp.tool()
def gemini_generate_image(
    prompt: str,
    output_path: Optional[str] = None,
    model: str = "pro",
    aspect_ratio: str = "1:1",
    image_size: str = "auto",
    input_images: Optional[List[str]] = None,
    google_search: bool = False,
    thinking_level: str = "auto"
) -> str:
    """
    Generate or edit images with Google's Nano Banana models: infographics with accurate data,
    readable text, technical diagrams, maps, illustrations; edits and multi-image fusion.

    Args:
        prompt: Description, or the change to apply to input_images
        output_path: Where to save the image
        model: pro (default, Nano Banana Pro), flash (Nano Banana 2.1: fast, panoramic, 14 references), lite (cheapest)
        aspect_ratio: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9; panoramic 1:4, 4:1, 1:8, 8:1 on flash
        image_size: auto (2K on pro, model default elsewhere), 512, 1K, 2K or 4K
        input_images: Up to 14 images to edit, combine or use as references
        google_search: Ground the image in Google Search results (facts, current events)
        thinking_level: auto, minimal, medium or high

    Returns:
        Path to the saved image (or a base64 preview)
    """
    return generate_image(
        prompt=prompt,
        input_images=input_images,
        model=model,
        aspect_ratio=aspect_ratio,
        image_size=image_size,
        output_path=output_path,
        google_search=google_search,
        thinking_level=thinking_level
    )


# =============================================================================
# TOOL: Video Generation & Editing (Gemini Omni Flash)
# =============================================================================

@mcp.tool()
def gemini_generate_video(
    prompt: str,
    output_path: Optional[str] = None,
    image_paths: Optional[List[str]] = None,
    video_path: Optional[str] = None,
    task: str = "auto",
    aspect_ratio: str = "16:9",
    resolution: str = "720p",
    duration: Optional[int] = None,
    negative_prompt: Optional[str] = None,
    continuation_id: Optional[str] = None,
    retrieve_id: Optional[str] = None,
    max_wait_minutes: int = 10,
    model: str = "omni"
) -> str:
    """
    Generate or edit a 3-10 s video with native audio using Gemini Omni Flash
    (Veo 3.1 Preview was shut down in the Gemini API on 2026-10-22).

    Args:
        prompt: What to generate or change (subject, action, camera, light, audio; timecodes like [0-3s] work).
                Bind images with <FIRST_FRAME>, <LAST_FRAME>, <IMAGE_REF_0>...; for edits add "Keep everything else the same".
        output_path: Where to save the .mp4
        image_paths: Start frame, first+last frames (interpolation) or subject/style references (up to 14)
        video_path: Clip <= 10 s to edit or extend (not available in the EEA, CH, UK)
        task: auto (default), text_to_video, image_to_video, reference_to_video, edit, extend
        aspect_ratio: 16:9 (default) or 9:16
        resolution: 360p, 720p (default), 1080p or 4k (upscaled)
        duration: Optional length in seconds (3-10)
        negative_prompt: Things to avoid (appended to the prompt)
        continuation_id: Edit or extend a video generated earlier (its interaction id)
        retrieve_id: Save the video of a generation that timed out
        max_wait_minutes: How long to wait (default 10)
        model: omni (Veo names are accepted and mapped to Omni)

    Returns:
        Path to the video and a continuation_id for further edits
    """
    return generate_video(
        prompt=prompt,
        image_paths=image_paths,
        video_path=video_path,
        task=task,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        duration=duration,
        negative_prompt=negative_prompt,
        continuation_id=continuation_id,
        retrieve_id=retrieve_id,
        output_path=output_path,
        max_wait_minutes=max_wait_minutes,
        model=model
    )


# =============================================================================
# TOOL: Text-to-Speech (Gemini 3.8 TTS)
# =============================================================================

@mcp.tool()
def gemini_text_to_speech(
    text: str,
    voice: str = "Kore",
    output_path: Optional[str] = None,
    speakers: Optional[List[dict]] = None,
    model: str = "flash",
    style: Optional[str] = None,
    language: Optional[str] = None
) -> str:
    """
    Convert text to speech with Gemini 3.8 TTS: one voice or a two-speaker dialogue.

    Args:
        text: Exact text. For two speakers write one turn per line: "Joe: ...\nJane: ..."
        voice: Featured voice (Kore, Puck, Charon, ...), a Voice Library ID (gemini_list_voices), or a voice_.../voicekey_... ID
        output_path: Where to save the .wav
        speakers: [{"name": "Joe", "voice": "Puck", "style": "cheerful"}, {"name": "Jane", "voice": "Kore"}]
        model: flash (default, best fidelity), lite (fastest/cheapest), pro (alias of flash)
        style: Delivery direction, e.g. "slow, warm audiobook narration"
        language: Optional BCP-47 language, e.g. "it-IT"

    Returns:
        Path to the generated WAV
    """
    return text_to_speech(
        text=text,
        voice=voice,
        output_path=output_path,
        speakers=speakers,
        model=model,
        style=style,
        language=language
    )


# =============================================================================
# TOOL: Audio Transcription (speech to text)
# =============================================================================

@mcp.tool()
def gemini_transcribe_audio(
    audio_path: str,
    diarization: bool = False,
    word_timestamps: bool = False,
    language_codes: Optional[List[str]] = None,
    vocabulary: Optional[List[str]] = None,
    mode: str = "auto",
    output_path: Optional[str] = None
) -> str:
    """
    Transcribe an audio file (speech to text) with Gemini's dedicated transcription model.
    85+ languages auto-detected, code-switching handled. Up to 1 hour of audio
    (30 minutes when diarization or word_timestamps are on).

    Args:
        audio_path: Local audio file (wav, mp3, m4a, aac, ogg, opus, flac, aiff, webm)
        diarization: Label speakers (up to 8). Not combinable with vocabulary
        word_timestamps: Return timestamped sentences ([mm:ss.s] prefix)
        language_codes: Optional BCP-47 hints, e.g. ["it", "en"]; omit for auto-detect
        vocabulary: Domain terms/names to bias recognition toward
        mode: auto (default: smart, or verbatim when word_timestamps is on), smart (fillers removed, numbers/dates formatted), verbatim
        output_path: Optional file to save the transcript (.json = structured, else text)

    Returns:
        Transcript with a header naming the model and detected language(s)
    """
    return transcribe_audio(
        audio_path=audio_path,
        diarization=diarization,
        word_timestamps=word_timestamps,
        language_codes=language_codes,
        vocabulary=vocabulary,
        mode=mode,
        output_path=output_path
    )


# =============================================================================
# TOOL: Video Understanding (static + agentic)
# =============================================================================

@mcp.tool()
def gemini_analyze_video(
    prompt: str,
    video_path: Optional[str] = None,
    youtube_url: Optional[str] = None,
    processing: str = "static",
    model: str = "flash",
    resolution: Optional[str] = None,
    max_wait_minutes: int = 20
) -> str:
    """
    Understand a video (local file or public YouTube URL): summary, Q&A, key moments with MM:SS
    timestamps, what is said and shown.

    Args:
        prompt: What to do with the video
        video_path: Local video file
        youtube_url: Public YouTube URL (alternative to video_path)
        processing: static (default, 1 FPS, short clips) or agentic (navigates long videos on demand, up to 88% fewer tokens)
        model: flash (default), pro, flash-lite, robotics (spatial/temporal JSON)
        resolution: Optional low/medium/high frame detail
        max_wait_minutes: How long to wait (default 20)

    Returns:
        The analysis
    """
    return analyze_video(
        prompt=prompt,
        video_path=video_path,
        youtube_url=youtube_url,
        processing=processing,
        model=model,
        resolution=resolution,
        max_wait_minutes=max_wait_minutes
    )


# =============================================================================
# TOOL: Music Generation (Lyria)
# =============================================================================

@mcp.tool()
def gemini_generate_music(
    prompt: str,
    output_path: Optional[str] = None,
    model: str = "full",
    image_paths: Optional[List[str]] = None,
    retrieve_id: Optional[str] = None,
    max_wait_minutes: int = 10
) -> str:
    """
    Generate music with Google Lyria: full songs with vocals and lyrics, or 30-second clips.

    Args:
        prompt: Genre, mood, instruments, tempo, vocals or instrumental, lyrics language, structure and length
        output_path: Where to save the .mp3
        model: full (default, newest Lyria: full-length songs) or clip (30 s)
        image_paths: Optional images to inspire the music
        retrieve_id: Save the song of a generation that timed out
        max_wait_minutes: How long to wait (default 10)

    Returns:
        Path to the MP3 and the generated lyrics
    """
    return generate_music(
        prompt=prompt,
        image_paths=image_paths,
        model=model,
        output_path=output_path,
        max_wait_minutes=max_wait_minutes,
        retrieve_id=retrieve_id
    )


# =============================================================================
# TOOL: Voice Library, Voice Design, Voice Replication
# =============================================================================

@mcp.tool()
def gemini_list_voices(
    language_codes: Optional[List[str]] = None,
    gender: Optional[List[str]] = None,
    pitch: Optional[List[str]] = None,
    accent: Optional[List[str]] = None,
    persona: Optional[List[str]] = None,
    contexts: Optional[List[str]] = None,
    voice_type: Optional[List[str]] = None,
    search: Optional[str] = None,
    page_size: int = 50,
    page_token: Optional[str] = None
) -> str:
    """
    Browse the Gemini Voice Library (hundreds of TTS voices) and your custom voices.

    Args:
        language_codes: BCP-47 codes, e.g. ["it-IT"]
        gender: female, male, neutral
        pitch: low, medium, high
        accent: e.g. ["British"]
        persona: e.g. ["Narrator"]
        contexts: e.g. ["Audiobook", "News"]
        voice_type: prebuilt, prompted (designed), replicated
        search: Free text on name and description
        page_size: Results per page (default 50, max 1000)
        page_token: Next page token

    Returns:
        Voice IDs to use in gemini_text_to_speech
    """
    return list_voices(
        language_codes=language_codes, gender=gender, pitch=pitch, accent=accent, persona=persona,
        contexts=contexts, voice_type=voice_type, search=search, page_size=page_size, page_token=page_token
    )


@mcp.tool()
def gemini_design_voice(
    description: str,
    display_name: str = "Custom voice",
    gender: Optional[str] = None,
    language_code: Optional[str] = None,
    model: str = "flash",
    preview_path: Optional[str] = None
) -> str:
    """
    Create a persistent custom TTS voice from a plain-language description.

    Args:
        description: Age, timbre, accent, attitude, e.g. "A warm astronomer in his 60s with a gentle British accent"
        display_name: Name of the voice
        gender: female, male or neutral
        language_code: BCP-47, e.g. "it-IT"
        model: flash (default) or lite
        preview_path: Where to save the WAV preview

    Returns:
        The voice_... ID and the preview path
    """
    return design_voice(description=description, display_name=display_name, gender=gender,
                        language_code=language_code, model=model, preview_path=preview_path)


@mcp.tool()
def gemini_replicate_voice(
    source_audio_path: str,
    consent_audio_path: str,
    display_name: str = "Replicated voice",
    store: bool = True,
    model: str = "flash"
) -> str:
    """
    Replicate a consenting adult speaker's voice for TTS. Needs a 10-30 s reference WAV and a consent WAV
    of the SAME speaker reading Google's consent statement ("I am the owner of this voice and I consent to
    Google using this voice to create a synthetic voice model."). Google verifies consent.

    Args:
        source_audio_path: 10-30 s WAV of clean natural speech
        consent_audio_path: WAV of the same speaker reading the consent statement
        display_name: Name of the voice
        store: true = persistent voice_... ID; false = stateless voicekey_... you keep
        model: flash (default) or lite

    Returns:
        The voice ID or key
    """
    return replicate_voice(source_audio_path=source_audio_path, consent_audio_path=consent_audio_path,
                           display_name=display_name, store=store, model=model)


# =============================================================================
# TOOL: Embeddings (Gemini Embedding 2, multimodal)
# =============================================================================

@mcp.tool()
def gemini_embed(
    texts: Optional[List[str]] = None,
    file_paths: Optional[List[str]] = None,
    task: str = "none",
    title: Optional[str] = None,
    aggregate: bool = False,
    output_dimensionality: Optional[int] = None,
    output_path: Optional[str] = None
) -> str:
    """
    Embed text, images, audio, video and PDF in one vector space (semantic search, clustering, cross-modal retrieval).

    Args:
        texts: Texts to embed
        file_paths: Images (PNG/JPEG <= 6), audio (MP3/WAV <= 180 s), video, PDF
        task: none, search_query, search_document, question_answering, fact_checking, code_retrieval, classification, clustering, similarity
        title: Title for search_document texts
        aggregate: One vector for all inputs instead of one per input
        output_dimensionality: 128-3072 (768 or 1536 recommended)
        output_path: Save vectors as JSON

    Returns:
        JSON with the vectors, or the path of the saved file
    """
    return embed(texts=texts, file_paths=file_paths, task=task, title=title, aggregate=aggregate,
                 output_dimensionality=output_dimensionality, output_path=output_path)


# =============================================================================
# TOOL: Antigravity managed agent
# =============================================================================

@mcp.tool()
def gemini_agent_task(
    task: str = "",
    continuation_id: Optional[str] = None,
    file_paths: Optional[List[str]] = None,
    tools: Optional[List[str]] = None,
    model: str = "flash",
    output_dir: Optional[str] = None,
    max_wait_minutes: int = 30
) -> str:
    """
    Delegate a multi-step task to Google's Antigravity agent, which works in its own Google-hosted Linux
    sandbox: runs Bash/Python/Node, installs packages, reads/writes files, searches and reads the web.

    Args:
        task: What to accomplish. Empty + continuation_id = retrieve a run that timed out
        continuation_id: Continue in the same sandbox (files persist) or retrieve a run
        file_paths: Local files to hand to the agent
        tools: Restrict to code_execution, google_search, url_context
        model: flash (default) or pro (newest flagship)
        output_dir: Save media/documents the agent returns here
        max_wait_minutes: How long to wait (default 30)

    Returns:
        The agent's answer and a continuation_id
    """
    return agent_task(task=task, continuation_id=continuation_id, file_paths=file_paths, tools=tools,
                      model=model, output_dir=output_dir, max_wait_minutes=max_wait_minutes)


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
    thinking_level: str = "auto",
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
        model: pro (newest Gemini Pro - best reasoning), flash (newest Gemini Flash - balanced), fast (same as flash), flash-lite (cheapest). IDs auto-detected from the API; see gemini_list_models
        temperature: Temperature 0.0-1.0 (default 0.5)
        thinking_level: auto (model default, default), low (fastest), medium, high (deepest). Gemini 3+ always thinks: auto is not zero
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
        model: Model ID or alias (e.g. 'pro' = newest Gemini flagship, 'gemini-4-argon', 'gemma-4-31b-it', 'openai/gpt-4o')
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
