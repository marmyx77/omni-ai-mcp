"""
Security utilities: path validation, secrets sanitization, safe file writing.
"""

import os
import re
import shutil
import hashlib
import tempfile
import signal
import stat
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

# File locking - cross-platform using filelock
try:
    from filelock import FileLock as FileLocker, Timeout as FileLockTimeout
    HAS_FILELOCK = True
except ImportError:
    # Fallback to fcntl on Unix if filelock not installed
    HAS_FILELOCK = False
    try:
        import fcntl
        HAS_FCNTL = True
    except ImportError:
        HAS_FCNTL = False

from .config import config


# =============================================================================
# FILE LOCKING (Race condition prevention)
# =============================================================================

class FileLockError(Exception):
    """Raised when file lock cannot be acquired."""
    pass


@contextmanager
def file_lock(file_path: str, timeout: float = 5.0, exclusive: bool = True):
    """
    Context manager for file locking to prevent race conditions.

    Uses filelock library for cross-platform support (Windows, macOS, Linux).
    Falls back to fcntl on Unix if filelock not installed.

    Args:
        file_path: Path to lock (creates .lock file alongside)
        timeout: Maximum seconds to wait for lock
        exclusive: If True, exclusive lock (write). If False, shared lock (read).

    Raises:
        FileLockError: If lock cannot be acquired within timeout

    Example:
        with file_lock('/path/to/file.txt'):
            # File is locked, safe to write
            write_to_file(...)
    """
    lock_path = f"{file_path}.lock"

    # Use filelock library if available (cross-platform)
    if HAS_FILELOCK:
        # Ensure parent directory exists for lock file
        lock_dir = os.path.dirname(lock_path)
        if lock_dir and not os.path.exists(lock_dir):
            os.makedirs(lock_dir, exist_ok=True)

        locker = FileLocker(lock_path)
        try:
            locker.acquire(timeout=timeout)
            yield
        except FileLockTimeout:
            raise FileLockError(
                f"Could not acquire lock on {file_path} within {timeout}s"
            )
        finally:
            if locker.is_locked:
                locker.release()
        return

    # Fallback to fcntl on Unix
    if not HAS_FCNTL:
        # No locking available - yield and hope for the best
        yield
        return

    lock_fd = None

    try:
        # Ensure parent directory exists for lock file
        lock_dir = os.path.dirname(lock_path)
        if lock_dir and not os.path.exists(lock_dir):
            os.makedirs(lock_dir, exist_ok=True)

        # Create lock file
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)

        # Try to acquire lock with timeout
        import time
        start_time = time.time()
        lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH

        while True:
            try:
                fcntl.flock(lock_fd, lock_type | fcntl.LOCK_NB)
                break  # Lock acquired
            except (IOError, OSError):
                if time.time() - start_time > timeout:
                    raise FileLockError(
                        f"Could not acquire lock on {file_path} within {timeout}s"
                    )
                time.sleep(0.1)  # Wait and retry

        yield

    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            except (IOError, OSError):
                pass
            # Clean up lock file (best effort)
            try:
                os.unlink(lock_path)
            except (IOError, OSError):
                pass


# =============================================================================
# REGEX TIMEOUT PROTECTION (ReDoS mitigation)
# =============================================================================

class RegexTimeoutError(Exception):
    """Raised when regex execution exceeds timeout."""
    pass


@contextmanager
def regex_timeout(seconds: float = 1.0):
    """
    Context manager to limit regex execution time (Unix only).

    Prevents ReDoS attacks by aborting long-running regex operations.
    On Windows/non-Unix platforms, this is a no-op (no timeout enforced).
    """
    def timeout_handler(signum, frame):
        raise RegexTimeoutError(f"Regex execution exceeded {seconds}s timeout")

    # Only set alarm on Unix-like systems
    if hasattr(signal, 'SIGALRM'):
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Windows/non-Unix: no timeout protection
        yield


# =============================================================================
# BINARY FILE DETECTION
# =============================================================================

