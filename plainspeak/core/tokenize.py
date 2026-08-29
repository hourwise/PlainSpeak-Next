"""Splitting text into sentences, words and syllables.

Everything downstream is counted in these units, so a change here moves
every readability metric and every barrier offset at once.
"""

import re


# ── Text segmentation ──────────────────────────────────────────────────────

# Abbreviations that should not trigger sentence boundaries
ABBREVIATIONS: set[str] = {
    # Titles & honorifics
    "mr", "mrs", "ms", "miss", "dr", "prof", "rev", "hon", "st", "sr", "jr",
    "esq", "sir", "madam", "mx", "fr", "br", "hrh",
    # Military & professional ranks
    "capt", "col", "comdr", "gen", "gov", "lt", "maj", "sgt", "cpl", "adm",
    "cmdr", "ltcol", "bg", "mg", "lg", "pfc", "po", "cpt",
    # Academic degrees & certifications
    "ph.d", "phd", "md", "rn", "jd", "dds", "dvm", "edd", "psyd",
    "ba", "bs", "ma", "ms", "mfa", "mba", "mpa", "mph", "llb", "llm",
    "cpa", "cfa", "pe", "ra", "aia",
    # Business entities
    "inc", "ltd", "co", "corp", "llc", "llp", "plc", "pty", "bros",
    "assn", "assoc", "dept", "univ", "inst", "soc", "org",
    # Common Latin abbreviations
    "etc", "vs", "viz", "al", "et al", "ca", "cf", "ibid", "op cit",
    "loc cit", "et seq", "q.v", "s.v", "n.b",
    # Common English abbreviations
    "approx", "appt", "apt", "ave", "blvd", "bldg", "est", "temp",
    "mgr", "admin", "dept", "div", "ext", "fax", "tel", "ph",
    # Months
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec",
    # Time
    "a.m", "p.m", "am", "pm",
    # Countries/regions (common abbreviations)
    "u.s", "u.k", "u.s.a", "u.a.e", "e.u", "n.z",
    # Latin phrases
    "e.g", "i.e", "a.d", "b.c", "c.e", "b.c.e",
    # References & citations
    "no", "nos", "vol", "vols", "pp", "p", "ch", "ed", "eds",
    "fig", "figs", "eq", "eqs", "ref", "refs", "sec", "secs",
    "art", "arts", "para", "paras", "sch", "sched", "reg", "regs",
    # Units of measurement
    "kg", "lb", "lbs", "oz", "fl oz", "ml", "l", "gal", "qt", "pt",
    "cm", "m", "km", "mm", "in", "ft", "yd", "mi", "sq", "cu",
    "mph", "kph", "rpm", "psi", "v", "w", "kw", "mw", "hz", "khz",
    # States (US)
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga",
    "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md",
    "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
    "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc",
    "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy",
    # Additional common multi-word abbreviations
    "u.s", "u.k", "e.g", "i.e",
    # Ordinal indicators
    "st", "nd", "rd", "th",
}


def count_syllables(word: str) -> int:
    """
    Estimate the number of syllables in an English word.

    Uses the CMU Pronouncing Dictionary for known words (125,000+ entries,
    near-100% accuracy) and falls back to a pattern-based heuristic for
    unknown words (~85-95% accuracy).

    Returns at least 1 for any non-empty alphabetic string.
    """
    word = word.lower().strip()
    if not word or not word.isalpha():
        return 0

    # Special cases for very short words
    if len(word) <= 2:
        return 1

    # Try the CMU dictionary first (lazy-loaded, cached in memory)
    try:
        from .syllables import get_syllable_count
        syllable_dict = get_syllable_count()
        if word in syllable_dict:
            return syllable_dict[word]
    except (ImportError, FileNotFoundError):
        pass  # Fall back to heuristic if data file not available

    # Fall back to heuristic for words not in the dictionary
    return _count_syllables_heuristic(word)


