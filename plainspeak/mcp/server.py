"""The MCP stdio transport and the protocol subset a tools-only server needs.

Messages are JSON-RPC 2.0, one per line, UTF-8, on standard input and output.
Standard error is for diagnostics only. Supported:

    initialize                  version negotiation; capabilities: tools
    notifications/initialized   acknowledged silently
    ping                        {}
    tools/list                  the three tools
    tools/call                  run one

Everything else that expects an answer gets a JSON-RPC error, never silence
and never a guess. A request before `initialize` is refused, as is a message
larger than `MAX_MESSAGE_BYTES`, a batch, or anything that is not a JSON-RPC
2.0 message. A tool that runs but cannot handle its input — an empty text, an
unknown profile — returns a result marked `isError` carrying the contract's
own error code, which is how MCP distinguishes a tool's failure from a
protocol's.
"""
from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO, Optional

from .. import __version__
from .tools import TOOLS, ToolArgumentError

SERVER_NAME = "plainspeak"

#: Protocol revisions this server speaks, newest first. A client asking for one
#: of them gets it; a client asking for anything else is offered the newest, and
#: decides for itself whether to continue.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

#: Revisions from which a tool result may carry `structuredContent` and a tool
#: definition an `outputSchema`.
STRUCTURED_FROM = "2025-06-18"

#: One message may not exceed this. The largest legitimate request is a verify
#: call with two texts at the tool limit, JSON-escaped.
MAX_MESSAGE_BYTES = 4 * 1024 * 1024

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

INSTRUCTIONS = (
    "PlainSpeak is a deterministic, offline engine for presenting and verifying English prose. "
    "Use `present` to apply only PlainSpeak's reviewed SAFE changes to a text, `diagnose` to see "
    "what it observes without changing anything, and `verify` to check a rewrite made by anyone "
    "— including you — against its integrity model. `verify` returns ACCEPTED, REFUSED or "
    "INCONCLUSIVE; INCONCLUSIVE is not a pass, and ACCEPTED does not mean the texts mean the "
    "same thing, only that every protected item survived and every difference is accounted for."
)


class Server:
    """One session's state: whether it has been initialised, and under which revision."""

    def __init__(self) -> None:
        self.protocol_version: Optional[str] = None

    @property
    def structured(self) -> bool:
        return self.protocol_version is not None and self.protocol_version >= STRUCTURED_FROM

    # ── Dispatch ──────────────────────────────────────────────────────────

    def handle_line(self, line: bytes) -> Optional[dict[str, Any]]:
        """Answer one line of input. `None` when no answer is due."""
        try:
            message = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _error(None, PARSE_ERROR, "not valid UTF-8 JSON")
        return self.handle(message)

    def handle(self, message: Any) -> Optional[dict[str, Any]]:
        if isinstance(message, list):
            return _error(None, INVALID_REQUEST, "batches are not supported")
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _error(_id_of(message), INVALID_REQUEST, "not a JSON-RPC 2.0 message")
        if "method" not in message:
            return None  # a response to something we never sent; nothing to answer
        method = message["method"]
        is_request = "id" in message
        request_id = message.get("id")
        if not isinstance(method, str):
            return _error(request_id, INVALID_REQUEST, "method must be a string") if is_request else None
        if is_request and (request_id is None or isinstance(request_id, bool)
                           or not isinstance(request_id, (str, int))):
            # MCP: a request id is a string or an integer, and never null.
            return _error(None, INVALID_REQUEST, "id must be a string or an integer")
        params = message.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return _error(request_id, INVALID_PARAMS, "params must be an object") if is_request else None

        if not is_request:
            return None  # notifications, including notifications/initialized, need no answer

        if method == "initialize":
            return _result(request_id, self._initialize(params))
        if method == "ping":
            return _result(request_id, {})
        if self.protocol_version is None:
            return _error(request_id, INVALID_REQUEST, "the session has not been initialised")
        if method == "tools/list":
            return _result(request_id, {
                "tools": [tool.definition(self.structured) for tool in TOOLS.values()],
            })
        if method == "tools/call":
            return self._call(request_id, params)
        return _error(request_id, METHOD_NOT_FOUND, f"method not found: {method}")

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        self.protocol_version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "title": "PlainSpeak", "version": __version__},
            "instructions": INSTRUCTIONS,
        }

    def _call(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        tool = TOOLS.get(name) if isinstance(name, str) else None
        if tool is None:
            return _error(request_id, INVALID_PARAMS, f"unknown tool: {name!r}")
        try:
            data, text, is_error = tool.call(params.get("arguments", {}))
        except ToolArgumentError as error:
            return _error(request_id, INVALID_PARAMS, f"{tool.name}: {error}")
        except Exception as error:  # noqa: BLE001 — reported to the caller, never swallowed
            return _error(request_id, INTERNAL_ERROR, f"{tool.name}: {type(error).__name__}: {error}")
        result: dict[str, Any] = {"content": [{"type": "text", "text": text}], "isError": is_error}
        if self.structured:
            result["structuredContent"] = data
        return _result(request_id, result)


def _result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _id_of(message: Any) -> Any:
    if isinstance(message, dict):
        value = message.get("id")
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return value
    return None


def encode(message: dict[str, Any]) -> bytes:
    """One message, one line. JSON escapes every newline inside a string."""
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n").encode("utf-8")


def serve_stdio(stdin: Optional[BinaryIO] = None, stdout: Optional[BinaryIO] = None) -> int:
    """Serve one session over standard input and output until input ends."""
    reader = stdin if stdin is not None else sys.stdin.buffer
    writer = stdout if stdout is not None else sys.stdout.buffer
    server = Server()
    while True:
        line = reader.readline(MAX_MESSAGE_BYTES + 1)
        if not line:
            return 0
        if len(line) > MAX_MESSAGE_BYTES and not line.endswith(b"\n"):
            # Discard the rest of the oversized message before answering it.
            while True:
                rest = reader.readline(MAX_MESSAGE_BYTES)
                if not rest or rest.endswith(b"\n"):
                    break
            answer = _error(None, INVALID_REQUEST, f"message larger than {MAX_MESSAGE_BYTES} bytes")
        elif not line.strip():
            continue
        else:
            try:
                answer = server.handle_line(line)
            except Exception as error:  # noqa: BLE001 — a failure must reach the client, not kill the session
                answer = _error(None, INTERNAL_ERROR, f"{type(error).__name__}: {error}")
        if answer is not None:
            writer.write(encode(answer))
            writer.flush()
