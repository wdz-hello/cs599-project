"""MCP (Model Context Protocol) Tool Server for DevMind.

Exposes file and shell tools via the MCP protocol, enabling any MCP-compatible
client to use DevMind's tool capabilities.

Run with: python -m src.mcp.tool_server
"""

import json
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.file_tools import FILE_TOOLS
from src.tools.shell_tools import SHELL_TOOLS


ALL_TOOLS = FILE_TOOLS + SHELL_TOOLS


def list_tools() -> list[dict]:
    """Return tool definitions in MCP format.

    Returns:
        List of tool definitions with name, description, and input schema.
    """
    definitions = []
    for tool in ALL_TOOLS:
        # Build JSON schema from tool's args_schema if available
        input_schema = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        if hasattr(tool, "args_schema") and tool.args_schema:
            schema = tool.args_schema.model_json_schema()
            input_schema["properties"] = schema.get("properties", {})
            input_schema["required"] = schema.get("required", [])

        definitions.append({
            "name": tool.name,
            "description": tool.description,
            "inputSchema": input_schema,
        })

    return definitions


def call_tool(name: str, arguments: dict) -> str:
    """Execute a tool by name with given arguments.

    Args:
        name: Tool name (e.g., 'read_file', 'execute_code').
        arguments: Keyword arguments to pass to the tool.

    Returns:
        Tool output as a string.
    """
    for tool in ALL_TOOLS:
        if tool.name == name:
            try:
                result = tool.invoke(arguments)
                return str(result)
            except Exception as e:
                return json.dumps({"error": str(e)})

    return json.dumps({"error": f"Unknown tool: {name}"})


def create_mcp_server():
    """Create a simple MCP server using stdio transport.

    This implements a minimal MCP-compatible JSON-RPC server over stdin/stdout.
    """
    print("DevMind MCP Tool Server starting...", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method", "")
        req_id = request.get("id")

        if method == "initialize":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "devmind-tool-server",
                        "version": "1.0.0",
                    },
                },
            }

        elif method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": list_tools()},
            }

        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            result_text = call_tool(tool_name, tool_args)

            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                },
            }

        elif method == "notifications/initialized":
            continue  # No response needed for notifications

        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    create_mcp_server()
