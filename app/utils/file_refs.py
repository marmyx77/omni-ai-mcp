"""
File reference expansion utilities.

Supports @file syntax for including file contents in prompts:
- @file.py - Include single file
- @src/main.py - Path with directories
- @*.py - Glob patterns (max 10 files)
- @src/**/*.ts - Recursive glob
- @. - Current directory listing
- @src - Directory listing
"""

import os
import re
import glob as glob_module
from typing import List, Tuple

from .line_numbers import add_line_numbers, should_add_line_numbers
from ..core.config import config
from ..core.security import validate_path, sensitive_reason, glob_root_allowed


# Limits
MAX_SINGLE_FILE_SIZE = 50 * 1024  # 50KB for single files
MAX_GLOB_FILE_SIZE = 10 * 1024    # 10KB per file for globs
MAX_GLOB_FILES = 10


def expand_file_references(text: str, base_dir: str = None) -> str:
    """
    Expand @file references in text to include file contents.

    Features:
    - Email addresses (user@example.com) are NOT expanded
    - Large files are truncated
    - Files wrapped in markdown code blocks
    - Code files get line numbers

    Args:
        text: Text containing @file references
        base_dir: Base directory for relative paths (default: the sandbox root)

    Returns:
        Text with file references replaced by contents
    """
    if not text or '@' not in text:
        return text

    base_dir = base_dir or config.sandbox_root

    # Pattern to match @references but not emails
    # Matches: @file.py, @src/main.py, @*.py, @., @src
    pattern = r'(?<![a-zA-Z0-9])@([a-zA-Z0-9_./*\-]+(?:/[a-zA-Z0-9_./*\-]*)*)'

    def replace_ref(match):
        ref = match.group(1)
        full_match = match.group(0)

        # Skip if looks like email (has @ before alphanumeric)
        start = match.start()
        if start > 0 and text[start - 1].isalnum():
            return full_match

        try:
            return _expand_single_ref(ref, base_dir)
        except Exception as e:
            return f"[Error expanding @{ref}: {e}]"

    return re.sub(pattern, replace_ref, text)


def _expand_single_ref(ref: str, base_dir: str) -> str:
    """Expand a single @reference (sandbox + credentials policy enforced)."""
    raw = os.path.join(base_dir, ref)

    # Glob patterns are checked match by match
    if '*' in ref:
        return _expand_glob(ref, base_dir)

    try:
        path = validate_path(raw)
    except ValueError as e:
        return f"[@{ref} not included: {e}]"

    # Check if it's a directory listing request
    if ref == '.' or os.path.isdir(path):
        return _list_directory(path, ref)

    # Single file
    if os.path.isfile(path):
        return _read_file(path, ref, MAX_SINGLE_FILE_SIZE)

    return f"[File not found: @{ref}]"


def _read_file(path: str, ref: str, max_size: int) -> str:
    """Read file and format with optional line numbers."""
    try:
        size = os.path.getsize(path)
        truncated = size > max_size

        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(max_size)

        if truncated:
            content += f"\n... [truncated, {size:,} bytes total]"

        # Add line numbers for code files
        if should_add_line_numbers(ref):
            content = add_line_numbers(content)

        # Detect language for syntax highlighting
        ext = os.path.splitext(ref)[1].lstrip('.')
        lang = ext if ext else ''

        return f"**{ref}:**\n```{lang}\n{content}\n```"

    except Exception as e:
        return f"[Error reading @{ref}: {e}]"


def _expand_glob(pattern: str, base_dir: str) -> str:
    """Expand glob pattern to multiple files."""
    full_pattern = os.path.join(base_dir, pattern)
    # Check the fixed prefix first: "@/**/*" must not walk the whole disk
    if not glob_root_allowed(full_pattern):
        return f"[@{pattern} not included: Access denied: path is outside allowed directory]"
    matches = sorted(glob_module.glob(full_pattern, recursive=True))

    # Keep only files the policy allows (inside the sandbox, not credentials), then limit
    allowed = []
    for m in matches:
        try:
            resolved = validate_path(m)
        except ValueError:
            continue
        if os.path.isfile(resolved):
            allowed.append(resolved)
    files = allowed[:MAX_GLOB_FILES]

    if not files:
        return f"[No files match: @{pattern}]"

    parts = []
    for file_path in files:
        rel_path = os.path.relpath(file_path, base_dir)
        parts.append(_read_file(file_path, rel_path, MAX_GLOB_FILE_SIZE))

    if len(matches) > MAX_GLOB_FILES:
        parts.append(f"\n... and {len(matches) - MAX_GLOB_FILES} more files")

    return '\n\n'.join(parts)


def _list_directory(path: str, ref: str) -> str:
    """List directory contents."""
    try:
        entries = sorted(e for e in os.listdir(path) if not sensitive_reason(os.path.join(path, e)))
        dirs = [e + '/' for e in entries if os.path.isdir(os.path.join(path, e))]
        files = [e for e in entries if os.path.isfile(os.path.join(path, e))]

        listing = '\n'.join(dirs + files)
        return f"**Directory @{ref}:**\n```\n{listing}\n```"

    except Exception as e:
        return f"[Error listing @{ref}: {e}]"


def extract_file_references(text: str) -> List[str]:
    """
    Extract all @file references from text.

    Args:
        text: Text to scan

    Returns:
        List of file references (without @)
    """
    if not text or '@' not in text:
        return []

    pattern = r'(?<![a-zA-Z0-9])@([a-zA-Z0-9_./*\-]+(?:/[a-zA-Z0-9_./*\-]*)*)'
    return re.findall(pattern, text)
