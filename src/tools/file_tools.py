"""File system tools for agents — read/write/list files in workspace."""

import os
from pathlib import Path
from langchain_core.tools import tool

WORKSPACE_ROOT = Path(__file__).parent.parent.parent


def _resolve_path(path: str) -> Path:
    """Resolve a path relative to workspace root with security check."""
    p = (WORKSPACE_ROOT / path).resolve()
    if not str(p).startswith(str(WORKSPACE_ROOT.resolve())):
        raise ValueError(f"Path traversal denied: {path}")
    return p


@tool
def read_file(path: str) -> str:
    """Read the contents of a file.

    Args:
        path: File path relative to the project workspace.

    Returns:
        The file content as a string, or an error message.
    """
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"Error: File not found: {path}"
        if not target.is_file():
            return f"Error: Not a file: {path}"
        return target.read_text(encoding="utf-8")
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with the given content.

    Args:
        path: File path relative to the project workspace.
        content: The content to write.

    Returns:
        A confirmation message.
    """
    try:
        target = _resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"File written successfully: {path} ({len(content)} chars)"
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def list_directory(path: str = ".") -> str:
    """List the contents of a directory.

    Args:
        path: Directory path relative to the workspace. Defaults to root.

    Returns:
        A formatted listing of files and directories.
    """
    try:
        target = _resolve_path(path) if path != "." else WORKSPACE_ROOT
        if not target.exists():
            return f"Error: Directory not found: {path}"
        if not target.is_dir():
            return f"Error: Not a directory: {path}"

        items = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        lines = []
        for item in items:
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            prefix = "[DIR] " if item.is_dir() else "[FILE]"
            lines.append(f"{prefix} {item.name}")
        return "\n".join(lines) if lines else "(empty directory)"
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error listing directory: {e}"


@tool
def delete_file(path: str) -> str:
    """Delete a file.

    Args:
        path: File path relative to the workspace.

    Returns:
        Confirmation or error message.
    """
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"Error: File not found: {path}"
        target.unlink()
        return f"File deleted: {path}"
    except ValueError as e:
        return f"Security error: {e}"
    except Exception as e:
        return f"Error deleting file: {e}"


# Tool list for registration
FILE_TOOLS = [read_file, write_file, list_directory, delete_file]