# Binary file signatures (magic bytes)
BINARY_SIGNATURES = [
    b'\x89PNG',      # PNG
    b'\xff\xd8\xff',  # JPEG
    b'GIF8',         # GIF
    b'RIFF',         # WAV, AVI
    b'%PDF',         # PDF
    b'PK\x03\x04',   # ZIP, DOCX, XLSX, etc.
    b'\x7fELF',      # ELF executable
    b'MZ',           # Windows executable
    b'\x00\x00\x01\x00',  # ICO
    b'\x1f\x8b',     # GZIP
    b'BZh',          # BZIP2
    b'\xfd7zXZ',     # XZ
    b'Rar!\x1a\x07', # RAR
]

# File extensions that are always binary
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp', '.tiff', '.tif',
    '.mp3', '.mp4', '.wav', '.avi', '.mov', '.mkv', '.flac', '.ogg', '.webm',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z',
    '.exe', '.dll', '.so', '.dylib', '.bin', '.dat',
    '.pyc', '.pyo', '.class', '.o', '.obj',
    '.db', '.sqlite', '.sqlite3',
    '.ttf', '.otf', '.woff', '.woff2', '.eot',
}


def is_binary_file(file_path: str, check_content: bool = True) -> bool:
    """
    Check if a file is binary (not text).

    Uses a combination of:
    1. File extension check (fast)
    2. Magic byte signature detection (reliable)
    3. Null byte presence in first 8KB (fallback)

    Args:
        file_path: Path to check
        check_content: If True, also check file content (slower but more accurate)

    Returns:
        True if file appears to be binary, False if text
    """
    path = Path(file_path)

    # Check extension first (fast path)
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True

    if not check_content:
        return False

    # Check file content
    try:
        with open(file_path, 'rb') as f:
            # Read first 8KB for analysis
            chunk = f.read(8192)

            if not chunk:
                return False  # Empty file is text

            # Check for magic byte signatures
            for sig in BINARY_SIGNATURES:
                if chunk.startswith(sig):
                    return True

            # Check for null bytes (binary indicator)
            if b'\x00' in chunk:
                return True

            # Check for high ratio of non-printable characters
            # Text files should be mostly printable ASCII or valid UTF-8
            try:
                chunk.decode('utf-8')
                # Valid UTF-8, likely text
                return False
            except UnicodeDecodeError:
                # Not valid UTF-8, check for high non-ASCII ratio
                non_text = sum(1 for b in chunk if b < 32 and b not in (9, 10, 13))
                if non_text / len(chunk) > 0.1:  # >10% control chars
                    return True

    except (IOError, OSError):
        pass  # Can't read file, assume text

    return False


# =============================================================================
# PATH VALIDATION
# =============================================================================

# Credentials and secrets a tool must never read or write, whatever the sandbox
# says (the server is driven by an LLM that prompt injection can steer).
SENSITIVE_DIR_NAMES = frozenset({
    ".ssh", ".gnupg", ".aws", ".azure", ".kube", ".password-store", ".gcloud",
    "keychains", ".1password", ".docker", ".terraform.d", ".vault-token", ".m2",
})
SENSITIVE_FILE_NAMES = frozenset({
    ".claude.json", ".netrc", ".npmrc", ".pypirc", ".git-credentials", ".pgpass",
    ".boto", ".s3cfg", "credentials", "credentials.json", "credentials.db", "credentials.toml",
    "secrets.json", "secrets.yaml", "secrets.yml", "service-account.json",
    ".bash_history", ".zsh_history", ".python_history", ".psql_history", ".mysql_history",
})
SENSITIVE_FILE_PREFIXES = ("id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", ".env")
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".kdbx", ".keychain", ".keychain-db", ".ppk", ".asc", ".gpg")
SENSITIVE_HOME_SUBPATHS = (
    ".claude", ".config/gcloud", ".config/gh", ".config/op", ".config/rclone",
    ".local/share/keyrings", "library/application support", "library/cookies",
)

# Files and folders a tool may READ inside the workspace but never WRITE: agent
# instructions and editor/VCS hooks would turn a prompt-injected output_path into
# persistent prompt injection or code execution (.git/hooks, .vscode/tasks.json).
WRITE_PROTECTED_DIR_NAMES = frozenset({".git", ".claude", ".vscode", ".idea", ".husky", ".cursor"})
WRITE_PROTECTED_FILE_NAMES = frozenset({"claude.md", "agents.md", "gemini.md", ".mcp.json", ".cursorrules"})


