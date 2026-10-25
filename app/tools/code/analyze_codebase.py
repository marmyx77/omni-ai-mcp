"""
Analyze Codebase Tool

Large codebase analysis using Gemini's 1M token context window.
"""

import os
import glob as glob_module
from typing import List, Optional

from ...tools.registry import tool
from ...services import types, MODELS, client, conversation_memory, CONVERSATION_MAX_TURNS
from ...utils.tokens import estimate_tokens
from ...core import config
from ...core.security import validate_path, glob_root_allowed, SENSITIVE_DIR_NAMES


ANALYSIS_INSTRUCTIONS = {
    "architecture": """Focus on:
- Overall project structure and organization
- Design patterns used
- Component relationships and dependencies
- Entry points and data flow
- Architectural strengths and weaknesses""",
    "security": """Focus on:
- Potential security vulnerabilities (OWASP Top 10)
- Input validation and sanitization
- Authentication and authorization patterns
- Sensitive data handling
- Injection risks (SQL, command, XSS)""",
    "refactoring": """Focus on:
- Code duplication and DRY violations
- Long methods or classes that should be split
- Poor naming or unclear abstractions
- Tight coupling between components
- Opportunities for design pattern application""",
    "documentation": """Focus on:
- Missing or outdated documentation
- Functions/classes without docstrings
- Complex logic without explanatory comments
- API documentation completeness
- README and setup instructions""",
    "dependencies": """Focus on:
- External library usage and versions
- Circular dependencies
- Unused imports or dependencies
- Dependency injection patterns
- Package organization""",
    "general": """Provide a comprehensive analysis covering:
- Architecture and structure
- Code quality and maintainability
- Potential issues or risks
- Recommendations for improvement"""
}


ANALYZE_CODEBASE_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "description": "Analysis task: e.g., 'Explain the architecture', 'Find security issues', 'Identify refactoring opportunities', 'How does authentication work?'"},
        "files": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of file paths to analyze. Supports glob patterns: ['src/**/*.py', 'tests/*.py']. Max ~50 files recommended."
        },
        "analysis_type": {
            "type": "string",
            "enum": ["architecture", "security", "refactoring", "documentation", "dependencies", "general"],
            "description": "Type of analysis to focus on",
            "default": "general"
        },
        "model": {
            "type": "string",
            "enum": ["pro", "flash"],
            "description": "pro (default): Best for complex analysis. flash: Faster for simpler tasks.",
            "default": "pro"
        },
        "continuation_id": {
            "type": "string",
            "description": "Thread ID to continue iterative analysis. Gemini remembers previous findings."
        }
    },
    "required": ["prompt", "files"]
}


