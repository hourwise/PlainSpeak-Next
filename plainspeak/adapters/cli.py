"""
Command-line interface for PlainSpeak.

Provides the `plainspeak` command with subcommands for analyzing
text readability and generating reports.
"""

import sys
from pathlib import Path
from typing import Optional

import click

from .. import __version__
from ..core.barriers import SimplificationResult, analyze_simplification
from ..core.metrics import analyze
from ..reporting.console import format_console_report
from ..reporting.html import generate_report
from ..pipeline import rules_api
from ..pipeline import (
    ERROR_EMPTY_INPUT,
    ERROR_UNREADABLE_INPUT,
    ERROR_UNSUPPORTED_INPUT,
    FORMAT_MARKDOWN,
    FORMAT_TEXT,
    UNSUPPORTED_MESSAGE,
    PresentError,
    ReviewError,
    is_reviewable_path,
    load_reviewable,
    parse_source,
)
from ..pipeline import present as present_document
from ..pipeline import explain_profile as profile_detail
from ..pipeline import plan_style_changes
from ..pipeline.sources import load_document
from ..pipeline import list_profiles
from ..reporting.json import generate_json


#: A leading blank line. Written via chr() rather than as an escape so the
#: literal survives any tooling that rewrites escape sequences in source.
BLANK = chr(10)



@click.group()
@click.version_option(version=__version__, prog_name="PlainSpeak")
def main():
    """
    PlainSpeak — A readability analysis and text simplification toolkit.

    Helps you understand how readable your writing is and what you can
    do to make it clearer. All processing is local and offline.

    Examples:

        plainspeak analyze document.txt

        plainspeak analyze document.txt --output report.html

        plainspeak analyze --stdin < document.txt
    """
    pass


@main.command()
@click.argument("file", type=click.Path(exists=True), required=False)
@click.option(
    "--stdin", "from_stdin", is_flag=True,
    help="Read text from standard input instead of a file.",
)
@click.option(
    "--output", "-o", type=click.Path(), default=None,
    help="Write HTML report to the specified file.",
)
@click.option(
    "--json", "-j", "json_output", type=click.Path(), default=None,
    help="Write JSON report to the specified file.",
)
@click.option(
    "--no-simplify", is_flag=True,
    help="Skip simplification analysis (faster, but no suggestions).",
)
@click.option(
    "--console", "-c", is_flag=True,
    help="Print a console-friendly report instead of HTML.",
)
def analyze_cmd(
    file: Optional[str],
    from_stdin: bool,
    output: Optional[str],
    json_output: Optional[str],
    no_simplify: bool,
    console: bool,
):
    """
    Analyze the readability of a text file or stdin.

    FILE is the path to a text file to analyze. If not provided,
    use --stdin to read from standard input.
    """
    # Get input text
    if from_stdin:
        text = sys.stdin.read()
        source = "stdin"
    elif file:
        # Try the multi-format reader first (supports .txt, .docx, .pdf, .html, .md)
        try:
            from ..pipeline.sources import read_text_source as read_auto
            text, source_format = read_auto(file)
            source = f"{file} ({source_format})"
        except ImportError:
            # reader module not available, fall back to plain text
            try:
                text = Path(file).read_text(encoding="utf-8")
                source = file
            except UnicodeDecodeError:
                try:
                    text = Path(file).read_text(encoding="latin-1")
                    source = file
                except Exception as e:
                    click.echo(f"Error: Cannot read file '{file}': {e}", err=True)
                    sys.exit(1)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Supported formats: .txt, .md, .docx, .pdf, .html", err=True)
            sys.exit(1)
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
        except Exception as e:
            # Fall back to plain text reading
            try:
                text = Path(file).read_text(encoding="utf-8")
                source = file
            except UnicodeDecodeError:
                try:
                    text = Path(file).read_text(encoding="latin-1")
                    source = file
                except Exception as e2:
                    click.echo(f"Error: Cannot read file '{file}': {e2}", err=True)
                    sys.exit(1)
    else:
        click.echo(
            "Error: Please provide a file or use --stdin. "
            "Run 'plainspeak analyze --help' for usage.",
            err=True,
        )
        sys.exit(1)

    if not text.strip():
        click.echo("Error: Input text is empty.", err=True)
        sys.exit(1)

    # Run readability analysis
    try:
        readability = analyze(text)
    except ValueError as e:
        click.echo(f"Error analyzing text: {e}", err=True)
        sys.exit(1)

    # Run simplification analysis (unless skipped)
    simplification: Optional[SimplificationResult] = None
    if not no_simplify:
        simplification = analyze_simplification(text)

    # Generate output
    if console or (not output and not console):
        # Console output
        report_text = format_console_report(readability, simplification)
        click.echo(report_text)

    if output:
        # HTML output
        html_report = generate_report(readability, simplification, text)
        try:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_report, encoding="utf-8")
            click.echo(f"\nHTML report written to: {output_path.absolute()}")
        except OSError as e:
            click.echo(f"Error writing report to '{output}': {e}", err=True)
            sys.exit(1)

    if json_output:
        # JSON output
        json_report = generate_json(readability, simplification, text)
        try:
            json_path = Path(json_output)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json_report, encoding="utf-8")
            click.echo(f"\nJSON report written to: {json_path.absolute()}")
        except OSError as e:
            click.echo(f"Error writing JSON to '{json_output}': {e}", err=True)
            sys.exit(1)


