# `plainspeak serve`: PlainSpeak as an MCP server

`plainspeak serve` runs PlainSpeak as a local
[Model Context Protocol](https://modelcontextprotocol.io) server, so an agent or
an MCP client can call it as a tool. It exposes three of PlainSpeak's canonical
operations and nothing else.

| Tool | Does | Returns |
|---|---|---|
| `present` | Applies PlainSpeak's SAFE changes to a text, and nothing else | `plainspeak.present.v1` |
| `verify` | Checks a rewrite made by anyone — including the agent itself — against the integrity model | `plainspeak.verify.v1` |
| `diagnose` | Reports everything PlainSpeak observes about a text, and changes nothing | `plainspeak.diagnose.v1` |

Each tool returns **exactly the bytes** the CLI prints with `--format json` —
the same contract, from the same pipeline call — as its text content, and the
same object as structured content for clients that negotiate protocol revision
`2025-06-18` or later. A tool that cannot handle its input (an empty text, say)
returns a result marked `isError` carrying the contract's own error code.
Arguments outside a tool's schema are a JSON-RPC `invalid params` error.

`verify` returns `ACCEPTED`, `REFUSED` or `INCONCLUSIVE`. `INCONCLUSIVE` is not a
pass, and `ACCEPTED` does not mean two texts mean the same thing — only that
every protected item survived and every difference is one the model accounts
for. See [VERIFY.md](VERIFY.md). The server says so in its instructions and in
the tool's description, so an agent reading either is told.

## Setting it up

The server speaks the MCP **stdio** transport: the client starts
`plainspeak serve` and talks to it over standard input and output.

Claude Code:

```bash
claude mcp add plainspeak -- plainspeak serve
```

Claude Desktop, or any client configured with JSON:

```json
{
  "mcpServers": {
    "plainspeak": { "command": "plainspeak", "args": ["serve"] }
  }
}
```

`plainspeak` must be on the client's `PATH` (`pip install plainspeak-next`, in
the environment the client will run it from); otherwise give the full path to
the executable.

## What it will not do

- **No network.** stdio only. There is no HTTP transport, no listening socket and
  nothing hosted. The tools work with networking disabled, and a test proves it.
- **No files.** No tool has an argument that names a path. Every tool takes text
  and returns a result; nothing is read from disk on an agent's behalf and
  nothing is written.
- **No commands, no mutation.** Nothing is executed, and nothing an agent sends
  can change a rule, a policy, a profile or any other part of PlainSpeak.
- **No telemetry**, and no dependencies. The protocol subset a tools-only server
  needs — the lifecycle handshake with version negotiation, `tools/list`,
  `tools/call` and `ping` — is implemented with the Python standard library, so
  installing PlainSpeak installs no MCP SDK, web framework or instrumentation
  library. A test fails if the server imports anything else.
- **No unbounded input.** A text argument may carry at most 200,000 characters
  and a message at most 4 MiB; larger ones are refused and the session
  continues.

Input from an agent is treated as untrusted data. Malformed JSON, batches,
invalid ids, unknown methods, unknown tools, requests before initialisation and
arguments outside the schema all receive JSON-RPC errors; none crashes the
session, and none is guessed at.

## Protocol

Protocol revisions `2025-11-25`, `2025-06-18`, `2025-03-26` and `2024-11-05`. A
client asking for one of them gets it; any other request is offered the newest,
and the client decides whether to continue. Capabilities: `tools` only
(`listChanged: false`). Tool annotations mark every tool read-only,
non-destructive, idempotent and closed-world.

Interoperability was checked against the official MCP Python SDK client
(`mcp` 2.2.0): the handshake, tool discovery, all three tools, tool errors,
invalid-argument errors and `ping`. That SDK is not a dependency of PlainSpeak.

## Architecture

`plainspeak.mcp` is an adapter layer. It may import `pipeline` and nothing else
from PlainSpeak; the only thing that imports it is the `plainspeak serve`
command; importing `plainspeak` does not import it. Each handler validates its
arguments, calls one pipeline function and returns that function's contract.
The architecture tests enforce all of this, and forbid the server — like every
interface — from containing a verifier of its own or spelling out a contract
identifier the pipeline defines.
