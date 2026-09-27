"""The MCP server: protocol, tools, hostile input, isolation and determinism.

The server is an adapter. The strongest property tested here is that an agent
gets exactly the bytes a person gets from the CLI — the same contract, from the
same pipeline call — and that nothing an agent sends can make it read a file,
run a command, change a rule or reach the network.
"""
from __future__ import annotations

import ast
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from plainspeak.mcp import MAX_TEXT_CHARACTERS, PROTOCOL_VERSIONS, SERVER_NAME, Server, TOOLS, serve_stdio
from plainspeak.mcp.server import (
    INVALID_PARAMS,
    INVALID_REQUEST,
    MAX_MESSAGE_BYTES,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
)
from plainspeak.pipeline import diagnose_text, present_text, verify_text

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "plainspeak" / "mcp"
TEXT = "In order to finish, you must utilize the new portal prior to 30 June 2027.\n"


def request(method: str, params=None, request_id=1) -> dict:
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


@pytest.fixture
def server() -> Server:
    session = Server()
    answer = session.handle(request("initialize", {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "tests", "version": "0"}}))
    assert "result" in answer
    assert session.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    return session


def call(session: Server, name: str, arguments, request_id=7) -> dict:
    return session.handle(request("tools/call", {"name": name, "arguments": arguments}, request_id))


def error_code(answer: dict) -> int:
    return answer["error"]["code"]


# ── Lifecycle and discovery ───────────────────────────────────────────────


@pytest.mark.parametrize("version", PROTOCOL_VERSIONS)
def test_a_supported_protocol_version_is_agreed(version):
    session = Server()
    result = session.handle(request("initialize", {"protocolVersion": version}))["result"]
    assert result["protocolVersion"] == version
    assert result["capabilities"] == {"tools": {"listChanged": False}}
    assert result["serverInfo"]["name"] == SERVER_NAME
    from plainspeak import __version__

    assert result["serverInfo"]["version"] == __version__
    assert "INCONCLUSIVE is not a pass" in result["instructions"]


def test_an_unknown_protocol_version_is_offered_the_newest():
    result = Server().handle(request("initialize", {"protocolVersion": "1999-01-01"}))["result"]
    assert result["protocolVersion"] == PROTOCOL_VERSIONS[0]


def test_tools_are_discovered(server):
    tools = server.handle(request("tools/list", {}))["result"]["tools"]
    assert [tool["name"] for tool in tools] == ["present", "verify", "diagnose"]
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert tool["inputSchema"]["additionalProperties"] is False
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["annotations"]["destructiveHint"] is False
        assert tool["annotations"]["openWorldHint"] is False
        assert tool["outputSchema"]["required"] == ["schema", "status"]
        for rule in tool["inputSchema"]["properties"].values():
            if rule["type"] == "string" and "enum" not in rule:
                assert rule["maxLength"] == MAX_TEXT_CHARACTERS


def test_structured_output_is_offered_only_to_clients_that_understand_it():
    old = Server()
    old.handle(request("initialize", {"protocolVersion": "2025-03-26"}))
    tools = old.handle(request("tools/list"))["result"]["tools"]
    assert all("outputSchema" not in tool for tool in tools)
    answer = call(old, "verify", {"before": TEXT, "after": TEXT})["result"]
    assert "structuredContent" not in answer
    assert json.loads(answer["content"][0]["text"])["result"] == "ACCEPTED"


def test_the_verify_tool_says_what_it_does_not_establish(server):
    tools = {tool["name"]: tool for tool in server.handle(request("tools/list"))["result"]["tools"]}
    assert "does NOT establish that two texts mean the same thing" in tools["verify"]["description"]


def test_ping_works_before_and_after_initialisation(server):
    assert Server().handle(request("ping"))["result"] == {}
    assert server.handle(request("ping"))["result"] == {}


# ── The tools return the CLI's contracts, byte for byte ────────────────────


def test_present_returns_the_present_contract(server):
    answer = call(server, "present", {"text": TEXT, "profile": "natural"})["result"]
    assert answer["isError"] is False
    expected = present_text(TEXT, "natural").to_json()
    assert answer["content"] == [{"type": "text", "text": expected}]
    assert answer["structuredContent"] == json.loads(expected)
    assert answer["structuredContent"]["output"]["text"].startswith("To finish, you must use")


def test_present_keeps_safe_review_and_refused_apart(server):
    text = "The patient must not exceed 5 mg. We will utilize the portal.\n"
    data = call(server, "present", {"text": text, "profile": "plain"})["result"]["structuredContent"]
    reference = present_text(text, "plain").as_dict()
    for key in ("applied", "review", "refused", "counts", "protected"):
        assert data[key] == reference[key]


