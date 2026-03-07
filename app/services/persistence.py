"""
SQLite Persistence for Conversation History

Provides persistent storage for conversation threads, replacing the in-memory
ConversationMemory. Data survives server restarts and IDE reconnections.

Features:
- SQLite-backed storage (no additional dependencies)
- Automatic TTL-based cleanup
- Thread-safe operations
- Automatic database initialization
"""

import sqlite3
import json
import os
import stat
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from ..core.config import config


# Restrictive permissions for database file (owner read/write only)
DB_FILE_PERMISSIONS = stat.S_IRUSR | stat.S_IWUSR  # 0o600


# Database location
DB_DIR = Path.home() / ".omni-ai-mcp"
DB_PATH = DB_DIR / "conversations.db"

# Configuration constants (exported for backward compatibility)
CONVERSATION_TTL_HOURS = config.conversation_ttl_hours
CONVERSATION_MAX_TURNS = config.conversation_max_turns


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""
    role: str
    content: str
    timestamp: str
    tool_name: str
    files: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: tuple) -> "ConversationTurn":
        return cls(
            role=row[0],
            content=row[1],
            timestamp=row[2],
            tool_name=row[3],
            files=json.loads(row[4]) if row[4] else []
        )


class PersistentConversationMemory:
    """
    SQLite-backed conversation memory.

    Thread-safe and persistent across server restarts.
    Automatically cleans up expired conversations.
    """

    def __init__(
        self,
        db_path: Path = DB_PATH,
        ttl_hours: int = None,
        max_turns: int = None
    ):
        # Handle both Path and str
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self.ttl_hours = ttl_hours or int(
            config.__dict__.get('conversation_ttl_hours', 3)
        )
        self.max_turns = max_turns or int(
            config.__dict__.get('conversation_max_turns', 50)
        )
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize database schema with secure permissions."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions on database directory (owner only)
        try:
            os.chmod(self.db_path.parent, stat.S_IRWXU)  # 0o700
        except OSError:
            pass  # Best effort - may fail on some filesystems

        db_exists = self.db_path.exists()

        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tool_name TEXT,
                    files TEXT DEFAULT '[]',
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_turns_conversation
                    ON turns(conversation_id);

                CREATE INDEX IF NOT EXISTS idx_conversations_updated
                    ON conversations(updated_at);

                -- Conversation index for v3.3.0
                CREATE TABLE IF NOT EXISTS conversation_index (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    mode TEXT NOT NULL DEFAULT 'local',
                    created_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL,
                    turn_count INTEGER DEFAULT 0,
                    first_prompt TEXT,
                    FOREIGN KEY (id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_conversation_index_mode
                    ON conversation_index(mode);

                CREATE INDEX IF NOT EXISTS idx_conversation_index_last_used
                    ON conversation_index(last_used_at);
            """)

        # Set restrictive permissions on database file (owner read/write only)
        # This prevents other users from reading conversation history
        if not db_exists and self.db_path.exists():
            try:
                os.chmod(self.db_path, DB_FILE_PERMISSIONS)  # 0o600
                # Also set permissions on WAL and SHM files if they exist
                wal_path = Path(f"{self.db_path}-wal")
                shm_path = Path(f"{self.db_path}-shm")
                if wal_path.exists():
                    os.chmod(wal_path, DB_FILE_PERMISSIONS)
                if shm_path.exists():
                    os.chmod(shm_path, DB_FILE_PERMISSIONS)
            except OSError:
                pass  # Best effort - may fail on some filesystems

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def create_thread(self, metadata: Dict[str, Any] = None, thread_id: str = None) -> str:
        """
        Create a new conversation thread.

        Args:
            metadata: Optional metadata to store with the thread
            thread_id: Optional custom thread ID (auto-generated UUID if not provided)

        Returns:
            The thread ID
        """
        import uuid
        thread_id = thread_id or str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """INSERT INTO conversations (id, created_at, updated_at, metadata)
                       VALUES (?, ?, ?, ?)""",
                    (thread_id, now, now, json.dumps(metadata or {}))
                )

        return thread_id

    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Get thread information.

        Returns None if thread doesn't exist or is expired.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, created_at, updated_at, metadata FROM conversations WHERE id = ?",
                (thread_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            # Check if expired
            updated_at = datetime.fromisoformat(row[2])
            if datetime.utcnow() - updated_at > timedelta(hours=self.ttl_hours):
                self.delete_thread(thread_id)
                return None

            return {
                "id": row[0],
                "created_at": row[1],
                "updated_at": row[2],
                "metadata": json.loads(row[3])
            }

    def add_turn(
        self,
        thread_id: str,
        role: str,
        content: str,
        tool_name: str = None,
        files: List[str] = None
    ) -> bool:
        """
        Add a turn to a conversation thread.

        Args:
            thread_id: The conversation thread ID
            role: "user" or "assistant"
            content: The message content
            tool_name: Optional tool that generated this turn
            files: Optional list of file paths referenced

        Returns:
            True if successful, False if thread not found or at max turns
        """
        now = datetime.utcnow().isoformat()

        with self._lock:
            with self._get_connection() as conn:
                # Check thread exists
                cursor = conn.execute(
                    "SELECT id FROM conversations WHERE id = ?",
                    (thread_id,)
                )
                if not cursor.fetchone():
                    return False

                # Check turn count
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM turns WHERE conversation_id = ?",
                    (thread_id,)
                )
                turn_count = cursor.fetchone()[0]
                if turn_count >= self.max_turns:
                    return False

                # Add turn
                conn.execute(
                    """INSERT INTO turns
                       (conversation_id, role, content, timestamp, tool_name, files)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (thread_id, role, content, now, tool_name, json.dumps(files or []))
                )

                # Update conversation timestamp
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, thread_id)
                )

        return True

    def get_thread_history(self, thread_id: str) -> List[ConversationTurn]:
        """
        Get all turns in a conversation thread.

        Returns empty list if thread doesn't exist.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT role, content, timestamp, tool_name, files
                   FROM turns
                   WHERE conversation_id = ?
                   ORDER BY timestamp""",
                (thread_id,)
            )
            return [ConversationTurn.from_row(row) for row in cursor.fetchall()]

    def build_context(
        self,
        thread_id: str,
        max_chars: int = 100000
    ) -> str:
        """
        Build a context string from conversation history.

        Prioritizes recent messages over older ones when truncating.

        Args:
            thread_id: The conversation thread ID
            max_chars: Maximum characters to include

        Returns:
            Formatted conversation history string
        """
        turns = self.get_thread_history(thread_id)
        if not turns:
            return ""

        parts = []
        total_chars = 0

        # Iterate newest to oldest to keep recent context when truncating
        for turn in reversed(turns):
            role_prefix = "User" if turn.role == "user" else "Assistant"
            part = f"[{role_prefix}]: {turn.content}"

            if total_chars + len(part) > max_chars:
                break

            parts.append(part)
            total_chars += len(part)

        # Reverse back to chronological order for output
        return "\n\n".join(reversed(parts))

    def get_or_create_thread(
        self,
        continuation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """
        Get existing thread or create a new one.

        Args:
            continuation_id: Optional existing thread ID
            metadata: Optional metadata (stored with thread creation)

        Returns:
            Tuple of (thread_id, is_new, thread_info)
        """
        if continuation_id:
            thread = self.get_thread(continuation_id)
            if thread:
                return (continuation_id, False, thread)

        # Create new thread with optional metadata
        thread_id = self.create_thread(metadata=metadata)
        thread = self.get_thread(thread_id)
        return (thread_id, True, thread)

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a conversation thread and all its turns."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM conversations WHERE id = ?",
                    (thread_id,)
                )
                return cursor.rowcount > 0

    def cleanup_expired(self) -> int:
        """
        Delete all expired conversation threads.

        Returns:
            Number of threads deleted
        """
        cutoff = (datetime.utcnow() - timedelta(hours=self.ttl_hours)).isoformat()

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM conversations WHERE updated_at < ?",
                    (cutoff,)
                )
                return cursor.rowcount

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored conversations."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM conversations")
            thread_count = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM turns")
            turn_count = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT MIN(created_at), MAX(updated_at) FROM conversations"
            )
            row = cursor.fetchone()
            oldest = row[0]
            newest = row[1]

        return {
            "threads": thread_count,
            "turns": turn_count,
            "oldest_thread": oldest,
            "newest_activity": newest,
            "db_path": str(self.db_path)
        }

    # ==================== Conversation Index Methods (v3.3.0) ====================

    def index_conversation(
        self,
        thread_id: str,
        title: str,
        mode: str = "local",
        first_prompt: str = None
    ) -> bool:
        """
        Add or update a conversation in the index.

        Args:
            thread_id: The conversation thread ID
            title: Human-readable title for the conversation
            mode: "local" (SQLite) or "cloud" (Interactions API)
            first_prompt: The first user prompt (for auto-title generation)

        Returns:
            True if successful
        """
        now = datetime.utcnow().isoformat()

        with self._lock:
            with self._get_connection() as conn:
                # Get turn count
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM turns WHERE conversation_id = ?",
                    (thread_id,)
                )
                turn_count = cursor.fetchone()[0]

                # Upsert into index
                conn.execute(
                    """INSERT INTO conversation_index
                       (id, title, mode, created_at, last_used_at, turn_count, first_prompt)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                           title = excluded.title,
                           last_used_at = excluded.last_used_at,
                           turn_count = excluded.turn_count""",
                    (thread_id, title, mode, now, now, turn_count, first_prompt)
                )

        return True

    def update_index_activity(self, thread_id: str) -> bool:
        """Update last_used_at and turn_count for a conversation."""
        now = datetime.utcnow().isoformat()

        with self._lock:
            with self._get_connection() as conn:
                # Get current turn count
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM turns WHERE conversation_id = ?",
                    (thread_id,)
                )
                turn_count = cursor.fetchone()[0]

                cursor = conn.execute(
                    """UPDATE conversation_index
                       SET last_used_at = ?, turn_count = ?
                       WHERE id = ?""",
                    (now, turn_count, thread_id)
                )
                return cursor.rowcount > 0

    def list_conversations(
        self,
        mode: str = None,
        search: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List conversations from the index.

        Args:
            mode: Filter by mode ("local" or "cloud"), None for all
            search: Search in title and first_prompt
            limit: Maximum results to return

        Returns:
            List of conversation index entries
        """
        query = """
            SELECT id, title, mode, created_at, last_used_at, turn_count, first_prompt
            FROM conversation_index
            WHERE 1=1
        """
        params = []

        if mode:
            query += " AND mode = ?"
            params.append(mode)

        if search:
            query += " AND (title LIKE ? OR first_prompt LIKE ?)"
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern])

        query += " ORDER BY last_used_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "title": row[1],
                "mode": row[2],
                "created_at": row[3],
                "last_used_at": row[4],
                "turn_count": row[5],
                "first_prompt": row[6]
            }
            for row in rows
        ]

    def get_conversation_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Find a conversation by exact or partial title match."""
        with self._get_connection() as conn:
            # Try exact match first
            cursor = conn.execute(
                "SELECT id, title, mode FROM conversation_index WHERE title = ?",
                (title,)
            )
            row = cursor.fetchone()

            if not row:
                # Try partial match
                cursor = conn.execute(
                    "SELECT id, title, mode FROM conversation_index WHERE title LIKE ? LIMIT 1",
                    (f"%{title}%",)
                )
                row = cursor.fetchone()

            if row:
                return {"id": row[0], "title": row[1], "mode": row[2]}
            return None

    def delete_from_index(self, thread_id: str) -> bool:
        """Remove a conversation from the index (and delete the conversation)."""
        # This will cascade delete from conversation_index due to FK
        return self.delete_thread(thread_id)

    def generate_title(self, first_prompt: str, max_length: int = 50) -> str:
        """
        Generate a title from the first prompt.

        Args:
            first_prompt: The first user message
            max_length: Maximum title length

        Returns:
            Generated title string
        """
        if not first_prompt:
            return "Untitled Conversation"

        # Clean and truncate
        title = first_prompt.strip()
        title = " ".join(title.split())  # Normalize whitespace

        if len(title) > max_length:
            title = title[:max_length - 3] + "..."

        return title

    def close(self):
        """Close the database connection (no-op for SQLite with context manager)."""
        # SQLite connections are managed via context manager
        # This method exists for API compatibility
        pass


# Global instance
conversation_memory = PersistentConversationMemory()


# Convenience functions for backwards compatibility
def create_thread(metadata: Dict = None) -> str:
    return conversation_memory.create_thread(metadata)


def get_thread(thread_id: str) -> Optional[Dict]:
    return conversation_memory.get_thread(thread_id)


def add_turn(thread_id: str, role: str, content: str,
             tool_name: str = None, files: List[str] = None) -> bool:
    return conversation_memory.add_turn(thread_id, role, content, tool_name, files)


def get_history(thread_id: str) -> List[ConversationTurn]:
    return conversation_memory.get_thread_history(thread_id)


def build_context(thread_id: str, max_chars: int = 100000) -> str:
    return conversation_memory.build_context(thread_id, max_chars)


def get_or_create(continuation_id: str = None) -> tuple:
    return conversation_memory.get_or_create_thread(continuation_id)