def _fold(path: str) -> str:
    """Case-folded path: macOS and Windows file systems ignore case (~/.SSH == ~/.ssh)."""
    return os.path.normcase(path).casefold()


def _is_within(path: str, root: str) -> bool:
    """True if path equals root or lies under it (case-folded, works for root = '/')."""
    path, root = _fold(path), _fold(root)
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def sensitive_reason(resolved_path: str) -> Optional[str]:
    """Why a resolved path is off-limits (credentials, keys, secrets), or None."""
    path = Path(resolved_path)
    parts = {part.casefold() for part in path.parts}
    hit = parts & SENSITIVE_DIR_NAMES
    if hit:
        return f"inside a credentials directory ({sorted(hit)[0]})"
    name = path.name
    lower = name.casefold()
    if lower in SENSITIVE_FILE_NAMES:
        return f"credentials file ({name})"
    if lower.startswith(SENSITIVE_FILE_PREFIXES) and not lower.endswith((".example", ".sample", ".template")):
        return f"key or environment file ({name})"
    if lower.endswith(SENSITIVE_SUFFIXES):
        return f"key/certificate file ({name})"
    home = os.path.realpath(os.path.expanduser("~"))
    for sub in SENSITIVE_HOME_SUBPATHS:
        if _is_within(resolved_path, os.path.join(home, sub)):
            return f"private application data (~/{sub})"
    return None


def write_protected_reason(resolved_path: str) -> Optional[str]:
    """Why a tool must not WRITE this path (agent instructions, VCS/editor hooks), or None."""
    path = Path(resolved_path)
    hit = {part.casefold() for part in path.parts[:-1]} & WRITE_PROTECTED_DIR_NAMES
    if hit:
        return f"files inside {sorted(hit)[0]}/ are never written by tools"
    if path.name.casefold() in WRITE_PROTECTED_FILE_NAMES:
        return f"{path.name} is never written by tools"
    return None


def output_base_dir() -> str:
    """Private folder for outputs written without output_path (GEMINI_OUTPUT_DIR overrides)."""
    if config.output_dir:
        return os.path.realpath(config.output_dir)
    owner = os.getuid() if hasattr(os, "getuid") else "user"
    return os.path.realpath(os.path.join(tempfile.gettempdir(), f"omni-ai-mcp-{owner}"))


def validate_path(file_path: str, allow_outside_sandbox: bool = False) -> str:
    """
    Validate and resolve a file path, ensuring it's within the sandbox.

    Security features:
    - Prevents directory traversal attacks (../)
    - Resolves symlinks to check actual destination
    - Refuses credentials and keys, even with the sandbox disabled
    - Blocks access outside SANDBOX_ROOT (unless disabled); the private output
      folder is also allowed, so generated files can feed other tools

    Args:
        file_path: The path to validate (absolute or relative)
        allow_outside_sandbox: If True, skip sandbox check (for system files)

    Returns:
        Resolved absolute path

    Raises:
        ValueError: If path is outside sandbox or invalid
    """
    file_path = os.path.expanduser(str(file_path))

    # Convert to absolute path (relative paths are relative to the sandbox root)
    if not os.path.isabs(file_path):
        file_path = os.path.join(config.sandbox_root, file_path)

    # Resolve any symlinks and normalize
    try:
        resolved_path = os.path.realpath(file_path)
    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid path: {e}")

    # Credentials are refused even with the sandbox disabled
    reason = sensitive_reason(resolved_path)
    if reason:
        raise ValueError(f"Access denied: {reason} is protected")

    if not config.sandbox_enabled or allow_outside_sandbox:
        return resolved_path

    if _is_within(resolved_path, os.path.realpath(config.sandbox_root)):
        return resolved_path
    if _is_within(resolved_path, output_base_dir()) and _owned_private_dir(output_base_dir()):
        return resolved_path
    # SECURITY: Don't expose full paths in error messages
    raise ValueError(
        "Access denied: path is outside allowed directory "
        "(set GEMINI_SANDBOX_ROOT to the folder the tools may use)"
    )


