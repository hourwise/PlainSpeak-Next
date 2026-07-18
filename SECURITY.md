# Security

## Threat assumptions

PlainSpeak is a local, offline text analysis tool. Its threat model is fundamentally different from networked applications.

### Trust boundaries

1. **Input text** — The user provides text to analyze. This text is untrusted in the sense that it may contain any content, but it is processed entirely in the user's own environment.
2. **Output report** — The HTML report is written to the user's filesystem. If shared, the report contains the full analyzed text.
3. **No network boundary** — The tool makes no network requests. There is no client-server boundary to protect.

### What we protect against

- **Command injection via input text.** Text passed to the tool should never result in arbitrary code execution.
- **HTML injection in reports.** User-provided text must be properly escaped when embedded in HTML output.
- **Path traversal.** File output paths must be validated to prevent writing outside intended directories.

### What we do not protect against

- **Malicious input designed to consume excessive resources.** A multi-gigabyte input could exhaust memory. We do not currently impose input size limits (see LIMITATIONS.md).
- **The user's own system.** If the user's machine is compromised, PlainSpeak provides no additional protection.

## Sensitive data handling

- **No data collection.** PlainSpeak does not collect, transmit, or store any user data outside the user's own filesystem.
- **No telemetry.** There is no analytics, no usage reporting, no crash reporting.
- **No caching.** Analyzed text exists only in memory during processing and in the output file if the user chooses to save it.
- **Output file security.** The HTML report inherits the filesystem permissions of the directory it is written to. Users should be aware that the report contains their full text.

## Authentication and authorization

Not applicable. PlainSpeak is a local CLI tool with no multi-user functionality.

## Dependency risks

### Direct dependencies (planned)
- `click` (BSD-3-Clause): Well-maintained, widely used. Low risk.

### Transitive dependencies
- None if `click` is the only dependency (click has no dependencies of its own).

### Supply-chain mitigations
- Pin dependency versions in requirements files.
- Document dependency hashes for verification.
- Prefer minimal dependency footprint.

## Abuse cases

### Misleading use of readability scores
A readability score (e.g., "Grade 8") could be used to claim a document is accessible when it is not. Automated metrics do not guarantee comprehension. The tool's output includes a warning about this limitation.

### Over-reliance on automated suggestions
A user might apply all simplification suggestions without reviewing them, potentially changing meaning. The tool's output includes guidance that suggestions should be reviewed by a human.

### Use for high-stakes documents
If PlainSpeak is used to "simplify" legal contracts, medical instructions, or safety-critical information, errors could cause harm. The tool is not designed or validated for these use cases. This is documented in LIMITATIONS.md.

## Reporting guidance

Security issues can be reported via the repository's issue tracker. Since this is an experiment with a limited 24-hour development window, formal security response processes are not established.

## Security work remaining

- [ ] Input size limits to prevent memory exhaustion
- [ ] Fuzz testing with malformed input
- [ ] Dependency hash verification in setup
- [ ] Formal escaping audit of HTML output
- [ ] Consider sandboxing for HTML report viewing
