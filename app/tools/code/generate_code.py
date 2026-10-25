"""
Generate Code Tool

Structured code generation using Gemini.
"""

import os
import re
import html
from typing import Any, Dict, List, Optional

import defusedxml.ElementTree as ET

from ...tools.registry import tool
from ...services import types, MODELS, generate_with_fallback
from ...core.security import validate_path, write_protected_reason
from ...utils.file_refs import expand_file_references
from ...utils.tokens import check_prompt_size
from ...core import config


def sanitize_xml_content(content: str) -> str:
    """
    Sanitize content before XML parsing to prevent injection attacks.

    - Removes control characters (except newlines, tabs)
    - Strips null bytes
    - Limits excessive whitespace
    """
    # Remove null bytes and other control characters (keep \n, \r, \t)
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', content)

    # Limit consecutive blank lines to 3
    sanitized = re.sub(r'\n{4,}', '\n\n\n', sanitized)

    return sanitized


def parse_generated_code(xml_content: str) -> List[Dict[str, str]]:
    """
    Parse <FILE> blocks from generated code XML using defusedxml.

    Returns list of dicts with keys: action, path, content

    Security:
    - Uses defusedxml to prevent XXE and XML bomb attacks
    - Validates action types (whitelist: create, modify, delete)
    - Blocks path traversal attempts
    """
    # Sanitize input first
    xml_content = sanitize_xml_content(xml_content)

    files = []

    # Extract content between <GENERATED_CODE> tags if present
    gen_match = re.search(r'<GENERATED_CODE>(.*?)</GENERATED_CODE>', xml_content, re.DOTALL)
    if gen_match:
        xml_content = gen_match.group(1)

    # Wrap in root element for parsing (required for multiple FILE elements)
    wrapped = f"<root>{xml_content}</root>"

    try:
        # Use defusedxml for secure parsing (prevents XXE, billion laughs, etc.)
        tree = ET.fromstring(wrapped)
    except ET.ParseError:
        # Fallback: try regex for malformed XML (LLM output may not be perfect)
        return _parse_with_regex_fallback(xml_content)

    for file_elem in tree.findall('.//FILE'):
        action = file_elem.get('action', '').strip()
        path = file_elem.get('path', '').strip()
        content = file_elem.text or ''

        # Validate action (whitelist only)
        if action not in ('create', 'modify', 'delete'):
            continue

        # Sanitize path (prevent directory traversal)
        if '..' in path or path.startswith('/') or path.startswith('~'):
            continue

        # Skip empty paths
        if not path:
            continue

        files.append({
            "action": action,
            "path": path,
            "content": content.strip()
        })

    return files


def _parse_with_regex_fallback(xml_content: str) -> List[Dict[str, str]]:
    """
    Fallback regex parser for when XML is malformed.

    Used only when defusedxml fails to parse LLM output.
    Applies same security validations as the XML parser.
    """
    files = []

    # More restrictive regex pattern
    pattern = r'<FILE\s+action=["\'](\w+)["\']\s+path=["\']([^"\'<>]+)["\']>\s*(.*?)\s*</FILE>'
    matches = re.findall(pattern, xml_content, re.DOTALL)

    for action, path, content in matches:
        # Validate action (whitelist only)
        if action not in ('create', 'modify', 'delete'):
            continue

        # Sanitize path (prevent directory traversal)
        path = path.strip()
        if '..' in path or path.startswith('/') or path.startswith('~'):
            continue

        # Skip empty paths
        if not path:
            continue

        files.append({
            "action": action,
            "path": path,
            "content": content.strip()
        })

    return files