@tool(
    name="gemini_analyze_codebase",
    description="Analyze large codebases using Gemini's 1M token context window. Perfect for architecture analysis, cross-file review, refactoring planning, and understanding complex projects. Supports 50+ files at once.",
    input_schema=ANALYZE_CODEBASE_SCHEMA,
    tags=["code", "analysis"]
)
def analyze_codebase(
    prompt: str,
    files: List[str],
    analysis_type: str = "general",
    model: str = "pro",
    continuation_id: Optional[str] = None
) -> str:
    """
    Analyze large codebases using Gemini's 1M token context window.
    """
    # Expand glob patterns and collect files. Every path goes through the
    # sandbox + credentials policy: this content is sent to Google.
    all_files = []
    denied = 0

    def allowed(path: str) -> Optional[str]:
        nonlocal denied
        try:
            return validate_path(path)
        except ValueError:
            denied += 1
            return None

    for pattern in files:
        pattern = os.path.expanduser(pattern)
        if not os.path.isabs(pattern):
            pattern = os.path.join(config.sandbox_root, pattern)
        if '*' in pattern or '?' in pattern:
            if not glob_root_allowed(pattern):  # before globbing: "/**/*" must not walk the disk
                denied += 1
                continue
            for candidate in glob_module.glob(pattern, recursive=True):
                resolved = allowed(candidate)
                if resolved and os.path.isfile(resolved):
                    all_files.append(resolved)
            continue
        resolved = allowed(pattern)
        if not resolved:
            continue
        if os.path.isfile(resolved):
            all_files.append(resolved)
        elif os.path.isdir(resolved):
            # Recurse without following symlinks and without entering credential dirs
            for root, dirs, filenames in os.walk(resolved, followlinks=False):
                dirs[:] = [d for d in dirs if d.casefold() not in SENSITIVE_DIR_NAMES and d != ".git"]
                for filename in filenames:
                    file_resolved = allowed(os.path.join(root, filename))
                    if file_resolved:
                        all_files.append(file_resolved)

    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)
    all_files = unique_files

    if not all_files:
        if denied:
            return ("**Error**: No readable files: the paths are outside the sandbox (GEMINI_SANDBOX_ROOT) "
                    "or are protected credentials.")
        return "**Error**: No files found matching the provided patterns."

    # Read file contents
    file_contents = []
    total_chars = 0
    skipped_files = []
    max_file_size = 100_000  # 100KB per file max
    max_total_bytes = 5_000_000  # 5MB total limit to prevent memory exhaustion

    for filepath in all_files:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            # Skip very large files
            if len(content) > max_file_size:
                skipped_files.append(f"{filepath} (too large: {len(content):,} chars)")
                continue

            # Skip binary files
            if '\x00' in content[:1000]:
                skipped_files.append(f"{filepath} (binary file)")
                continue

            # Check total size limit
            if total_chars + len(content) > max_total_bytes:
                skipped_files.append(f"{filepath} (total size limit exceeded)")
                continue

            file_contents.append({
                "path": filepath,
                "content": content,
                "size": len(content)
            })
            total_chars += len(content)

        except Exception as e:
            skipped_files.append(f"{filepath} (error: {str(e)})")

    if not file_contents:
        return "**Error**: Could not read any files. Check paths and permissions."

    # Estimate tokens
    estimated_tokens = estimate_tokens(str(total_chars))

    instructions = ANALYSIS_INSTRUCTIONS.get(analysis_type, ANALYSIS_INSTRUCTIONS["general"])

    # Build the codebase content
    codebase_content = []
    for fc in file_contents:
        ext = os.path.splitext(fc["path"])[1].lstrip('.')
        codebase_content.append(f"### FILE: {fc['path']}\n```{ext}\n{fc['content']}\n```\n")

    codebase_text = "\n".join(codebase_content)

    # Handle conversation memory
    thread_id, is_new, thread = conversation_memory.get_or_create_thread(
        continuation_id=continuation_id,
        metadata={"tool": "analyze_codebase", "model": model, "analysis_type": analysis_type}
    )

    # Build conversation context if continuing
    conversation_context = ""
    if not is_new:
        conversation_context = conversation_memory.build_context(thread_id, max_chars=200000)  # Reserve space for code

    # Add user turn
    files_list = [fc["path"] for fc in file_contents]
    conversation_memory.add_turn(thread_id, "user", prompt, "analyze_codebase", files_list)

    # Build full prompt
    full_prompt = f"""# CODEBASE ANALYSIS REQUEST

## Analysis Type: {analysis_type.upper()}

{instructions}

## User Request
{prompt}

## Codebase Statistics
- Files analyzed: {len(file_contents)}
- Total size: {total_chars:,} characters (~{estimated_tokens:,} tokens)
{f"- Skipped files: {len(skipped_files)}" if skipped_files else ""}

## Codebase Contents

{codebase_text}

---
Provide a thorough analysis based on the above codebase and the user's request.
Structure your response clearly with sections and specific file references where applicable."""

    if conversation_context:
        full_prompt = f"{conversation_context}\n\n=== NEW ANALYSIS REQUEST ===\n{full_prompt}"

    # Check prompt size (use higher limit since Gemini has 1M context)
    if len(full_prompt) > 3_000_000:  # ~750K tokens, leave room for response
        return f"**Error**: Combined codebase too large ({len(full_prompt):,} chars). Try analyzing fewer files or specific directories."

    try:
        model_id = MODELS.get(model, MODELS["pro"])

        response = client.models.generate_content(
            model=model_id,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=config.max_output_tokens  # thinking + answer share it on Gemini 3+
            )
        )

        if not response.candidates:
            return "No response generated. The codebase may have been blocked by safety filters."

        result_text = response.text

        # Add assistant turn
        conversation_memory.add_turn(thread_id, "assistant", result_text, "analyze_codebase", [])
        turn_count = len(conversation_memory.get_thread_history(thread_id))

        # Build output
        output = f"""## Codebase Analysis Results

**Files Analyzed:** {len(file_contents)} ({total_chars:,} chars)
**Model:** {model_id}
**Analysis Type:** {analysis_type}
{f"**Skipped:** {len(skipped_files)} files" if skipped_files else ""}
{f"**Not sent (outside sandbox or credentials):** {denied} paths" if denied else ""}

---

{result_text}

---
*continuation_id: {thread_id}* (turn {turn_count}/{CONVERSATION_MAX_TURNS})
*Use continuation_id for follow-up questions about this codebase*"""

        return output

    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "429" in error_msg:
            # Try with flash model
            try:
                response = client.models.generate_content(
                    model=MODELS["flash"],
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=config.max_output_tokens
                    )
                )
                result_text = response.text
                conversation_memory.add_turn(thread_id, "assistant", result_text, "analyze_codebase", [])
                turn_count = len(conversation_memory.get_thread_history(thread_id))

                return f"""## Codebase Analysis Results (Flash Fallback)

**Files Analyzed:** {len(file_contents)} ({total_chars:,} chars)
**Model:** {MODELS["flash"]} (fallback due to quota)
**Analysis Type:** {analysis_type}

---

{result_text}

---
*continuation_id: {thread_id}* (turn {turn_count}/{CONVERSATION_MAX_TURNS})"""
            except:
                pass
        return f"Analysis error: {error_msg}"
