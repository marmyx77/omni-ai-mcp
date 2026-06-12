"""
Ask Gemini Tool

Text generation with model selection, thinking capabilities, and conversation memory.
"""

import re
from typing import Optional

from ...tools.registry import tool
from ...services import (
    types,
    MODELS,
    generate_with_fallback,
    conversation_memory,
    CONVERSATION_MAX_TURNS,
)
from ...utils.file_refs import expand_file_references
from ...utils.tokens import check_prompt_size
from ...schemas.inputs import AskGeminiInput


ASK_GEMINI_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "description": "The question or prompt"},
        "model": {
            "type": "string",
            "enum": ["pro", "flash", "fast"],
            "description": "Model: pro (Gemini 3 - best reasoning, default), flash (2.5 - balanced), fast (2.5 - high volume, low reasoning)",
            "default": "pro"
        },
        "temperature": {
            "type": "number",
            "description": "Temperature 0.0-1.0",
            "default": 0.5
        },
        "thinking_level": {
            "type": "string",
            "enum": ["off", "low", "high"],
            "description": "Thinking level for Gemini 3 Pro: 'off' (no thinking), 'low' (fast), 'high' (deep reasoning). For 2.5 models uses budget instead.",
            "default": "off"
        },
        "include_thoughts": {
            "type": "boolean",
            "description": "If true, returns thought summaries showing model's reasoning process",
            "default": False
        },
        "continuation_id": {
            "type": "string",
            "description": "Thread ID to continue a previous conversation. Gemini will remember previous context. Omit to start a new conversation."
        },
        "mode": {
            "type": "string",
            "enum": ["local", "cloud"],
            "description": "Conversation mode: 'local' (SQLite, default) for fast temporary chats, 'cloud' (Interactions API) for long-term conversations with 55-day retention",
            "default": "local"
        },
        "title": {
            "type": "string",
            "description": "Optional title for the conversation. If not provided, auto-generated from the first prompt. Used for listing/resuming conversations."
        }
    },
    "required": ["prompt"]
}


