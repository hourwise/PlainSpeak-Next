"""Deterministic analysis and transformation.

Nothing in this package knows how it is being called. The CLI, the desktop
application and the MCP server are all adapters over the functions here, so
that no interface can drift into having its own rewriting behaviour.
"""