def save_generated_files(files: List[Dict[str, str]], output_dir: str) -> List[Dict[str, Any]]:
    """
    Save parsed files to disk.

    Returns list of results with status for each file.
    """
    results = []

    for file_info in files:
        action = file_info["action"]
        rel_path = file_info["path"]
        content = file_info["content"]

        try:
            # Construct full path
            full_path = os.path.join(output_dir, rel_path)

            # Validate path is within sandbox, and never an agent-instruction or hook file
            validated_path = validate_path(full_path)
            protected = write_protected_reason(validated_path)
            if protected:
                raise ValueError(f"Access denied: {protected}")

            # Create directories if needed
            dir_path = os.path.dirname(validated_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            # Write file
            with open(validated_path, 'w', encoding='utf-8') as f:
                f.write(content)

            results.append({
                "path": rel_path,
                "full_path": validated_path,
                "action": action,
                "status": "success",
                "lines": len(content.split('\n'))
            })

        except PermissionError as e:
            results.append({
                "path": rel_path,
                "action": action,
                "status": "error",
                "error": f"Permission denied: {str(e)}"
            })
        except Exception as e:
            results.append({
                "path": rel_path,
                "action": action,
                "status": "error",
                "error": str(e)
            })

    return results


STYLE_INSTRUCTIONS = {
    "production": """**Production Quality Code:**
- Full error handling with informative messages
- Complete type annotations/hints
- JSDoc/docstrings for public APIs
- Input validation where appropriate
- Follow established patterns from context files
- Include necessary imports""",

    "prototype": """**Prototype Quality Code:**
- Working code with basic error handling
- Key type annotations only
- Brief comments for complex logic
- Focus on functionality over polish""",

    "minimal": """**Minimal Code:**
- Bare essentials only
- No comments unless critical
- Minimal error handling
- Shortest working solution"""
}


GENERATE_CODE_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "What code to generate. Be specific about requirements, framework, and style. Example: 'Create a React login form with Tailwind CSS'"
        },
        "context_files": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Files to include as context. Supports @file syntax: ['@src/App.tsx', '@package.json', '@src/styles/*.css']. Gemini will match the existing code style."
        },
        "language": {
            "type": "string",
            "enum": ["auto", "typescript", "javascript", "python", "rust", "go", "java", "cpp", "csharp", "html", "css", "sql"],
            "description": "Target language. 'auto' detects from context files or prompt.",
            "default": "auto"
        },
        "style": {
            "type": "string",
            "enum": ["production", "prototype", "minimal"],
            "description": "Code style: 'production' (full error handling, types, docs), 'prototype' (working but basic), 'minimal' (bare essentials)",
            "default": "production"
        },
        "model": {
            "type": "string",
            "enum": ["pro", "flash"],
            "description": "pro (default): Best quality code. flash: Faster for simple tasks.",
            "default": "pro"
        },
        "output_dir": {
            "type": "string",
            "description": "Optional directory to save generated files. If specified, files are saved automatically and a summary is returned. If not specified, returns XML for Claude to apply manually."
        },
        "dry_run": {
            "type": "boolean",
            "description": "If true, shows what files would be created/modified without actually writing them. Useful for preview before applying changes.",
            "default": False
        }
    },
    "required": ["prompt"]
}


