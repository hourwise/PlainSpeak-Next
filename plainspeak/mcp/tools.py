"""The tools: their schemas, argument validation, and one call each into the pipeline.

Each handler validates its arguments against the schema it publishes, calls one
pipeline function, and returns that function's contract. No handler interprets
a result, filters it or adds to it; an agent sees what the CLI's JSON shows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..pipeline import (
    DIAGNOSE_SCHEMA,
    FORMAT_MARKDOWN,
    FORMAT_TEXT,
    PRESENT_SCHEMA,
    VERIFY_SCHEMA,
    PresentError,
    VerifyError,
    list_profiles,
    present_text,
    verify_text,
)
from ..pipeline import diagnose_text

#: The largest text any one argument may carry. Verification aligns two texts
#: and is quadratic in the worst case; an unbounded argument would let one
#: request occupy the server indefinitely.
MAX_TEXT_CHARACTERS = 200_000

_PROFILES = tuple(item["id"] for item in list_profiles())

_FORMAT = {
    "type": "string",
    "enum": [FORMAT_MARKDOWN, FORMAT_TEXT],
    "default": FORMAT_MARKDOWN,
    "description": "How to parse the text. Markdown keeps code, quotations, tables and link "
                   "destinations out of reach; plain text treats every paragraph as prose.",
}


def _text(description: str) -> dict[str, Any]:
    return {"type": "string", "maxLength": MAX_TEXT_CHARACTERS, "description": description}


_PROFILE = {
    "type": "string",
    "enum": list(_PROFILES),
    "description": "Style profile. It decides which style observations are reported; it does not "
                   "change the SAFE changes or what is protected.",
}


class ToolArgumentError(ValueError):
    """Arguments that do not satisfy the tool's input schema."""


@dataclass(frozen=True)
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    schema_id: str
    handler: Callable[[dict[str, Any]], Any]

    def definition(self, structured: bool) -> dict[str, Any]:
        found = {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "title": self.title,
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        }
        if structured:
            found["outputSchema"] = {
                "type": "object",
                "properties": {
                    "schema": {"type": "string", "const": self.schema_id},
                    "status": {"type": "string", "enum": ["ok", "error"]},
                },
                "required": ["schema", "status"],
            }
        return found

    def call(self, arguments: Any) -> tuple[dict[str, Any], str, bool]:
        """Run the tool.

        Returns the contract as data, the same contract as the canonical JSON
        the CLI prints — produced by the pipeline, not re-rendered here — and
        whether it is an error.
        """
        validate(self.input_schema, arguments)
        try:
            result = self.handler(arguments)
        except (PresentError, VerifyError) as error:
            return error.as_dict(), error.to_json(), True
        return result.as_dict(), result.to_json(), False


def validate(schema: dict[str, Any], arguments: Any) -> None:
    """The subset of JSON Schema the published input schemas use, enforced exactly."""
    if not isinstance(arguments, dict):
        raise ToolArgumentError("arguments must be an object")
    properties = schema["properties"]
    unknown = sorted(set(arguments) - set(properties))
    if unknown:
        raise ToolArgumentError(f"unknown argument(s): {', '.join(unknown)}")
    missing = [name for name in schema.get("required", ()) if name not in arguments]
    if missing:
        raise ToolArgumentError(f"missing required argument(s): {', '.join(missing)}")
    for name, value in arguments.items():
        rule = properties[name]
        if rule["type"] == "string" and not isinstance(value, str):
            raise ToolArgumentError(f"`{name}` must be a string")
        if "enum" in rule and value not in rule["enum"]:
            raise ToolArgumentError(f"`{name}` must be one of: {', '.join(rule['enum'])}")
        if "maxLength" in rule and len(value) > rule["maxLength"]:
            raise ToolArgumentError(f"`{name}` is longer than {rule['maxLength']} characters")


def _markdown(arguments: dict[str, Any]) -> bool:
    return arguments.get("format", FORMAT_MARKDOWN) == FORMAT_MARKDOWN


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in (
        Tool(
            name="present",
            title="Present a text (SAFE changes only)",
            description=(
                "Apply PlainSpeak's governed presentation to a text: every SAFE change is "
                "applied, and nothing else. Every change passes the integrity firewall, which "
                "protects numbers, dates, amounts, units, negation, modals, comparators, "
                "identifiers and terms of art. Suggestions that need a person are reported and "
                "not applied; refused changes are reported with the reason. Returns the "
                "versioned plainspeak.present.v1 result; the presented text is output.text."
            ),
            input_schema=_schema(
                {"text": _text("The text to present."), "profile": _PROFILE, "format": _FORMAT},
                ["text", "profile"],
            ),
            schema_id=PRESENT_SCHEMA,
            handler=lambda arguments: present_text(
                arguments["text"], arguments["profile"], markdown=_markdown(arguments)),
        ),
        Tool(
            name="verify",
            title="Verify a transformation",
            description=(
                "Check whether `after` is an admissible transformation of `before` — whoever "
                "made it: a person, a language model, an agent or other software. The result is "
                "ACCEPTED (every protected item survived and every difference is accounted for), "
                "REFUSED (a protected item, term of art, or region PlainSpeak never rewrites was "
                "lost, added or changed) or INCONCLUSIVE (nothing protected was lost, but "
                "something changed that the integrity model cannot vouch for). It does NOT "
                "establish that two texts mean the same thing; INCONCLUSIVE is not a pass. "
                "Returns the versioned plainspeak.verify.v1 result with a deterministic receipt."
            ),
            input_schema=_schema(
                {"before": _text("The original text."),
                 "after": _text("The transformed text to check against the original."),
                 "format": _FORMAT},
                ["before", "after"],
            ),
            schema_id=VERIFY_SCHEMA,
            handler=lambda arguments: verify_text(
                arguments["before"], arguments["after"], markdown=_markdown(arguments)),
        ),
        Tool(
            name="diagnose",
            title="Diagnose a text (changes nothing)",
            description=(
                "Report everything PlainSpeak observes about a text and change nothing: the SAFE "
                "changes present would apply, suggestions that need a person, refused changes "
                "and why, style observations under the profile with their coverage (including "
                "where the text was too short to judge), the protected facts, and readability "
                "measurements. Returns the versioned plainspeak.diagnose.v1 result."
            ),
            input_schema=_schema(
                {"text": _text("The text to diagnose."), "profile": _PROFILE, "format": _FORMAT},
                ["text", "profile"],
            ),
            schema_id=DIAGNOSE_SCHEMA,
            handler=lambda arguments: diagnose_text(
                arguments["text"], arguments["profile"], markdown=_markdown(arguments)),
        ),
    )
}