def glob_root_allowed(pattern: str) -> bool:
    """True if the fixed (wildcard-free) prefix of a glob is an allowed path.

    Checked BEFORE globbing, so `/**/*` never walks the whole disk.
    """
    fixed = []
    for part in Path(pattern).parts:
        if any(ch in part for ch in "*?["):
            break
        fixed.append(part)
    prefix = os.path.join(*fixed) if fixed else config.sandbox_root
    try:
        validate_path(prefix)
        return True
    except ValueError:
        return False


def safe_input_path(file_path: str, allowed_extensions: Optional[set] = None, must_exist: bool = True) -> str:
    """
    Validate a path a tool will READ (and possibly upload to Google).

    Sandbox + credentials policy (validate_path), optional extension allowlist,
    existence check. Raises ValueError with a user-facing message.
    """
    if not file_path or not str(file_path).strip():
        raise ValueError("empty file path")
    resolved = validate_path(file_path)
    if allowed_extensions is not None:
        ext = os.path.splitext(resolved)[1].lower()
        if ext not in allowed_extensions:
            raise ValueError(
                f"unsupported file type '{ext or '(none)'}'; allowed: {', '.join(sorted(allowed_extensions))}"
            )
    if must_exist and not os.path.exists(resolved):
        raise ValueError(f"file not found: {os.path.basename(resolved)}")
    return resolved


def safe_output_path(file_path: str, allowed_extensions: set) -> str:
    """
    Validate a path a tool will WRITE: sandbox + credentials policy, mandatory
    extension allowlist (so outputs can never become ~/.zshrc, authorized_keys,
    LaunchAgents plists...), no agent-instruction or hook files (CLAUDE.md,
    .claude/, .git/, .vscode/), no writing through symlinks, parent created
    inside the sandbox. Raises ValueError.
    """
    if not file_path or not str(file_path).strip():
        raise ValueError("empty output path")
    expanded = os.path.expanduser(str(file_path))
    if not os.path.isabs(expanded):
        expanded = os.path.join(config.sandbox_root, expanded)
    if os.path.islink(expanded):
        raise ValueError("refusing to write through a symbolic link")
    resolved = validate_path(expanded)
    protected = write_protected_reason(resolved)
    if protected:
        raise ValueError(f"Access denied: {protected}")
    ext = os.path.splitext(resolved)[1].lower()
    if ext not in allowed_extensions:
        raise ValueError(
            f"output must end with {', '.join(sorted(allowed_extensions))} (got '{ext or '(none)'}')"
        )
    parent = os.path.dirname(resolved)
    validate_path(parent)
    os.makedirs(parent, exist_ok=True)
    return resolved


def _owned_private_dir(path: str) -> bool:
    """True if path is a directory owned by this user (a shared /tmp can hold a planted one)."""
    try:
        info = os.stat(path)
    except OSError:
        return False
    return not hasattr(os, "getuid") or info.st_uid == os.getuid()


def default_output_path(stem: str, extension: str) -> str:
    """
    Unique, unpredictable output file in a private (0700) folder, for tools
    called without output_path. GEMINI_OUTPUT_DIR overrides the folder.
    """
    base = output_base_dir()
    os.makedirs(base, mode=0o700, exist_ok=True)
    if not _owned_private_dir(base):
        raise ValueError(f"output folder {base} belongs to another user: set GEMINI_OUTPUT_DIR")
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass
    fd, path = tempfile.mkstemp(prefix=f"{stem}_", suffix=extension, dir=base)
    os.close(fd)
    return path


def check_file_size(file_path: str, max_size: int = None) -> Optional[Dict[str, str]]:
    """
    Check if file size is within limits BEFORE reading.

    Returns:
        Error dict if too large, None if OK.
    """
    max_size = max_size or config.max_file_size_bytes

    try:
        size = os.path.getsize(file_path)
        if size > max_size:
            return {
                "status": "error",
                "message": f"File too large: {size:,} bytes (max {max_size:,})"
            }
    except OSError:
        pass  # File doesn't exist, let caller handle

    return None


