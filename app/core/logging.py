"""
Structured logging for omni-ai-mcp.
Supports both text and JSON formats for container observability.
"""

import os
import sys
import json
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler

from .config import config
from .security import secrets_sanitizer


@dataclass
class LogRecord:
    """Structured log record for JSON logging."""
    timestamp: str
    level: str
    tool: Optional[str]
    status: str
    duration_ms: Optional[float]
    request_id: Optional[str]
    details: Dict[str, Any]
    error: Optional[str]


class StructuredLogger:
    """
    JSON-structured logger for production observability.

    Features:
    - JSON output to stderr for container logging
    - Automatic secrets sanitization
    - Request ID tracking
    - Duration tracking

    Output format:
    {"timestamp": "...", "level": "INFO", "tool": "ask_gemini", ...}
    """

    def __init__(self, name: str = "omni-ai-mcp"):
        self.name = name

    def _emit(self, record: LogRecord):
        """Output log record as JSON to stderr."""
        # Sanitize sensitive data in details
        safe_details = {}
        for k, v in record.details.items():
            str_val = str(v) if not isinstance(v, str) else v
            safe_details[k] = secrets_sanitizer.sanitize(str_val)

        output = {
            "timestamp": record.timestamp,
            "level": record.level,
            "tool": record.tool,
            "status": record.status,
            "duration_ms": record.duration_ms,
            "request_id": record.request_id,
            "details": safe_details,
            "error": secrets_sanitizer.sanitize(record.error) if record.error else None
        }

        # Remove None values for cleaner output
        output = {k: v for k, v in output.items() if v is not None}

        print(json.dumps(output), file=sys.stderr, flush=True)

    def tool_start(self, tool: str, request_id: str, args: Dict):
        """Log tool execution start."""
        self._emit(LogRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level="INFO",
            tool=tool,
            status="start",
            duration_ms=None,
            request_id=request_id,
            details={"args_keys": list(args.keys())},
            error=None
        ))

    def tool_success(self, tool: str, request_id: str, duration_ms: float, result_len: int):
        """Log tool execution success."""
        self._emit(LogRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level="INFO",
            tool=tool,
            status="success",
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
            details={"result_length": result_len},
            error=None
        ))

    def tool_error(self, tool: str, request_id: str, duration_ms: float, error: str):
        """Log tool execution error."""
        self._emit(LogRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level="ERROR",
            tool=tool,
            status="error",
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
            details={},
            error=error
        ))

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._emit(LogRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level="INFO",
            tool=kwargs.get("tool"),
            status=kwargs.get("status", "info"),
            duration_ms=None,
            request_id=kwargs.get("request_id"),
            details={"message": message},
            error=None
        ))

    def error(self, message: str, **kwargs):
        """Log error message."""
        self._emit(LogRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            level="ERROR",
            tool=kwargs.get("tool"),
            status=kwargs.get("status", "error"),
            duration_ms=None,
            request_id=kwargs.get("request_id"),
            details={},
            error=message
        ))


# Global structured logger instance
structured_logger = StructuredLogger()


# =============================================================================
# ACTIVITY LOGGER (File-based)
# =============================================================================

activity_logger = None

def _init_activity_logger():
    """Initialize the activity file logger."""
    global activity_logger

    if not config.activity_log_enabled:
        return

    try:
        os.makedirs(config.log_dir, exist_ok=True)
        activity_log_path = os.path.join(config.log_dir, "activity.log")

        activity_logger = logging.getLogger("gemini_activity")
        activity_logger.setLevel(logging.INFO)
        activity_logger.propagate = False

        handler = RotatingFileHandler(
            activity_log_path,
            maxBytes=config.log_max_bytes,
            backupCount=config.log_backup_count
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        activity_logger.addHandler(handler)
    except Exception:
        activity_logger = None


# Initialize on module load
_init_activity_logger()


def log_activity(tool_name: str, status: str, duration_ms: float = 0,
                 details: Dict[str, Any] = None, error: str = None,
                 request_id: str = None):
    """
    Log tool activity for usage monitoring.

    Args:
        tool_name: Name of the tool called
        status: "start", "success", or "error"
        duration_ms: Execution time in milliseconds
        details: Additional details (truncated for privacy)
        error: Error message if status is "error"
        request_id: Unique request identifier
    """
    # JSON structured logging
    if config.log_format == "json":
        try:
            if status == "start":
                structured_logger.tool_start(tool_name, request_id or "", details or {})
            elif status == "success":
                result_len = details.get("result_len", 0) if details else 0
                structured_logger.tool_success(tool_name, request_id or "", duration_ms, result_len)
            elif status == "error":
                structured_logger.tool_error(tool_name, request_id or "", duration_ms, error or "")
        except Exception:
            pass
        return

    # Text format (file logging)
    if not activity_logger:
        return

    try:
        parts = [f"tool={tool_name}", f"status={status}"]

        if request_id:
            parts.append(f"req_id={request_id}")

        if duration_ms > 0:
            parts.append(f"duration={duration_ms:.0f}ms")

        if details:
            safe_details = {}
            for k, v in details.items():
                if isinstance(v, str) and len(v) > 100:
                    safe_details[k] = f"{v[:100]}... ({len(v)} chars)"
                elif isinstance(v, list):
                    safe_details[k] = f"[{len(v)} items]"
                else:
                    safe_details[k] = v
            parts.append(f"details={json.dumps(safe_details)}")

        if error:
            safe_error = secrets_sanitizer.sanitize(error[:200])
            parts.append(f"error={safe_error}")

        activity_logger.info(" | ".join(parts))
    except Exception:
        pass


def log_progress(message: str, stage: str = "progress"):
    """
    Log progress messages to stderr for long-running operations.
    """
    if config.log_format == "json":
        structured_logger.info(message, status=stage)
    else:
        print(f"[omni-ai-mcp] {message}", file=sys.stderr, flush=True)
