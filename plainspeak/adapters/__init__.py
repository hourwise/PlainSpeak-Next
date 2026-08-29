"""Interfaces onto the engine.

An adapter translates between the outside world and `plainspeak.core`. It
must never contain analysis or rewriting logic of its own: the whole point
of the split is that the CLI, the desktop application and the MCP server
cannot give different answers for the same input.
"""