def _count_syllables_heuristic(word: str) -> int:
    """
    Pattern-based syllable counter. Used as fallback when the CMU dictionary
    doesn't contain the word.
    """
    original = word

    # Check for -le and -les patterns BEFORE removing silent e
    # These form a syllable: table -> ta-ble, little -> lit-tle
    le_syllable = False
    if word.endswith("le") and len(word) > 2 and word[-3] not in "aeiouy":
        le_syllable = True
    if word.endswith("les") and len(word) > 3 and word[-4] not in "aeiouy":
        le_syllable = True

    # Remove silent e at end
    # But keep it if the word is short or the e is part of a vowel digraph
    if word.endswith("e") and len(word) > 3:
        # Don't remove if preceded by a vowel (e.g., 'see', 'bee', 'free')
        if word[-2] not in "aeiouy":
            word = word[:-1]

    # Count vowel groups
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False

    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel

    # Add syllable for -le pattern
    if le_syllable:
        count += 1

    # ed-endings: 'wanted', 'needed' keep the syllable, others lose it
    if original.endswith("ed") and len(original) > 3:
        if original[-3] in "dt":
            pass  # 'wanted', 'needed' — ed IS a syllable
        else:
            count = max(1, count - 1)

    return max(1, count)


def split_sentences(text: str) -> list[str]:
    """
    Split text into sentences using regex heuristics.

    Handles common abbreviations, decimal numbers, URLs, initials,
    numbered lists, and ellipses. Known limitations:
    - Some abbreviations not in ABBREVIATIONS set
    - Dialogue with complex punctuation
    - Lists with complex formatting

    Returns a list of sentence strings with whitespace stripped.
    """
    if not text:
        return []

    # Phase 1: Protect patterns that contain periods but are not
    # sentence boundaries.

    protected = text

    # 1a. Protect URLs and email addresses
    # Match http/https/ftp URLs and email addresses
    url_pattern = re.compile(
        r'(?:https?://|ftp://|www\.)[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE,
    )
    url_placeholders: dict[str, str] = {}
    url_counter = [0]

    def _protect_url(match: re.Match) -> str:
        key = f"__URL_{url_counter[0]}__"
        url_counter[0] += 1
        url_placeholders[key] = match.group(0)
        return key

    protected = url_pattern.sub(_protect_url, protected)

    # Also protect email addresses
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    email_placeholders: dict[str, str] = {}
    email_counter = [0]

    def _protect_email(match: re.Match) -> str:
        key = f"__EMAIL_{email_counter[0]}__"
        email_counter[0] += 1
        email_placeholders[key] = match.group(0)
        return key

    protected = email_pattern.sub(_protect_email, protected)

    # 1b. Protect decimal numbers (3.14, 99.9%, $5.00, etc.)
    protected = re.sub(r'(\d)\.(\d)', r'\1__DECIMAL__\2', protected)

    # 1c. Protect known abbreviations (longest first to avoid partial matches)
    for abbr in sorted(ABBREVIATIONS, key=len, reverse=True):
        # Match abbreviation followed by a period, at word boundaries
        pattern = re.compile(
            r'\b' + re.escape(abbr) + r'\.',
            re.IGNORECASE,
        )
        placeholder = f'__ABBR_{abbr.replace(".", "_").replace(" ", "_")}__'
        protected = pattern.sub(placeholder, protected)

    # 1d. Protect single-letter initials in names (J.K. Rowling, J. R. R. Tolkien)
    # Pattern: uppercase letter + period, possibly repeated with spaces
    # This is tricky; we target the common "X. X. Lastname" pattern
    initial_pattern = re.compile(
        r'\b([A-Z])\.(?=\s+[A-Z]\.)',
    )
    protected = initial_pattern.sub(r'\1__INITIAL__', protected)

    # Also protect single initial before surname: "J. Smith"
    initial_surname_pattern = re.compile(
        r'\b([A-Z])\.(?=\s+[A-Z][a-z])',
    )
    protected = initial_surname_pattern.sub(r'\1__INITIAL__', protected)

    # 1e. Protect ellipsis (...)
    protected = protected.replace('...', '__ELLIPSIS__')

    # 1f. Protect numbered list markers at start of line
    # Like "1." or "1.1" or "a." or "i." at the beginning of a line
    numbered_list_pattern = re.compile(
        r'(^|\n)\s*((?:\d+\.)+(?:\d+)?|[a-zA-Z]\.|\([a-zA-Z0-9]+\))\s*',
        re.MULTILINE,
    )
    list_placeholders: dict[str, str] = {}
    list_counter = [0]

    def _protect_list(match: re.Match) -> str:
        key = f'__LIST_{list_counter[0]}__'
        list_counter[0] += 1
        list_placeholders[key] = match.group(0)
        return key

    protected = numbered_list_pattern.sub(_protect_list, protected)

    # Phase 2: Split on structural boundaries first (paragraphs, list items)
    
    # 2a. Split on double newlines (paragraph/section breaks)
    paragraphs = re.split(r'\n\s*\n', protected)
    
    all_sentences = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 2b. Split on single newlines within paragraphs — treat each line
        # as a potential independent unit if it lacks terminal punctuation
        # or if the next line starts with a list marker / heading pattern
        lines = para.split('\n')
        if len(lines) <= 1:
            # Single-line paragraph — apply punctuation splitting
            all_sentences.append(para)
        else:
            # Multi-line paragraph — check each line
            merged = []
            for line in lines:
                line = line.strip()
                if not line:
                    if merged:
                        all_sentences.append(' '.join(merged))
                        merged = []
                    continue
                
                # Detect standalone lines: headings, list items, lines without
                # terminal punctuation that aren't clearly continuations
                is_standalone = False
                
                # Line starts with a list-like marker (bullet, number, letter)
                if re.match(r'^[\*\-\•\‣\◦\d+\.]\s', line):
                    is_standalone = True
                # Line is ALL CAPS or Title Case (likely a heading)
                elif line.isupper() and len(line.split()) <= 10:
                    is_standalone = True
                # Line ends with colon (heading introducing a list)
                elif line.rstrip().endswith(':'):
                    is_standalone = True
                # Line has no terminal punctuation and doesn't start lowercase
                elif not re.search(r'[.!?]$', line) and line[0].isupper():
                    is_standalone = True
                
                if is_standalone:
                    # Flush any accumulated non-standalone text
                    if merged:
                        all_sentences.append(' '.join(merged))
                        merged = []
                    # Standalone line becomes its own sentence
                    all_sentences.append(line)
                else:
                    merged.append(line)
            
            if merged:
                all_sentences.append(' '.join(merged))
    
    # 2c. Now apply punctuation-based splitting to each unit
    sentences = []
    for unit in all_sentences:
        unit = unit.strip()
        if not unit:
            continue
        # Split on [.!?] followed by whitespace and capital letter/number
        sub_sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', unit)
        for s in sub_sentences:
            s = s.strip()
            if s:
                sentences.append(s)
    
    # If no structural splits found, fall back to punctuation-only splitting
    if not sentences:
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', protected)

    # Phase 3: Restore protected patterns
    result = []
    for s in sentences:
        # Restore URLs
        for key, url in url_placeholders.items():
            s = s.replace(key, url)
        # Restore emails
        for key, email in email_placeholders.items():
            s = s.replace(key, email)
        # Restore decimal numbers
        s = s.replace('__DECIMAL__', '.')
        # Restore abbreviations
        for abbr in ABBREVIATIONS:
            placeholder = f'__ABBR_{abbr.replace(".", "_").replace(" ", "_")}__'
            s = s.replace(placeholder, abbr + '.')
        # Restore initials
        s = s.replace('__INITIAL__', '.')
        # Restore ellipsis
        s = s.replace('__ELLIPSIS__', '...')
        # Restore list markers
        for key, marker in list_placeholders.items():
            s = s.replace(key, marker)

        stripped = s.strip()
        if stripped:
            result.append(stripped)

    # If no splits found, treat the whole text as one sentence
    if not result:
        stripped = text.strip()
        if stripped:
            result = [stripped]

    return result


def split_words(text: str) -> list[str]:
    """Split text into words, keeping only alphabetic sequences."""
    return re.findall(r"[a-zA-Z]+", text.lower())


def count_complex_words(words: list[str], syllable_threshold: int = 3) -> int:
    """
    Count words with syllable_threshold or more syllables.
    Default threshold is 3 (standard for Gunning Fog and Flesch).
    """
    return sum(1 for w in words if count_syllables(w) >= syllable_threshold)