def secure_read_file(
    file_path: str,
    max_size: int = None,
    allow_binary: bool = False
) -> str:
    """
    Read file with path validation, size check, and binary detection.

    SECURITY:
    - Uses fstat() on open file descriptor to prevent TOCTOU race conditions
    - Rejects binary files by default to prevent crashes and garbled output
    - The file size is checked AFTER opening, making it atomic

    Args:
        file_path: Path to read
        max_size: Maximum file size in bytes
        allow_binary: If True, attempt to read binary files (may fail)

    Returns:
        File contents

    Raises:
        ValueError: If path invalid, file too large, or file is binary
    """
    validated_path = validate_path(file_path)
    max_size = max_size or config.max_file_size_bytes

    # Check for binary file before attempting to read as text
    if not allow_binary and is_binary_file(validated_path):
        raise ValueError(
            f"Cannot read binary file as text. "
            f"Use a specialized tool for this file type."
        )

    try:
        with open(validated_path, 'r', encoding='utf-8') as f:
            # SECURITY: Check size on open file descriptor (atomic, prevents TOCTOU)
            file_size = os.fstat(f.fileno()).st_size
            if file_size > max_size:
                raise ValueError(f"File too large: {file_size:,} bytes (max {max_size:,})")
            return f.read()
    except UnicodeDecodeError:
        raise ValueError(
            f"Cannot decode file as UTF-8 text. "
            f"File may be binary or use a different encoding."
        )
    except OSError as e:
        raise ValueError(f"Error reading file: {e}")


# =============================================================================
# SECRETS SANITIZER
# =============================================================================