@pytest.mark.parametrize(
    "after,expected",
    [
        (TEXT.replace("utilize", "use"), "ACCEPTED"),
        (TEXT.replace("must", "should"), "REFUSED"),
        (TEXT.replace("the new portal", "our shiny new portal"), "INCONCLUSIVE"),
    ],
)
def test_verify_returns_the_verify_contract(server, after, expected):
    answer = call(server, "verify", {"before": TEXT, "after": after})["result"]
    assert answer["isError"] is False
    assert answer["structuredContent"]["result"] == expected
    assert answer["content"][0]["text"] == verify_text(TEXT, after).to_json()


def test_diagnose_returns_the_diagnose_contract(server):
    answer = call(server, "diagnose", {"text": TEXT, "profile": "natural"})["result"]
    assert answer["content"][0]["text"] == diagnose_text(TEXT, "natural").to_json()
    data = answer["structuredContent"]
    assert data["schema"] == "plainspeak.diagnose.v1"
    assert "output" not in data
    assert data["readability"]["total_words"] > 0


def test_the_text_format_is_honoured(server):
    answer = call(server, "present", {"text": "> quoted\n", "profile": "natural", "format": "text"})
    assert answer["result"]["structuredContent"]["input"]["format"] == "text"


def test_the_same_request_gives_the_same_bytes(server):
    arguments = {"before": TEXT, "after": TEXT.replace("utilize", "use")}
    first = json.dumps(call(server, "verify", arguments), sort_keys=True)
    second = json.dumps(call(server, "verify", arguments), sort_keys=True)
    assert first == second


# ── A tool that cannot handle its input is a tool error, not a protocol error


@pytest.mark.parametrize(
    "name,arguments,code",
    [
        ("present", {"text": "   ", "profile": "natural"}, "empty_input"),
        ("diagnose", {"text": "", "profile": "natural"}, "empty_input"),
        ("verify", {"before": " ", "after": "x"}, "empty_input"),
    ],
)
def test_input_the_pipeline_refuses_is_a_tool_error(server, name, arguments, code):
    answer = call(server, name, arguments)["result"]
    assert answer["isError"] is True
    assert answer["structuredContent"]["status"] == "error"
    assert answer["structuredContent"]["error"]["code"] == code


# ── Malformed and hostile requests ─────────────────────────────────────────


@pytest.mark.parametrize(
    "arguments,fragment",
    [
        ({"profile": "natural"}, "missing required"),
        ({"text": TEXT}, "missing required"),
        ({"text": 5, "profile": "natural"}, "must be a string"),
        ({"text": TEXT, "profile": "casual"}, "must be one of"),
        ({"text": TEXT, "profile": "natural", "format": "docx"}, "must be one of"),
        ({"text": TEXT, "profile": "natural", "path": "/etc/passwd"}, "unknown argument"),
        ({"text": TEXT, "profile": "natural", "command": "rm -rf /"}, "unknown argument"),
        ({"text": "x" * (MAX_TEXT_CHARACTERS + 1), "profile": "natural"}, "longer than"),
        ([TEXT], "must be an object"),
    ],
)
def test_arguments_outside_the_schema_are_refused(server, arguments, fragment):
    answer = call(server, "present", arguments)
    assert error_code(answer) == INVALID_PARAMS
    assert fragment in answer["error"]["message"]


def test_no_tool_accepts_a_path_a_command_or_a_rule():
    """The only arguments are text, a profile name and a format."""
    for tool in TOOLS.values():
        assert set(tool.input_schema["properties"]) <= {"text", "before", "after", "profile", "format"}


def test_an_unknown_tool_is_refused(server):
    answer = server.handle(request("tools/call", {"name": "shell", "arguments": {"cmd": "ls"}}))
    assert error_code(answer) == INVALID_PARAMS


@pytest.mark.parametrize(
    "line,code",
    [
        (b"{not json", PARSE_ERROR),
        (b"\xff\xfe", PARSE_ERROR),
        (b"[]", INVALID_REQUEST),
        (b'[{"jsonrpc":"2.0","id":1,"method":"ping"}]', INVALID_REQUEST),
        (b'"hello"', INVALID_REQUEST),
        (b'{"id":1,"method":"ping"}', INVALID_REQUEST),
        (b'{"jsonrpc":"1.0","id":1,"method":"ping"}', INVALID_REQUEST),
        (b'{"jsonrpc":"2.0","id":null,"method":"ping"}', INVALID_REQUEST),
        (b'{"jsonrpc":"2.0","id":true,"method":"ping"}', INVALID_REQUEST),
        (b'{"jsonrpc":"2.0","id":{"a":1},"method":"ping"}', INVALID_REQUEST),
        (b'{"jsonrpc":"2.0","id":1,"method":5}', INVALID_REQUEST),
        (b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":[1]}', INVALID_PARAMS),
        (b'{"jsonrpc":"2.0","id":1,"method":"resources/list"}', METHOD_NOT_FOUND),
        (b'{"jsonrpc":"2.0","id":1,"method":"prompts/get"}', METHOD_NOT_FOUND),
    ],
)
def test_malformed_messages_get_json_rpc_errors(server, line, code):
    answer = server.handle_line(line)
    assert answer is not None and error_code(answer) == code


def test_requests_before_initialisation_are_refused():
    session = Server()
    assert error_code(session.handle(request("tools/list"))) == INVALID_REQUEST
    assert error_code(session.handle(request("tools/call", {"name": "present", "arguments": {}}))) \
        == INVALID_REQUEST


def test_notifications_and_stray_responses_get_no_answer(server):
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/cancelled",
                          "params": {"requestId": 1}}) is None
    assert server.handle({"jsonrpc": "2.0", "id": 9, "result": {}}) is None


