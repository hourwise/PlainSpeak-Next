"""The MCP server: PlainSpeak's canonical operations as tools for an agent.

An adapter, not an engine. It exposes three pipeline operations — `present`,
`verify` and `diagnose` — over the Model Context Protocol, and returns exactly
the versioned contracts the CLI returns (`plainspeak.present.v1`,
`plainspeak.verify.v1`, `plainspeak.diagnose.v1`), byte for byte. It may import
`pipeline` and nothing else from PlainSpeak; nothing in PlainSpeak imports it
except the `plainspeak serve` command that starts it.

Local-first by construction:

- **Transport:** standard input and output only (newline-delimited JSON-RPC
  2.0, the MCP stdio transport). No sockets, no HTTP, no hosted anything.
- **No dependencies.** The protocol subset a tools-only server needs —
  lifecycle, `tools/list`, `tools/call`, `ping` — is small and stable, and is
  implemented here with the standard library, so installing PlainSpeak pulls in
  no MCP SDK, no web framework and no telemetry.
- **No files, no shell, no mutation.** Every tool takes text as an argument and
  returns a result. There is no argument naming a path, nothing is written,
  nothing is executed, and no request can change PlainSpeak's rules, policies
  or profiles. Input is treated as untrusted data and bounded in size.
- **Deterministic.** The same request produces the same bytes.
"""

from .server import PROTOCOL_VERSIONS, SERVER_NAME, Server, serve_stdio
from .tools import MAX_TEXT_CHARACTERS, TOOLS

__all__ = [
    "MAX_TEXT_CHARACTERS",
    "PROTOCOL_VERSIONS",
    "SERVER_NAME",
    "Server",
    "TOOLS",
    "serve_stdio",
]
