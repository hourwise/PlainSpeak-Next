# PlainSpeak

**A readability analysis and text simplification toolkit.**

PlainSpeak helps you understand how readable your writing is — and what you can do to make it clearer.

## What it does

- **Measures readability** using Flesch-Kincaid Grade Level, Flesch Reading Ease, Gunning Fog Index, and SMOG Index.
- **Identifies barriers** to comprehension: passive voice, long sentences, complex words, nominalizations, and jargon.
- **Suggests plain-language alternatives** from a built-in glossary of over 200 common jargon terms.
- **Generates accessible HTML reports** that explain each finding in plain language — the report itself is designed to be readable.

## What problem it addresses

Every day, people encounter text they cannot understand: medical instructions, legal notices, government forms, terms of service. Complex language creates barriers that disproportionately affect people with lower literacy, non-native speakers, people with cognitive disabilities, and elderly people.

PlainSpeak gives writers and advocates a free, offline tool to check whether text is accessible — and to understand why it might not be.

## Who it is for

- **Public service writers** checking whether forms and notices are understandable.
- **Healthcare communicators** creating patient-facing materials.
- **Educators** preparing accessible learning resources.
- **Legal aid organizations** explaining rights and processes.
- **Anyone** who wants their writing to be understood by more people.

## What currently works

✅ **Working prototype.** The core toolkit is functional and tested.

- [x] Problem selection and mission definition
- [x] Repository structure and documentation
- [x] Readability metric computation (6 metrics)
- [x] Text pattern analysis (7 barrier types)
- [x] Plain-language suggestion engine (300+ terms)
- [x] HTML report generation (WCAG 2.1 AA-targeted)
- [x] CLI interface (analyze, score, version commands)
- [x] Test suite (113 tests, all passing)

## How to run it

```bash
pip install -e .
plainspeak analyze my_document.txt --output report.html
```

## How to test it

```bash
python -m pytest tests/ -v
```

## What remains incomplete

See [LIMITATIONS.md](LIMITATIONS.md) for a full accounting of known gaps. Key items:

- English-only; no internationalization.
- No empirical validation with human readers.
- Heuristic accuracy limits (~90% syllable counting).
- HTML report not tested with real screen readers.

## Principal limitations

1. **Readability formulas are proxies**, not direct measures of comprehension.
2. **Suggestions are rule-based**, not context-aware — they must be reviewed by a human.
3. **English only.** The metrics and patterns are language-specific.
4. **CLI-only interface** may exclude some intended beneficiaries.
5. **Not validated** for legal, medical, or safety-critical documents.

## License

MIT — see [LICENSE](LICENSE) file.

## Contributing

This is an experimental project built within a constrained 24-hour window. Contributions, forks, and continuations are welcome. Start with [MISSION.md](MISSION.md) to understand the project's purpose and [DECISIONS.md](DECISIONS.md) for the rationale behind major choices.

Repository: [github.com/hourwise/Project-PlainSpeak](https://github.com/hourwise/Project-PlainSpeak)