@main.command()
@click.argument("text", required=False)
@click.option(
    "--stdin", "from_stdin", is_flag=True,
    help="Read text from standard input.",
)
def score(text: Optional[str], from_stdin: bool):
    """
    Quick readability scoring — print scores only.

    TEXT is the text to score. Use --stdin to read from stdin.
    """
    if from_stdin:
        text = sys.stdin.read()
    elif not text:
        click.echo("Error: Provide text or use --stdin.", err=True)
        sys.exit(1)

    if not text.strip():
        click.echo("Error: Empty input.", err=True)
        sys.exit(1)

    try:
        scores = analyze(text)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Words:              {scores.total_words}")
    click.echo(f"Sentences:          {scores.total_sentences}")
    click.echo(f"Avg Sentence Length: {scores.avg_sentence_length:.1f}")
    click.echo(f"Flesch Reading Ease: {scores.flesch_reading_ease:.1f}")
    click.echo(f"Flesch-Kincaid:      {scores.flesch_kincaid_grade:.1f}")
    click.echo(f"Gunning Fog:         {scores.gunning_fog_index:.1f}")
    click.echo(f"SMOG:                {scores.smog_index:.1f}")
    click.echo(f"Consensus Grade:     {scores.consensus_grade_level:.1f}")
    click.echo(f"Level:               {scores.reading_level_description}")


# ── Presenting: the governed, non-interactive transformation ──────────────

#: What `--format` may ask for. `json` is the versioned machine contract; the
#: other three are for people and pipes, and carry no guarantee about layout.
PRESENT_FORMATS = ("json", "text", "marked", "summary")


def _read_present_input(path: Optional[str], from_stdin: bool, input_format: Optional[str]):
    """Resolve the input to a `Document`, or raise `PresentError` with a code.

    Standard input is parsed as Markdown unless told otherwise, because Markdown
    parsing is the more conservative of the two: it keeps code, quotes, tables
    and link destinations out of reach.
    """
    if from_stdin:
        text = sys.stdin.read()
        markdown = (input_format or FORMAT_MARKDOWN) == FORMAT_MARKDOWN
        if not text.strip():
            raise PresentError(ERROR_EMPTY_INPUT, "the input is empty")
        return parse_source(text, markdown=markdown), FORMAT_MARKDOWN if markdown else FORMAT_TEXT

    if input_format is not None:
        raise click.UsageError(
            "--input-format applies to --stdin only; a file is parsed according to its extension"
        )
    if not is_reviewable_path(path):
        raise PresentError(ERROR_UNSUPPORTED_INPUT, UNSUPPORTED_MESSAGE)
    try:
        document = load_reviewable(path)
    except (ReviewError, OSError, UnicodeDecodeError) as error:
        raise PresentError(ERROR_UNREADABLE_INPUT, f"cannot read {path}: {error}") from None
    fmt = FORMAT_TEXT if Path(path).suffix.lower() == ".txt" else FORMAT_MARKDOWN
    return document, fmt