@tool(
    name="ask_gemini",
    description="Ask Gemini a question with optional model selection. Supports multi-turn conversations via continuation_id. Use mode='cloud' for long-term conversations with 55-day retention.",
    input_schema=ASK_GEMINI_SCHEMA,
    input_model=AskGeminiInput,
    tags=["text", "conversation"]
)
def ask_gemini(
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
    Gemini query with model selection, thinking capabilities, and conversation memory.

    Thinking allows the model to engage in deeper reasoning for complex tasks.
    - For Gemini 3 Pro: uses thinking_level ("low" or "high")
    - For Gemini 2.5: uses thinking_budget (auto-calculated based on level)

    Supports @file references in prompts to include file contents:
    - @file.py - Include single file
    - @src/main.py - Path with directories
    - @*.py - Glob patterns
    - @src/**/*.ts - Recursive glob patterns

    Supports multi-turn conversations via continuation_id:
    - Omit continuation_id to start a new conversation
    - Pass continuation_id to continue a previous conversation
    - Response includes continuation_id for subsequent calls

    Conversation modes (v3.3.0):
    - mode="local": SQLite storage, fast, configurable TTL (default)
    - mode="cloud": Interactions API, 55-day retention, survives restarts

    Use title parameter to name conversations for easy retrieval.
    """
    # Auto-detect mode from continuation_id prefix
    if continuation_id and continuation_id.startswith("int_"):
        mode = "cloud"

    # Handle cloud mode via Interactions API
    if mode == "cloud":
        return _ask_gemini_cloud(
            prompt=prompt,
            model=model,
            temperature=temperature,
            thinking_level=thinking_level,
            include_thoughts=include_thoughts,
            continuation_id=continuation_id,
            title=title
        )

    # === LOCAL MODE (SQLite) ===
    # Expand @file references in prompt
    original_prompt = prompt
    prompt = expand_file_references(prompt)

    # Check prompt size after file expansion
    size_error = check_prompt_size(prompt)
    if size_error:
        return f"**Error**: {size_error['message']}"

    # Extract file references from expanded prompt for tracking
    files_referenced = []
    if '@' in original_prompt:
        file_refs = re.findall(r'(?<![a-zA-Z0-9])@([^\s@]+)', original_prompt)
        files_referenced = [ref for ref in file_refs if '@' not in ref]  # Exclude emails

    # Handle conversation memory
    thread_id, is_new, thread = conversation_memory.get_or_create_thread(
        continuation_id=continuation_id,
        metadata={"tool": "ask_gemini", "model": model}
    )

    # Build conversation context if continuing
    conversation_context = ""
    if not is_new:
        conversation_context = conversation_memory.build_context(thread_id)

    # Add user turn to thread
    conversation_memory.add_turn(
        thread_id=thread_id,
        role="user",
        content=original_prompt,
        tool_name="ask_gemini",
        files=files_referenced
    )

    # Combine context with current prompt
    if conversation_context:
        full_prompt = f"{conversation_context}\n\n=== NEW REQUEST ===\n{prompt}"
    else:
        full_prompt = prompt

    model_id = MODELS.get(model, MODELS["pro"])

    # Build config
    config_params = {
        "temperature": temperature,
        "max_output_tokens": 8192
    }

    # Add thinking config if enabled
    if thinking_level != "off":
        thinking_params = {}

        # Include thought summaries if requested
        if include_thoughts:
            thinking_params["include_thoughts"] = True

        # For Gemini 3 Pro, use thinking_level
        if model == "pro":
            thinking_params["thinking_level"] = thinking_level
        else:
            # For Gemini 2.5 models, use thinking_budget
            # Map levels to budgets: low=1024, high=8192
            budget_map = {"low": 1024, "high": 8192}
            thinking_params["thinking_budget"] = budget_map.get(thinking_level, 1024)

        config_params["thinking_config"] = types.ThinkingConfig(**thinking_params)

    response = generate_with_fallback(
        model_id=model_id,
        contents=full_prompt,
        config=types.GenerateContentConfig(**config_params),
        operation="ask_gemini"
    )

    # Extract response text
    response_text = ""
    if include_thoughts and thinking_level != "off":
        result_parts = []
        thoughts_parts = []
        answer_parts = []

        for part in response.candidates[0].content.parts:
            if not hasattr(part, 'text') or not part.text:
                continue
            if hasattr(part, 'thought') and part.thought:
                thoughts_parts.append(part.text)
            else:
                answer_parts.append(part.text)

        if thoughts_parts:
            result_parts.append("**Thought Summary:**\n" + "\n".join(thoughts_parts))
        if answer_parts:
            result_parts.append("**Answer:**\n" + "\n".join(answer_parts))

        # Add token usage info
        if hasattr(response, 'usage_metadata'):
            meta = response.usage_metadata
            if hasattr(meta, 'thoughts_token_count'):
                result_parts.append(f"\n*Thinking tokens: {meta.thoughts_token_count}*")

        response_text = "\n\n".join(result_parts) if result_parts else response.text
    else:
        response_text = response.text

    # Add assistant turn to thread
    conversation_memory.add_turn(
        thread_id=thread_id,
        role="assistant",
        content=response_text,
        tool_name="ask_gemini",
        files=[]
    )

    # Index the conversation (v3.3.0)
    turn_count = len(conversation_memory.get_thread_history(thread_id))
    if is_new:
        # Generate title if not provided
        conv_title = title or conversation_memory.generate_title(original_prompt)
        conversation_memory.index_conversation(
            thread_id=thread_id,
            title=conv_title,
            mode="local",
            first_prompt=original_prompt[:200]  # Store first 200 chars
        )
    else:
        # Update activity
        conversation_memory.update_index_activity(thread_id)

    # Format output with continuation_id
    output = f"**GEMINI (ask_gemini):**\n\n{response_text}"

    # Add continuation info
    output += f"\n\n---\n*continuation_id: {thread_id}* (turn {turn_count}/{CONVERSATION_MAX_TURNS})"

    return output


def _ask_gemini_cloud(
    prompt: str,
    model: str = "pro",
    temperature: float = 0.5,
    thinking_level: str = "off",
    include_thoughts: bool = False,
    continuation_id: Optional[str] = None,
    title: Optional[str] = None
) -> str:
    """
    Cloud mode implementation using Interactions API.

    Conversations are stored server-side with 55-day retention (paid tier).
    """
    from ...services import client

    # Check if Interactions API is available
    if not hasattr(client, 'interactions'):
        return "**Error**: Cloud mode requires google-genai >= 1.55.0 with Interactions API support."

    # Expand @file references
    original_prompt = prompt
    prompt = expand_file_references(prompt)

    # Check prompt size
    size_error = check_prompt_size(prompt)
    if size_error:
        return f"**Error**: {size_error['message']}"

    try:
        # Build interaction request
        model_id = MODELS.get(model, MODELS["pro"])
        create_kwargs = {
            "input": prompt,
            "model": model_id,  # Use model (not agent) for standard queries
        }

        # Continue existing conversation if ID provided
        if continuation_id:
            # Strip "int_" prefix if present
            interaction_id = continuation_id.replace("int_", "")
            create_kwargs["previous_interaction_id"] = interaction_id

        # Create interaction
        interaction = client.interactions.create(**create_kwargs)

        # For non-background interactions, response is immediate
        # (handles new 'steps' schema in google-genai >= 2.0 and legacy outputs)
        from ..web.deep_research import extract_interaction_text
        response_text = extract_interaction_text(interaction)

        # Index the conversation locally for listing
        thread_id = f"int_{interaction.id}"
        conv_title = title or conversation_memory.generate_title(original_prompt)

        # Create a local record for the index (but history is on server)
        # Use the cloud thread_id so foreign key constraint is satisfied
        conversation_memory.create_thread(
            metadata={"cloud_id": interaction.id, "mode": "cloud"},
            thread_id=thread_id
        )
        conversation_memory.index_conversation(
            thread_id=thread_id,
            title=conv_title,
            mode="cloud",
            first_prompt=original_prompt[:200]
        )

        # Format output
        output = f"**GEMINI (ask_gemini - cloud):**\n\n{response_text}"
        output += f"\n\n---\n*continuation_id: {thread_id}* (cloud mode, 55-day retention)"

        return output

    except Exception as e:
        error_msg = str(e)
        if "interactions" in error_msg.lower():
            return f"**Error**: Interactions API not available. Ensure google-genai >= 1.55.0 is installed.\n\nDetails: {error_msg}"
        return f"**Error**: Cloud mode failed: {error_msg}"