@tool(
    name="gemini_generate_code",
    description="Generate code using Gemini. Returns structured output with file operations (create/modify) that can be applied by Claude. Best for UI components, boilerplate, and tasks where Gemini excels. Supports @file references for context.",
    input_schema=GENERATE_CODE_SCHEMA,
    tags=["code", "generation"]
)
def generate_code(
    prompt: str,
    context_files: Optional[List[str]] = None,
    language: str = "auto",
    style: str = "production",
    model: str = "pro",
    output_dir: Optional[str] = None,
    dry_run: bool = False
) -> str:
    """
    Generate code using Gemini with structured output for Claude to apply.
    """
    # Build context from files
    context_content = ""
    if context_files:
        context_parts = []
        for file_ref in context_files:
            # Ensure @ prefix for expand_file_references
            if not file_ref.startswith('@'):
                file_ref = '@' + file_ref
            expanded = expand_file_references(file_ref)
            if expanded != file_ref:  # File was found and expanded
                context_parts.append(expanded)
        if context_parts:
            context_content = "\n\n".join(context_parts)

    # Check prompt size
    combined = prompt + context_content
    size_error = check_prompt_size(combined)
    if size_error:
        return f"**Error**: {size_error['message']}"

    style_instruction = STYLE_INSTRUCTIONS.get(style, STYLE_INSTRUCTIONS["production"])

    # Language detection hint
    lang_hint = ""
    if language != "auto":
        lang_hint = f"\n**Target Language:** {language}"

    # Build the prompt
    full_prompt = f"""# CODE GENERATION REQUEST

## Task
{prompt}
{lang_hint}

{style_instruction}

## Output Format
You MUST return code in this EXACT XML format. This format allows automated processing.

```xml
<GENERATED_CODE>
<FILE action="create" path="relative/path/to/newfile.ext">
// Complete file contents here
// Include ALL necessary code - imports, types, implementation
</FILE>

<FILE action="modify" path="relative/path/to/existing.ext">
// Show the COMPLETE modified file
// Or use comments to indicate unchanged sections:
// ... existing imports ...

// NEW OR MODIFIED CODE HERE

// ... rest of file unchanged ...
</FILE>
</GENERATED_CODE>
```

## Rules
1. Use action="create" for new files
2. Use action="modify" for changes to existing files
3. Paths should be relative to project root
4. Include complete, runnable code - no placeholders like "// add your code here"
5. Match the code style from context files if provided
6. Each FILE block must contain the full file OR clearly marked sections

## Need More Context?
If you need to see additional files before generating code, respond with ONLY:
```json
{{"need_files": ["path/to/file1.ts", "path/to/file2.py"]}}
```
Do NOT include any other text. I will provide the requested files and ask again.

{f'## Context Files (match this style){chr(10)}{context_content}' if context_content else ''}

## Generate Code Now
Return ONLY the <GENERATED_CODE> block with the requested implementation.
If you need more files first, return ONLY the JSON need_files request.
"""

    model_id = MODELS.get(model, MODELS["pro"])

    try:
        response = generate_with_fallback(
            model_id=model_id,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=config.max_output_tokens  # thinking + answer share it on Gemini 3+
            ),
            operation="generate_code"
        )

        result = response.text

        # JSON More Info Protocol - detect need_files requests
        need_files_match = re.search(r'\{\s*"need_files"\s*:\s*\[(.*?)\]\s*\}', result, re.DOTALL)
        if need_files_match and "<GENERATED_CODE>" not in result:
            # Gemini is requesting more files
            try:
                files_str = need_files_match.group(1)
                requested_files = re.findall(r'"([^"]+)"', files_str)

                if requested_files:
                    additional_context = []
                    for file_path in requested_files[:5]:  # Limit to 5 files
                        file_ref = f"@{file_path}" if not file_path.startswith('@') else file_path
                        expanded = expand_file_references(file_ref)
                        if expanded != file_ref:
                            additional_context.append(expanded)

                    if additional_context:
                        new_context = context_content + "\n\n" + "\n\n".join(additional_context)

                        retry_prompt = f"""# CODE GENERATION REQUEST (RETRY WITH ADDITIONAL FILES)

## Task
{prompt}
{lang_hint}

{style_instruction}

## Output Format
You MUST return code in this EXACT XML format:
```xml
<GENERATED_CODE>
<FILE action="create" path="relative/path/to/file.ext">
// Complete file contents
</FILE>
</GENERATED_CODE>
```

## Context Files (match this style)
{new_context}

## Generate Code Now
You now have the additional files you requested. Return ONLY the <GENERATED_CODE> block.
"""
                        retry_response = generate_with_fallback(
                            model_id=model_id,
                            contents=retry_prompt,
                            config=types.GenerateContentConfig(
                                max_output_tokens=config.max_output_tokens
                            ),
                            operation="generate_code_retry"
                        )
                        result = retry_response.text

            except Exception:
                pass

        # Validate output format
        if "<GENERATED_CODE>" not in result:
            result = f"""<GENERATED_CODE>
<FILE action="create" path="generated_code.txt">
{result}
</FILE>
</GENERATED_CODE>

**Note:** Gemini didn't return structured output. Review and apply manually."""

        # Auto-save if output_dir is specified (or dry-run preview)
        if output_dir or dry_run:
            try:
                target_dir = output_dir or config.sandbox_root
                validated_dir = validate_path(target_dir)

                files = parse_generated_code(result)
                if not files:
                    return f"""## Code Generation Result

**Style:** {style}
**Language:** {language}
**Model:** {model_id}
**Mode:** {'DRY RUN (preview only)' if dry_run else 'auto-save'}

**Warning:** No <FILE> blocks found in output. Raw result:

{result}"""

                # DRY RUN - show preview without saving
                if dry_run:
                    summary_lines = [
                        "## Code Generation Preview (DRY RUN)",
                        "",
                        f"**Style:** {style}",
                        f"**Language:** {language}",
                        f"**Model:** {model_id}",
                        f"**Target Directory:** {validated_dir}",
                        "",
                        "### Files that would be created/modified:",
                        ""
                    ]

                    for f in files:
                        action_emoji = "➕" if f["action"] == "create" else "✏️" if f["action"] == "modify" else "🗑️"
                        lines = len(f["content"].split('\n'))
                        full_path = os.path.join(validated_dir, f["path"])
                        exists = os.path.exists(full_path)
                        status = "(exists)" if exists else "(new)"

                        summary_lines.append(f"{action_emoji} **{f['action']}** `{f['path']}` - {lines} lines {status}")

                    summary_lines.extend([
                        "",
                        "### Preview of generated code:",
                        ""
                    ])

                    for f in files:
                        ext = os.path.splitext(f["path"])[1].lstrip('.') or 'txt'
                        preview = f["content"][:2000]
                        if len(f["content"]) > 2000:
                            preview += f"\n\n... ({len(f['content']) - 2000} more chars)"
                        summary_lines.append(f"#### {f['path']}")
                        summary_lines.append(f"```{ext}")
                        summary_lines.append(preview)
                        summary_lines.append("```")
                        summary_lines.append("")

                    summary_lines.extend([
                        "---",
                        "**This was a dry run. No files were written.**",
                        "To apply changes, run again without `dry_run=True` or with `output_dir` specified."
                    ])

                    return "\n".join(summary_lines)

                # ACTUAL SAVE
                if not os.path.exists(validated_dir):
                    os.makedirs(validated_dir, exist_ok=True)

                save_results = save_generated_files(files, validated_dir)

                success_count = sum(1 for r in save_results if r["status"] == "success")
                error_count = sum(1 for r in save_results if r["status"] == "error")

                summary_lines = [
                    "## Code Generation Result",
                    "",
                    f"**Style:** {style}",
                    f"**Language:** {language}",
                    f"**Model:** {model_id}",
                    f"**Output Directory:** {validated_dir}",
                    "",
                    f"### Files Saved ({success_count} success, {error_count} errors)",
                    ""
                ]

                for r in save_results:
                    if r["status"] == "success":
                        summary_lines.append(f"- **{r['action']}** `{r['path']}` ({r['lines']} lines)")
                    else:
                        summary_lines.append(f"- **{r['action']}** `{r['path']}` - ERROR: {r['error']}")

                summary_lines.extend(["", "---", "Files have been saved. Review them to verify correctness."])

                return "\n".join(summary_lines)

            except PermissionError as e:
                return f"**Error:** Cannot write to output directory: {str(e)}"
            except Exception as e:
                return f"**Error:** Failed to save files: {str(e)}"

        # Default: return XML for Claude to apply
        return f"""## Code Generation Result

**Style:** {style}
**Language:** {language}
**Model:** {model_id}

{result}

---
**Instructions for Claude:** Parse the <GENERATED_CODE> block and apply file operations using Write/Edit tools.
- action="create": Use Write tool to create new file
- action="modify": Use Edit tool to modify existing file"""

    except Exception as e:
        return f"Code generation error: {str(e)}"