def _render_present(result, fmt: str) -> str:
    if fmt == "json":
        return result.to_json()
    if fmt == "text":
        return result.text
    if fmt == "marked":
        return result.marked_text()
    return _present_summary(result)


def _present_summary(result) -> str:
    identity = result.bundle.identities()
    lines = [
        f"PlainSpeak present — profile {result.bundle.profile_id}, "
        f"ruleset {identity['ruleset_version']} ({identity['ruleset_sha256'][:12]})",
        f"input {result.bundle.input_hash[:16]}  output {result.preview.output_hash[:16]}"
        + ("" if result.changed else "  (unchanged)"),
        "",
        f"Applied automatically (SAFE): {len(result.applied)}",
    ]
    lines += [f"  {item.before!r} -> {item.after!r}  [{item.rule_id}]" for item in result.applied]
    lines.append(f"Awaiting a person (REVIEW, not applied): {len(result.review)}")
    lines += [f"  {item.before!r} -> {item.after!r}  [{item.rule_id}]" for item in result.review]
    lines.append(f"Refused (REFUSED, never applied): {len(result.refused)}")
    lines += [f"  {item.before!r}: {item.refusal}" for item in result.refused]
    diagnostics = result.bundle.diagnostics()
    lines.append(f"Style observations under {result.bundle.profile_id}: {len(diagnostics)}")
    lines += [f"  [{item.severity}] {item.message}" for item in diagnostics]
    return BLANK.join(lines) + BLANK


