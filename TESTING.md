# Testing

## How the project is tested

### Automated tests
- **Unit tests** for each module: analyzer (readability metrics), simplifier (pattern matching), glossary (term lookup), reporter (HTML generation).
- **Known-answer tests** for readability metrics. We use manually scored text samples with pre-computed Flesch-Kincaid, Flesch Reading Ease, Gunning Fog, and SMOG scores to verify calculation correctness.
- **Property-based tests** where appropriate (e.g., syllable count should never be negative, sentence count should match known segmentations).
- **HTML output validation** to verify the generated report is well-formed and contains expected elements.

### Manual testing
- Running the CLI against real-world text samples (government documents, medical disclaimers, Terms of Service excerpts).
- Visual inspection of HTML reports in multiple browsers.
- Verification that the HTML report passes automated accessibility checks (using axe-core or similar).

## What the tests establish

- That readability metrics are computed correctly against known reference values.
- That sentence segmentation works for common patterns.
- That the HTML report is well-formed and escapes user input properly.
- That the CLI accepts expected arguments and produces output files.

## What the tests do not establish

- That the tool improves actual human comprehension of text.
- That simplification suggestions are contextually appropriate.
- That the syllable counter is accurate for all English words.
- That the tool works correctly for non-English text.
- Performance characteristics for large documents.
- Accessibility with real assistive technology.

## How to reproduce validation

```bash
# Clone and install
git clone <repo>
cd plainspeak
pip install -e .

# Run tests
python -m pytest tests/ -v

# Run on sample text
plainspeak analyze examples/legal_sample.txt --output report.html

# Open report in browser and inspect
```

## Known test gaps

1. **No integration tests** that exercise the full pipeline end-to-end beyond CLI invocation.
2. **No performance/load tests.**
3. **No accessibility automation in CI** (axe-core not integrated).
4. **No cross-platform CI** — tests run only on the development machine.
5. **Limited edge case coverage** for sentence segmentation (abbreviations, ellipses, dialogue, lists).
6. **No regression test suite** for HTML output formatting.
7. **Syllable counter tested only on a curated word list**, not on a representative corpus.

## Test data

Test samples are synthetic or drawn from publicly available documents. No personal, confidential, or copyrighted text is used in tests without appropriate licensing.
