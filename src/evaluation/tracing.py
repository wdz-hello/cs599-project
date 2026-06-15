"""Observability — LLM call tracing with optional LangFuse integration."""

import time
import json
import logging
from pathlib import Path
from typing import Optional, Any
from datetime import datetime
from src.config.settings import settings

logger = logging.getLogger("devmind.tracing")


class TraceManager:
    """Manages LLM observability traces.

    If LangFuse credentials are configured, traces are sent to LangFuse.
    Otherwise, traces are logged to a local JSONL file for later analysis.
    """

    def __init__(self):
        self._traces: dict[str, dict] = {}
        self._langfuse = None
        self._use_langfuse = False

        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                from langfuse import Langfuse
                self._langfuse = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                self._use_langfuse = True
                logger.info("LangFuse tracing enabled")
            except ImportError:
                logger.warning("langfuse package not installed, using file-based tracing")
            except Exception as e:
                logger.warning(f"LangFuse init failed: {e}, using file-based tracing")

        # File-based fallback
        self._log_dir = Path(settings.CHROMA_PERSIST_DIR).parent / "traces"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    def start_trace(self, name: str, metadata: Optional[dict] = None) -> str:
        """Start a new trace.

        Args:
            name: Human-readable trace name (e.g., 'spec_architect_run').
            metadata: Optional key-value metadata.

        Returns:
            A trace_id string for use with subsequent log calls.
        """
        trace_id = f"{name}_{int(time.time() * 1000)}"

        trace = {
            "trace_id": trace_id,
            "name": name,
            "metadata": metadata or {},
            "start_time": time.time(),
            "llm_calls": [],
            "tool_calls": [],
            "status": "running",
        }
        self._traces[trace_id] = trace

        if self._use_langfuse and self._langfuse:
            try:
                self._langfuse.trace(
                    id=trace_id,
                    name=name,
                    metadata=metadata,
                )
            except Exception:
                pass

        return trace_id

    def log_llm_call(
        self,
        trace_id: str,
        prompt: str,
        response: str,
        model: str,
        tokens: int = 0,
    ) -> None:
        """Log an LLM API call within a trace.

        Args:
            trace_id: Trace identifier from start_trace.
            prompt: The input prompt sent to the LLM.
            response: The LLM's response text.
            model: Model name (e.g., 'deepseek-chat').
            tokens: Approximate token count.
        """
        entry = {
            "timestamp": time.time(),
            "model": model,
            "prompt": prompt[:500],  # Truncate for storage
            "response": response[:500],
            "tokens": tokens,
        }

        if trace_id in self._traces:
            self._traces[trace_id]["llm_calls"].append(entry)

        if self._use_langfuse and self._langfuse:
            try:
                trace = self._langfuse.trace(id=trace_id)
                trace.generation(
                    name=f"llm_{model}",
                    model=model,
                    input=prompt[:1000],
                    output=response[:1000],
                )
            except Exception:
                pass

        self._write_to_file(trace_id, "llm_call", entry)

    def log_tool_call(
        self,
        trace_id: str,
        tool_name: str,
        input_args: dict,
        output: str,
    ) -> None:
        """Log a tool invocation within a trace.

        Args:
            trace_id: Trace identifier.
            tool_name: Name of the tool (e.g., 'read_file').
            input_args: Arguments passed to the tool.
            output: Tool return value (truncated).
        """
        entry = {
            "timestamp": time.time(),
            "tool": tool_name,
            "input": dict(input_args),
            "output": output[:500],
        }

        if trace_id in self._traces:
            self._traces[trace_id]["tool_calls"].append(entry)

        if self._use_langfuse and self._langfuse:
            try:
                trace = self._langfuse.trace(id=trace_id)
                trace.span(
                    name=f"tool_{tool_name}",
                    input=input_args,
                    output=output[:1000],
                )
            except Exception:
                pass

        self._write_to_file(trace_id, "tool_call", entry)

    def end_trace(self, trace_id: str, status: str = "success") -> None:
        """Complete a trace.

        Args:
            trace_id: Trace identifier.
            status: 'success' or 'error'.
        """
        if trace_id in self._traces:
            self._traces[trace_id]["status"] = status
            self._traces[trace_id]["end_time"] = time.time()
            duration = (
                self._traces[trace_id]["end_time"]
                - self._traces[trace_id]["start_time"]
            )
            self._traces[trace_id]["duration_ms"] = int(duration * 1000)

        self._write_to_file(trace_id, "trace_end", {"status": status})

        if self._use_langfuse and self._langfuse:
            try:
                self._langfuse.flush()
            except Exception:
                pass

    def get_trace(self, trace_id: str) -> Optional[dict]:
        """Retrieve a trace by ID."""
        return self._traces.get(trace_id)

    def _write_to_file(self, trace_id: str, event_type: str, data: dict) -> None:
        """Append a trace event to the JSONL log file."""
        try:
            record = {
                "trace_id": trace_id,
                "event": event_type,
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass


# Global instance
trace_manager = TraceManager()