def _write_new_file(destination: str, content: str, overwrite: bool, source: Optional[str]) -> None:
    """Write `content` to `destination` atomically and conservatively.

    Refuses to replace an existing file unless told to, and refuses outright to
    replace the input: presenting a document never destroys it.
    """
    target = Path(destination)
    if source is not None and target.resolve() == Path(source).resolve():
        raise click.UsageError("--output is the input file; PlainSpeak never overwrites its input")
    if target.exists() and not overwrite:
        raise click.UsageError(f"{target} already exists; pass --overwrite to replace it")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".plainspeak-partial")
    try:
        with open(partial, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        partial.replace(target)
    finally:
        if partial.exists():
            partial.unlink()


def _run_present(path, from_stdin, profile_id, fmt, input_format, output, overwrite) -> None:
    if bool(path) == bool(from_stdin):
        raise click.UsageError("give exactly one input: a PATH or --stdin")
    try:
        document, detected = _read_present_input(path, from_stdin, input_format)
        result = present_document(document, profile_id, input_format=detected)
    except PresentError as error:
        if fmt == "json":
            click.echo(error.to_json(), nl=False)
        click.echo(f"Error ({error.code}): {error.message}", err=True)
        sys.exit(1)

    rendered = _render_present(result, fmt)
    if output:
        _write_new_file(output, rendered, overwrite, path)
        click.echo(f"Wrote {fmt} to {Path(output)}", err=True)
    else:
        click.echo(rendered, nl=False)


_PRESENT_OPTIONS = (
    click.argument("path", type=click.Path(exists=True, dir_okay=False), required=False),
    click.option("--stdin", "from_stdin", is_flag=True, help="Read the text from standard input."),
    click.option(
        "--profile", "profile_id", required=True,
        help="Profile to present under: natural, plain, technical, government or academic. No default.",
    ),
    click.option(
        "--input-format", type=click.Choice([FORMAT_MARKDOWN, FORMAT_TEXT]), default=None,
        help="How to parse --stdin (default markdown). A file is parsed according to its extension.",
    ),
    click.option(
        "--output", "-o", type=click.Path(dir_okay=False), default=None,
        help="Write to this file instead of standard output.",
    ),
    click.option(
        "--overwrite", is_flag=True,
        help="Allow --output to replace an existing file. Never the input.",
    ),
)


def _with_present_options(function):
    for decorator in reversed(_PRESENT_OPTIONS):
        function = decorator(function)
    return function


@main.command()
@_with_present_options
@click.option(
    "--format", "fmt", type=click.Choice(PRESENT_FORMATS), default="json", show_default=True,
    help="json: the versioned plainspeak.present.v1 contract. text: the presented document "
         "only. marked: the document with applied changes in **asterisks**. summary: a "
         "readable account of what happened.",
)
def present(path, from_stdin, profile_id, input_format, output, overwrite, fmt):
    """Present a document: apply every SAFE change, and nothing else.

    Every change passes the integrity firewall. Style suggestions that need a
    person are reported and left unapplied; review them in plainspeak-desktop.
    The input file is never written.

    Exit status: 0 presented; 1 the input could not be presented (with --format
    json, standard output carries the error code); 2 invalid usage.
    """
    _run_present(path, from_stdin, profile_id, fmt, input_format, output, overwrite)


@main.command()
@_with_present_options
def simplify(path, from_stdin, profile_id, input_format, output, overwrite):
    """Deprecated: use `plainspeak present --format marked`.

    Prints the presented document with applied changes in **asterisks**. It
    runs the governed pipeline — rules, integrity firewall, profiles — exactly
    as `present` does. The inherited substitution engine this command once
    used is no longer reachable from the command line.
    """
    click.echo("Note: `simplify` is deprecated; use `plainspeak present --format marked`.", err=True)
    _run_present(path, from_stdin, profile_id, "marked", input_format, output, overwrite)


@main.command()
@click.option(
    "--host", default="127.0.0.1",
    help="Host to bind to (default: 127.0.0.1).",
)
@click.option(
    "--port", "-p", type=int, default=5100,
    help="Port to listen on (default: 5100).",
)
@click.option(
    "--no-open", is_flag=True,
    help="Don't automatically open the browser.",
)
def web(host: str, port: int, no_open: bool):
    """
    Start the local web interface.

    Its "Simplified Text" is the governed presentation — the same operation as
    `plainspeak present`, under the Natural profile: SAFE changes only, every
    one through the integrity firewall. Use `plainspeak-desktop` to review style
    suggestions.

    Opens a browser-based readability analyzer that runs entirely
    on your computer. No data is ever sent anywhere.

    Install web dependencies with: pip install plainspeak[web]
    """
    try:
        from .web import create_app
    except ImportError:
        click.echo(
            "Error: Flask is required for the web interface.\n"
            "Install it with: pip install plainspeak[web]\n"
            "Or: pip install flask",
            err=True,
        )
        sys.exit(1)

    import webbrowser

    app = create_app()

    click.echo(f"\n  PlainSpeak Web v{__version__}")
    click.echo("  ─────────────────────────────")
    click.echo(f"  Starting local server at: http://{host}:{port}")
    click.echo("  All analysis runs offline on your computer.")
    click.echo("  No data is ever sent anywhere.")
    click.echo("  Press Ctrl+C to stop.\n")

    if not no_open:
        webbrowser.open(f"http://{host}:{port}")

    app.run(host=host, port=port, debug=False)


@main.group()
def rules():
    """Inspect the declarative ruleset.

    Read-only. Applying rules to a document is not exposed here yet: the engine
    is new, and a destructive command should wait until it has been used in
    anger. Tests drive the pipeline directly in the meantime.
    """


@rules.command("list")
@click.option("--mode", type=click.Choice(["safe-fix", "diagnostic", "protected"]), default=None,
              help="Show only rules of one mode.")
def rules_list(mode: Optional[str]):
    """List the bundled rules."""
    loaded = rules_api.ruleset()
    described = [item for item in rules_api.all_rules(loaded) if mode is None or item.mode == mode]

    click.echo(f"Ruleset {loaded.version}  ({loaded.hash[:12]})")
    click.echo(f"{len(described)} of {len(loaded)} rules" + BLANK)
    for item in described:
        click.echo(f"  {item.id:18} {item.mode:11} {item.name}")
        click.echo(f"  {'':18} {item.reason}")


@rules.command("explain")
@click.argument("rule_id")
def rules_explain(rule_id: str):
    """Explain one rule, by ID. For example: PS.CLARITY.001"""
    try:
        item = rules_api.rule(rule_id.upper())
    except KeyError:
        raise click.ClickException(
            f"No rule with ID {rule_id!r}. Run 'plainspeak rules list' to see them all."
        )

    click.echo(f"{item.id} v{item.version}  {item.name}")
    click.echo(f"  Mode        {item.mode}")
    click.echo(f"  Family      {item.family}")
    click.echo(f"  Matches     {item.matches}")
    click.echo(f"  Proposes    {item.proposes}")
    click.echo(f"  Where       {', '.join(item.scope_include)}"
               + (f" (not {', '.join(item.scope_exclude)})" if item.scope_exclude else ""))
    click.echo(f"  Priority    {item.priority}")
    click.echo(f"  Why         {item.reason}")
    click.echo(f"  {item.description}")
    click.echo(BLANK + "  Should match:")
    for example in item.examples_positive:
        click.echo(f"    + {example}")
    click.echo("  Should not match:")
    for example in item.examples_negative:
        click.echo(f"    - {example}")
    if item.examples_transform:
        click.echo("  Produces:")
        for before, after in item.examples_transform:
            click.echo(f"    {before}")
            click.echo(f"      -> {after}")
    click.echo(f"  Source      {item.provenance_source}")
    if item.provenance_reference:
        click.echo(f"  Reference   {item.provenance_reference}")
    click.echo(f"  Licence     {item.provenance_licence}")


@main.group()
def profiles():
    """Inspect the style profiles.

    Read-only, and deliberately so. A profile decides how a measurement is
    interpreted for a kind of prose; it proposes no edits, and there is no
    command here that changes a document. `plainspeak fix --profile` does not
    exist and will not until style transformation has been designed on its own
    terms.
    """


@profiles.command("list")
def profiles_list():
    """List the built-in style profiles."""
    described = list_profiles()
    click.echo(f"{len(described)} built-in profiles" + BLANK)
    for item in described:
        moved = sum(1 for value in item["diagnostics"].values() if value["differs_from_baseline"])
        click.echo(f"  {item['id']:12} {item['name']}")
        click.echo(f"  {'':12} {item['description']}")
        click.echo(
            f"  {'':12} {moved} of {len(item['diagnostics'])} diagnostics differ from "
            f"the baseline; {len(item['weakly_calibrated'])} weakly calibrated"
        )
        click.echo(f"  {'':12} {item['sha256'][:12]}" + BLANK)


@profiles.command("explain")
@click.argument("profile_id")
def profiles_explain(profile_id: str):
    """Explain one profile, by ID. For example: technical"""
    try:
        item = profile_detail(profile_id.lower())
    except ValueError as error:
        # `ProfileError` subclasses ValueError. Caught by the base type because
        # an adapter may not import `style`, and the layering test enforces it.
        raise click.ClickException(str(error))

    click.echo(f"{item['id']} v{item['version']}  {item['name']}")
    click.echo(f"  {item['description']}")
    click.echo(BLANK + f"  For          {item['target_use']}")
    click.echo(f"  Provenance   {item['provenance']}")
    click.echo(f"  Identity     {item['sha256']}")
    click.echo(f"  Pack         {item['profile_pack_sha256'][:12]}")
    click.echo(f"  Style policy {item['style_policy_version']}")

    moved = {k: v for k, v in item["diagnostics"].items() if v["differs_from_baseline"]}
    click.echo(BLANK + f"  Differs from the baseline on {len(moved)} diagnostics:")
    for key, value in moved.items():
        click.echo(
            f"    {key.split('.')[-1]:28} {value['notice']} / {value['strong']}"
            f"  (baseline {value['baseline_notice']} / {value['baseline_strong']})"
        )
        if value["minimum_sample"] != value["baseline_minimum_sample"]:
            click.echo(
                f"    {'':28} needs {value['minimum_sample']} samples, not "
                f"{value['baseline_minimum_sample']}"
            )
        click.echo(f"    {'':28} {value['provenance']}")

    if item["targets"]:
        click.echo(BLANK + "  Target ranges (descriptive, not findings):")
        for metric, target in item["targets"].items():
            click.echo(f"    {metric:34} {target['min']} to {target['max']}  ({target['provenance']})")

    if item["disabled"]:
        click.echo(BLANK + f"  Disabled: {', '.join(item['disabled'])}")

    if item["weakly_calibrated"]:
        click.echo(BLANK + "  Weakly calibrated — no document on one side of the line:")
        for key in item["weakly_calibrated"]:
            click.echo(f"    {key}")


@main.group()
def style():
    """Preview profile-governed style suggestions.

    Read-only. Every suggestion here requires human review by design, and there
    is deliberately no command that applies one — `plainspeak style fix` does not
    exist. A style preference becoming an automatic edit is exactly what this
    part of the engine is built to prevent, and a CLI flag would be the easiest
    place to lose that.
    """


@style.command("preview")
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--profile", "profile_id", required=True,
              help="Which style profile to read the document against. No default.")
