"""Shell tool for safe code execution in isolated subprocess."""

import subprocess
import tempfile
import os
from pathlib import Path
from langchain_core.tools import tool

# Blocklist of dangerous patterns
BLOCKED_PATTERNS = [
    "rm -rf /",
    "sudo ",
    "systemctl ",
    "shutdown",
    "reboot",
    ":(){ :|:& };:",  # fork bomb
    "chmod 777 /",
    "mkfs.",
    "dd if=",
    "/dev/sda",
    "format c:",
    "del /f /s",
]

MAX_TIMEOUT = 30  # seconds


def _is_safe(code: str) -> tuple[bool, str]:
    """Check if code contains blocked patterns."""
    code_lower = code.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in code_lower:
            return False, f"Blocked dangerous pattern detected: {pattern}"
    return True, ""


@tool
def execute_code(code: str, language: str = "python") -> str:
    """Execute code in a subprocess with safety checks and timeout.

    Args:
        code: The source code to execute.
        language: Programming language (only 'python' is supported currently).

    Returns:
        Combined stdout and stderr output, or error message.
    """
    if language not in ("python", "py"):
        return f"Error: Unsupported language '{language}'. Only Python is supported."

    safe, reason = _is_safe(code)
    if not safe:
        return f"Execution blocked: {reason}"

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            temp_path = f.name

        result = subprocess.run(
            ["python", temp_path],
            capture_output=True,
            text=True,
            timeout=MAX_TIMEOUT,
            cwd=str(Path(__file__).parent.parent.parent),
        )

        os.unlink(temp_path)

        output_parts = []
        if result.stdout:
            output_parts.append(f"[stdout]\n{result.stdout}")
        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr}")
        if not result.stdout and not result.stderr:
            output_parts.append("[no output]")

        output_parts.append(f"\n[exit code: {result.returncode}]")
        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return f"Execution timed out after {MAX_TIMEOUT} seconds"
    except Exception as e:
        return f"Execution error: {e}"


SHELL_TOOLS = [execute_code]