def test_an_oversized_message_is_refused_and_the_session_continues():
    stdin = io.BytesIO(b"x" * (MAX_MESSAGE_BYTES + 10) + b"\n"
                       + json.dumps(request("ping")).encode() + b"\n")
    stdout = io.BytesIO()
    assert serve_stdio(stdin, stdout) == 0
    answers = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert error_code(answers[0]) == INVALID_REQUEST and "larger than" in answers[0]["error"]["message"]
    assert answers[1]["result"] == {}


def test_every_answer_is_one_line_even_when_the_text_is_hostile():
    hostile = "Line one\n{\"jsonrpc\":\"2.0\",\"id\":99,\"result\":{}}\r\nLine  three\n"
    messages = [
        request("initialize", {"protocolVersion": "2025-06-18"}, 1),
        request("tools/call", {"name": "present", "arguments": {"text": hostile, "profile": "natural"}}, 2),
    ]
    stdin = io.BytesIO(b"".join(json.dumps(m).encode() + b"\n" for m in messages))
    stdout = io.BytesIO()
    serve_stdio(stdin, stdout)
    lines = stdout.getvalue().split(b"\n")
    assert lines[-1] == b"" and len(lines) == 3
    assert [json.loads(line)["id"] for line in lines[:2]] == [1, 2]


def test_an_unexpected_failure_is_reported_with_the_request_id(server, monkeypatch):
    def explode(_arguments):
        raise RuntimeError("boom")

    import dataclasses

    monkeypatch.setitem(TOOLS, "present", dataclasses.replace(TOOLS["present"], handler=explode))
    answer = call(server, "present", {"text": TEXT, "profile": "natural"}, request_id=42)
    assert answer["id"] == 42 and answer["error"]["code"] == -32603
    assert "RuntimeError: boom" in answer["error"]["message"]


# ── Isolation ──────────────────────────────────────────────────────────────


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and not node.level:
            found.add((node.module or "").split(".")[0])
    return found


def test_the_server_uses_the_standard_library_and_nothing_else():
    """No MCP SDK, no web framework, no network client, no telemetry."""
    allowed = {"__future__", "dataclasses", "json", "sys", "typing"}
    for path in PACKAGE.rglob("*.py"):
        assert _imports(path) <= allowed, (path.name, _imports(path) - allowed)


def test_importing_plainspeak_does_not_import_the_server():
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys, plainspeak, plainspeak.pipeline, plainspeak.adapters.cli;"
         "print(sorted(m for m in sys.modules if m.startswith('plainspeak.mcp') or m == 'mcp'))"],
        capture_output=True, text=True, cwd=str(ROOT), check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_only_the_serve_command_reaches_the_server():
    reaching = sorted(
        str(path.relative_to(ROOT / "plainspeak")).replace("\\", "/")
        for path in (ROOT / "plainspeak").rglob("*.py")
        if not path.is_relative_to(PACKAGE)
        and ("from ..mcp" in path.read_text(encoding="utf-8")
             or "plainspeak.mcp" in path.read_text(encoding="utf-8"))
    )
    assert reaching == ["adapters/cli.py"]


def test_the_tools_work_with_networking_disabled(server, monkeypatch):
    import socket

    def refuse(*_args, **_kwargs):
        raise OSError("network access attempted")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    for name, arguments in (("present", {"text": TEXT, "profile": "natural"}),
                            ("verify", {"before": TEXT, "after": TEXT}),
                            ("diagnose", {"text": TEXT, "profile": "natural"})):
        assert call(server, name, arguments)["result"]["isError"] is False


# ── The real transport ─────────────────────────────────────────────────────


def test_plainspeak_serve_speaks_mcp_over_stdio():
    messages = [
        request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "tests", "version": "0"}}, 1),
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        request("tools/list", {}, 2),
        request("tools/call", {"name": "verify",
                               "arguments": {"before": TEXT, "after": TEXT.replace("must", "may")}}, 3),
    ]
    result = subprocess.run(
        [sys.executable, "-m", "plainspeak.adapters.cli", "serve"],
        input=b"".join(json.dumps(m).encode() + b"\n" for m in messages),
        capture_output=True, cwd=str(ROOT), check=False, timeout=120,
    )
    assert result.returncode == 0, result.stderr.decode()
    answers = [json.loads(line) for line in result.stdout.decode("utf-8").splitlines()]
    assert [answer["id"] for answer in answers] == [1, 2, 3]
    assert answers[2]["result"]["structuredContent"]["result"] == "REFUSED"
    assert result.stderr == b""