def style_preview(path: str, profile_id: str):
    """Show the style changes a profile would suggest, and change nothing."""
    try:
        document = load_document(Path(path))
        plan = plan_style_changes(document, profile_id.lower())
    except ValueError as error:
        raise click.ClickException(str(error))

    click.echo(f"{Path(path).name}  profile {plan.profile_id} v{plan.profile_version}")
    click.echo(f"  ruleset {plan.ruleset_version} ({plan.ruleset_hash[:12]})")
    click.echo(f"  plan    {plan.plan_hash[:16]}" + BLANK)

    if plan.findings:
        click.echo("  Style findings under this profile:")
        for finding in plan.findings:
            click.echo(
                f"    {finding['id'].split('.')[-1]:28} {finding['severity']:8} "
                f"{finding['value']} (line {finding['threshold']})"
            )
        click.echo("")

    reviewable = plan.review_required
    if not reviewable:
        click.echo("  No style changes suggested.")
    else:
        click.echo(f"  {len(reviewable)} suggestion(s), all requiring review:" + BLANK)
        for item in reviewable:
            click.echo(f"    {item.proposal_id}  {item.rule_id}")
            click.echo(f"      before   {item.before!r}")
            click.echo(f"      after    {item.after!r}")
            click.echo(f"      because  {item.reason}")
            click.echo(f"      trigger  {item.trigger_diagnostic} ({item.trigger_severity})")
            click.echo(f"      integrity {'checked' if item.integrity_checked else 'not checked'}")
            click.echo("")

    if plan.refused:
        click.echo(f"  {len(plan.refused)} suggestion(s) refused:")
        for item in plan.refused:
            click.echo(f"    {item.rule_id} at {item.location}: {item.refusal}")

    if plan.truncated:
        click.echo(BLANK + "  Some suggestions were not shown:")
        for key, count in sorted(plan.truncated.items()):
            click.echo(f"    {key}: {count} beyond the per-diagnostic cap")

    click.echo(BLANK + "  Nothing was changed. Applying a style suggestion needs an "
                       "explicit review decision, which this command cannot make.")


@main.command()
def version():
    """Print version information."""
    click.echo(f"PlainSpeak v{__version__}")
    click.echo("A readability analysis and text simplification toolkit.")
    click.echo("License: MIT")


if __name__ == "__main__":
    main()