class SecretsSanitizer:
    """
    Detect and mask sensitive data in logs and outputs.

    Patterns detected:
    - API keys (Google, AWS, GitHub, generic)
    - JWT tokens
    - Bearer tokens
    - Private keys
    - Passwords in URLs
    - Connection strings

    Security:
    - Regex patterns are designed to avoid catastrophic backtracking (ReDoS)
    - Timeout protection on Unix platforms for defense in depth
    """

    # SECURITY: Patterns are designed to be ReDoS-safe
    # - Avoid nested quantifiers like (a+)+
    # - Use possessive quantifiers where possible (simulated via atomic groups)
    # - Limit repetition ranges explicitly
    PATTERNS = [
        # JWT tokens (three base64-encoded parts) - fixed length segments
        (r'eyJ[a-zA-Z0-9\-_]{10,500}\.eyJ[a-zA-Z0-9\-_]{10,500}\.[a-zA-Z0-9\-_]{10,500}', 'JWT_TOKEN'),
        # Private keys (PEM format headers)
        (r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', 'PRIVATE_KEY'),
        # Google/Gemini API keys (AIza format) - exact length
        (r'AIza[0-9A-Za-z\-_]{35}', 'GOOGLE_API_KEY'),
        # AWS Access Keys (AKIA format) - exact length
        (r'AKIA[0-9A-Z]{16}', 'AWS_ACCESS_KEY'),
        # GitHub tokens (specific prefixes) - exact length
        (r'ghp_[a-zA-Z0-9]{36}', 'GITHUB_PAT'),
        (r'gho_[a-zA-Z0-9]{36}', 'GITHUB_OAUTH'),
        (r'ghu_[a-zA-Z0-9]{36}', 'GITHUB_USER_TOKEN'),
        (r'ghs_[a-zA-Z0-9]{36}', 'GITHUB_SERVER_TOKEN'),
        (r'ghr_[a-zA-Z0-9]{36}', 'GITHUB_REFRESH_TOKEN'),
        # Anthropic API keys - bounded length
        (r'sk-ant-[a-zA-Z0-9\-_]{40,100}', 'ANTHROPIC_API_KEY'),
        # OpenRouter API keys - bounded length (sk-or-v1-<64 hex>)
        (r'sk-or-v1-[a-fA-F0-9]{32,128}', 'OPENROUTER_API_KEY'),
        # OpenAI API keys (legacy and project keys) - bounded length
        (r'sk-proj-[a-zA-Z0-9\-_]{20,200}', 'OPENAI_API_KEY'),
        (r'sk-[a-zA-Z0-9]{48}', 'OPENAI_API_KEY'),
        # Slack tokens - bounded length
        (r'xox[baprs]-[0-9a-zA-Z\-]{10,50}', 'SLACK_TOKEN'),
        # Bearer tokens - bounded length
        (r'(?i)bearer\s+[a-zA-Z0-9\-_.]{10,200}', 'BEARER_TOKEN'),
        # Password in URLs (http://user:pass@host)
        # SECURITY FIX: Use possessive-like pattern with bounded length to prevent ReDoS
        # Old vulnerable pattern: r'(?i)://[^:]+:([^@]{3,})@'
        (r'(?i)://[^:@]{1,100}:([^@]{3,100})@', 'URL_PASSWORD'),
        # AWS Secret Keys (generic 40-char base64) - exact length
        (r'(?i)(?:aws_secret|secret_key)["\s:=]+["\']?([A-Za-z0-9/+=]{40})["\']?', 'AWS_SECRET_KEY'),
        # Generic API key patterns - bounded length
        (r'(?i)(?:api[_-]?key|apikey)["\s:=]+["\']?([a-zA-Z0-9\-_]{20,100})["\']?', 'API_KEY'),
        # Generic secrets - bounded length
        (r'(?i)(?:password|passwd|secret)["\s:=]+["\']?([^\s"\']{8,100})["\']?', 'GENERIC_SECRET'),
    ]

    # Timeout for regex operations (seconds)
    REGEX_TIMEOUT = 0.5

    def __init__(self):
        """Compile regex patterns for efficiency."""
        self.compiled_patterns = [
            (re.compile(pattern), name)
            for pattern, name in self.PATTERNS
        ]

    def sanitize(self, text: str) -> str:
        """
        Replace all detected secrets with masked versions.

        Args:
            text: Input text potentially containing secrets

        Returns:
            Text with secrets replaced by [REDACTED_TYPE]

        Note:
            Uses timeout protection on Unix to prevent ReDoS attacks.
            On timeout, returns original text (fail-open for availability).
        """
        if not text:
            return text

        # Limit input size to prevent DoS
        if len(text) > 1_000_000:  # 1MB max
            text = text[:1_000_000]

        result = text
        try:
            with regex_timeout(self.REGEX_TIMEOUT):
                for pattern, name in self.compiled_patterns:
                    result = pattern.sub(f'[REDACTED_{name}]', result)
        except RegexTimeoutError:
            # Fail-open: return original text if regex times out
            # This prioritizes availability over perfect sanitization
            pass
        return result

    def detect(self, text: str) -> List[str]:
        """
        Return list of detected secret types (without values).
        """
        if not text:
            return []

        # Limit input size
        if len(text) > 1_000_000:
            text = text[:1_000_000]

        detected = []
        try:
            with regex_timeout(self.REGEX_TIMEOUT):
                for pattern, name in self.compiled_patterns:
                    if pattern.search(text):
                        detected.append(name)
        except RegexTimeoutError:
            pass
        return detected

    def has_secrets(self, text: str) -> bool:
        """Quick check if text contains any secrets."""
        if not text:
            return False

        # Limit input size
        if len(text) > 1_000_000:
            text = text[:1_000_000]

        try:
            with regex_timeout(self.REGEX_TIMEOUT):
                for pattern, _ in self.compiled_patterns:
                    if pattern.search(text):
                        return True
        except RegexTimeoutError:
            pass
        return False


# Global instance
secrets_sanitizer = SecretsSanitizer()


# =============================================================================
# SAFE FILE WRITER
# =============================================================================

@dataclass
class WriteResult:
    """Result of a safe write operation."""
    success: bool
    path: str
    backup_path: Optional[str]
    content_hash: str
    error: Optional[str] = None
    preserved_permissions: Optional[int] = None


class SafeFileWriter:
    """
    Atomic file writer with backup and audit trail.

    Features:
    - Automatic backup before overwrite
    - Atomic write (temp file + rename)
    - Content hash verification
    - Permission preservation
    - File locking to prevent race conditions (Unix)

    Security:
    - Uses fcntl.flock() on Unix for exclusive locking
    - Atomic rename prevents partial writes
    - Hash verification ensures data integrity
    """

    BACKUP_DIR = ".gemini_backups"
    MAX_BACKUPS_PER_FILE = 5
    LOCK_TIMEOUT = 5.0  # seconds

    def __init__(self, sandbox_root: str = None):
        self.sandbox_root = Path(sandbox_root or config.sandbox_root)
        self.backup_root = self.sandbox_root / self.BACKUP_DIR

    def write(self, path: str, content: str, create_backup: bool = True) -> WriteResult:
        """
        Safely write content to file with atomic operation and locking.

        1. Validate path is in sandbox
        2. Acquire file lock (Unix only)
        3. Create backup if file exists
        4. Write to temp file
        5. Verify content hash
        6. Atomic rename to target
        7. Release lock
        """
        target_path = Path(path)

        # Validate sandbox using secure path comparison
        # SECURITY: Use is_relative_to() instead of string startswith() to prevent
        # path traversal attacks like /var/data vs /var/database
        try:
            resolved = target_path.resolve()
            sandbox_resolved = self.sandbox_root.resolve()
            if not resolved.is_relative_to(sandbox_resolved):
                return WriteResult(
                    success=False,
                    path=str(path),
                    backup_path=None,
                    content_hash="",
                    error="Path outside sandbox"
                )
        except Exception as e:
            return WriteResult(False, str(path), None, "", str(e))

        # Use file locking to prevent race conditions
        try:
            with file_lock(str(resolved), timeout=self.LOCK_TIMEOUT, exclusive=True):
                return self._write_locked(target_path, content, create_backup)
        except FileLockError as e:
            return WriteResult(False, str(path), None, "", str(e))

    def _write_locked(self, target_path: Path, content: str, create_backup: bool) -> WriteResult:
        """Internal write operation, called while holding the lock."""
        # Preserve permissions if file exists
        preserved_permissions = None
        if target_path.exists():
            try:
                preserved_permissions = target_path.stat().st_mode
            except OSError:
                pass

        # Create backup if file exists
        backup_path = None
        if create_backup and target_path.exists():
            backup_path = self._create_backup(target_path)

        # Write to temp file first
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        try:
            # Create parent directories
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file in same directory (for atomic rename)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=target_path.parent,
                prefix=f".{target_path.name}.",
                suffix=".tmp"
            )

            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    f.write(content)

                # Verify written content
                with open(temp_path, 'r', encoding='utf-8') as f:
                    if hashlib.sha256(f.read().encode()).hexdigest()[:16] != content_hash:
                        raise IOError("Content verification failed")

                # Restore permissions before rename
                if preserved_permissions is not None:
                    os.chmod(temp_path, preserved_permissions)

                # Atomic rename
                os.replace(temp_path, target_path)

            except Exception:
                # Cleanup temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

            return WriteResult(
                success=True,
                path=str(target_path),
                backup_path=backup_path,
                content_hash=content_hash,
                preserved_permissions=preserved_permissions
            )

        except Exception as e:
            return WriteResult(False, str(target_path), backup_path, "", str(e))

    def _create_backup(self, path: Path) -> str:
        """Create timestamped backup of file."""
        self.backup_root.mkdir(parents=True, exist_ok=True)

        # Add .gitignore to backup directory
        gitignore_path = self.backup_root / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("*\n")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        microseconds = datetime.now().strftime("%f")[:4]

        try:
            relative_path = path.relative_to(self.sandbox_root)
        except ValueError:
            relative_path = Path(path.name)

        backup_name = f"{relative_path.name}.{timestamp}_{microseconds}.bak"

        # Create subdirectory structure in backup
        backup_subdir = self.backup_root / relative_path.parent
        backup_subdir.mkdir(parents=True, exist_ok=True)

        backup_path = backup_subdir / backup_name
        shutil.copy2(path, backup_path)

        # Rotate old backups
        self._rotate_backups(backup_subdir, relative_path.name)

        return str(backup_path)

    def _rotate_backups(self, backup_dir: Path, filename: str):
        """Keep only MAX_BACKUPS_PER_FILE most recent backups."""
        backups = sorted(
            backup_dir.glob(f"{filename}.*.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        for old_backup in backups[self.MAX_BACKUPS_PER_FILE:]:
            old_backup.unlink()


def secure_write_file(path: str, content: str, create_backup: bool = True) -> WriteResult:
    """Convenience function for safe file writing."""
    writer = SafeFileWriter()
    return writer.write(path, content, create_backup)
