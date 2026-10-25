"""
RAG File Store Tools

Create and manage File Search Stores for RAG queries.
"""

import os
import time
from typing import Optional

from ...tools.registry import tool
from ...core.security import safe_input_path
from ...services import client
from ...core import log_progress


def resolve_store_name(store_name: str) -> str:
    """
    Resolve a store name to its full path.

    Accepts either:
    - Full path: "fileSearchStores/storename-abc123" -> returned as-is
    - Display name: "my_store" -> resolved to full path

    Args:
        store_name: Short display name or full store path

    Returns:
        Full store path (fileSearchStores/...)

    Raises:
        ValueError: If store not found by display name
    """
    # Already a full path
    if store_name.startswith("fileSearchStores/"):
        return store_name

    # Search by display name
    stores = client.file_search_stores.list()
    for store in stores:
        if store.display_name == store_name:
            return store.name

    # Not found
    available = [s.display_name for s in stores] if stores else []
    raise ValueError(
        f"Store '{store_name}' not found. "
        f"Available stores: {available or 'none'}"
    )


CREATE_FILE_STORE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Display name for the store"}
    },
    "required": ["name"]
}


@tool(
    name="gemini_create_file_store",
    description="Create a File Search Store for RAG. Use this before uploading files.",
    input_schema=CREATE_FILE_STORE_SCHEMA,
    tags=["rag", "storage"]
)
def create_file_store(name: str) -> str:
    """Create a File Search Store."""
    store = client.file_search_stores.create(
        config={"display_name": name}
    )
    return f"Created File Search Store:\n- Name: {store.name}\n- Display Name: {name}\n\nUse this store_name for uploads and queries: {store.name}"


UPLOAD_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "file_path": {"type": "string", "description": "Local file path to upload"},
        "store_name": {"type": "string", "description": "File Search Store name (from create_file_store)"}
    },
    "required": ["file_path", "store_name"]
}


@tool(
    name="gemini_upload_file",
    description="Upload a file to a File Search Store for RAG queries",
    input_schema=UPLOAD_FILE_SCHEMA,
    tags=["rag", "upload"]
)
def upload_file(file_path: str, store_name: str) -> str:
    """Upload file to File Search Store."""
    try:
        file_path = safe_input_path(file_path)   # sandbox + credentials policy: this file is uploaded to Google
    except ValueError as e:
        if "not found" in str(e):
            return f"Error: File not found: {file_path}"
        return f"Error: {e}"

    # Resolve short name to full path
    try:
        resolved_store = resolve_store_name(store_name)
    except ValueError as e:
        return f"Error: {e}"

    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    log_progress(f"Uploading '{filename}' ({file_size / 1024:.1f} KB) to RAG store...")

    operation = client.file_search_stores.upload_to_file_search_store(
        file=file_path,
        file_search_store_name=resolved_store,
        config={"display_name": filename}
    )

    # Wait for completion (with timeout)
    timeout = 120
    start = time.time()
    while not operation.done and (time.time() - start) < timeout:
        time.sleep(2)
        operation = client.operations.get(operation)

    if operation.done:
        log_progress(f"Upload completed: '{filename}'")
        return f"Successfully uploaded '{filename}' to store {store_name}"
    else:
        log_progress(f"Upload still in progress: '{filename}'")
        return f"Upload in progress for '{filename}'. Check back later."


LIST_FILE_STORES_SCHEMA = {
    "type": "object",
    "properties": {},
}


@tool(
    name="gemini_list_file_stores",
    description="List all available File Search Stores",
    input_schema=LIST_FILE_STORES_SCHEMA,
    tags=["rag", "list"]
)
def list_file_stores() -> str:
    """List all File Search Stores."""
    stores = client.file_search_stores.list()
    if not stores:
        return "No File Search Stores found. Create one with gemini_create_file_store."

    result = "**Available File Search Stores:**\n"
    for store in stores:
        result += f"- {store.display_name}: `{store.name}`\n"
    return result
