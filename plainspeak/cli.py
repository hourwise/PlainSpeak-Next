"""
Command-line interface for PlainSpeak.

Provides the `plainspeak` command with subcommands for analyzing
text readability and generating reports.
"""

import sys
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .analyzer import analyze, ReadabilityScores
from .simplifier import analyze_simplification, SimplificationResult
from .reporter import generate_report, format_console_report


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
        try:
            text = Path(file).read_text(encoding="utf-8")
            source = file
        except UnicodeDecodeError:
            # Try with other common encodings
            try:
                text = Path(file).read_text(encoding="latin-1")
                source = file
            except Exception as e:
                click.echo(f"Error: Cannot read file '{file}': {e}", err=True)
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


@main.command()
def version():
    """Print version information."""
    click.echo(f"PlainSpeak v{__version__}")
    click.echo("A readability analysis and text simplification toolkit.")
    click.echo("License: MIT")


if __name__ == "__main__":
    main()
