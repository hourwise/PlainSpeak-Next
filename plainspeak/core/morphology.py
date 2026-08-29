"""Repairing the grammar that mechanical substitution breaks.

Replacing a word changes the text around it: "an application" becomes
"a **request**", and a replacement at the start of a sentence loses its
capital. These fixes are narrow and deterministic by design.
"""

import re


# Words that start with a vowel sound (for a/an correction)
# Comprehensive list including words starting with silent 'h'
VOWEL_SOUND_WORDS: set[str] = {
    # Vowel-starting
    "a", "able", "about", "above", "absolute", "abstract", "academic",
    "accept", "acceptable", "access", "accident", "account", "accurate",
    "achieve", "achievement", "acid", "acquire", "across", "act", "action",
    "active", "activity", "actual", "add", "addition", "additional",
    "address", "adequate", "adjust", "administration", "admit", "adopt",
    "adult", "advance", "advantage", "advertise", "advice", "affair",
    "affect", "afford", "afraid", "after", "afternoon", "again", "against",
    "age", "agency", "agent", "ago", "agree", "agreement", "ahead", "aid",
    "aim", "air", "aircraft", "airline", "airport", "alarm", "album",
    "alcohol", "alert", "alien", "alive", "all", "allocate", "allow",
    "almost", "alone", "along", "already", "also", "alter", "alternative",
    "although", "always", "amaze", "amount", "an", "analysis", "ancient",
    "anger", "angle", "angry", "animal", "announce", "annual", "another",
    "answer", "anxiety", "any", "anybody", "anymore", "anyone", "anything",
    "anyway", "anywhere", "apart", "apartment", "apparent", "appeal",
    "appear", "apple", "application", "apply", "appoint", "approach",
    "appropriate", "approve", "area", "argue", "argument", "arise", "arm",
    "army", "around", "arrange", "arrest", "arrival", "arrive", "arrow",
    "art", "article", "artist", "aside", "ask", "asleep", "aspect",
    "assault", "assess", "asset", "assign", "assist", "associate",
    "assume", "atmosphere", "attach", "attack", "attempt", "attend",
    "attention", "attitude", "attract", "audience", "author", "authority",
    "automatic", "autumn", "available", "average", "avoid", "awake",
    "award", "aware", "away", "awesome", "awful",
    # Silent 'h' words (vowel sound)
    "hour", "hourly", "honest", "honestly", "honesty", "honor", "honorable",
    "honorary", "heir", "heiress", "heirloom", "herb", "herbal",
    # Initialisms that start with vowel-sound letters
    "f", "h", "l", "m", "n", "r", "s", "x",
    "fbi", "fda", "lcd", "led", "mph", "mtv", "nfl", "nba", "nhl",
    "rpm", "suv", "x-ray",
    # Common words that start with vowels in different forms
    "easy", "easily", "east", "eastern", "eat", "economic", "economy",
    "edge", "edition", "editor", "educate", "education", "effect",
    "effective", "efficient", "effort", "egg", "eight", "either",
    "elderly", "elect", "election", "electric", "electronic", "element",
    "eleven", "else", "elsewhere", "emerge", "emergency", "emission",
    "emotion", "emotional", "emphasis", "empire", "employ", "employee",
    "employer", "empty", "enable", "encounter", "encourage", "end",
    "enemy", "energy", "enforce", "engage", "engine", "engineer",
    "enjoy", "enormous", "enough", "ensure", "enter", "enterprise",
    "entertainment", "entire", "entirely", "entrance", "entry",
    "environment", "episode", "equal", "equipment", "era", "error",
    "escape", "especially", "essay", "essential", "establish", "estate",
    "estimate", "evaluate", "even", "evening", "event", "eventually",
    "ever", "every", "everybody", "everyday", "everyone", "everything",
    "everywhere", "evidence", "evil", "exact", "exactly", "exam",
    "examination", "examine", "example", "exceed", "excellent", "except",
    "exception", "exchange", "excite", "excitement", "exciting", "exclude",
    "exclusive", "excuse", "execute", "executive", "exercise", "exhibit",
    "exhibition", "exist", "existence", "existing", "expand", "expansion",
    "expect", "expectation", "expense", "expensive", "experience",
    "experiment", "expert", "explain", "explanation", "explode",
    "explore", "explosion", "export", "expose", "exposure", "express",
    "expression", "extend", "extension", "extensive", "extent", "extra",
    "extraordinary", "extreme", "extremely", "eye",
    "ice", "idea", "ideal", "identify", "identity", "ignore", "ill",
    "illegal", "illness", "illustrate", "image", "imagination", "imagine",
    "immediate", "immediately", "immigrant", "immigration", "impact",
    "implement", "implication", "imply", "import", "importance",
    "important", "impose", "impossible", "impress", "impression",
    "impressive", "improve", "improvement", "incentive", "incident",
    "include", "including", "income", "increase", "increasingly",
    "incredible", "indeed", "independent", "indicate", "individual",
    "industrial", "industry", "infant", "infection", "inflation",
    "influence", "inform", "information", "initial", "initially",
    "initiative", "injury", "inner", "innocent", "innovation", "input",
    "inquiry", "inside", "insight", "insist", "inspect", "install",
    "instance", "instead", "institution", "instruction", "instrument",
    "insurance", "intellectual", "intelligence", "intend", "intense",
    "intention", "interaction", "interest", "interesting", "internal",
    "international", "internet", "interpret", "interpretation",
    "intervention", "interview", "introduce", "introduction", "invasion",
    "invent", "invest", "investigate", "investigation", "investigator",
    "investment", "investor", "invitation", "invite", "involve",
    "involved", "involvement", "iron", "irony", "island", "isolate",
    "isolated", "isolation", "issue",
    "object", "objection", "objective", "obligation", "observation",
    "observe", "observer", "obstacle", "obtain", "obvious", "obviously",
    "occasion", "occasionally", "occupy", "occur", "ocean", "odd",
    "odds", "offense", "offensive", "offer", "offering", "office",
    "officer", "official", "often", "oil", "old", "older", "once",
    "one", "ongoing", "online", "only", "onto", "open", "opening",
    "operate", "operating", "operation", "operator", "opinion",
    "opponent", "opportunity", "oppose", "opposite", "opposition",
    "option", "orange", "order", "ordinary", "organ", "organic",
    "organization", "organize", "orientation", "origin", "original",
    "originally", "other", "others", "otherwise", "ought", "outcome",
    "outer", "outlet", "output", "outside", "outstanding", "overcome",
    "overlook", "overseas", "owe", "own", "owner", "ownership",
    "ultimate", "ultimately", "umbrella", "unable", "uncle", "under",
    "undergo", "understand", "understanding", "undertake", "unemployment",
    "unexpected", "unfair", "unfold", "unfortunate", "unhappy", "uniform",
    "union", "unique", "unit", "unite", "united", "unity", "universal",
    "universe", "university", "unknown", "unless", "unlike", "unlikely",
    "until", "unusual", "up", "upon", "upper", "upset", "urban", "urge",
    "urgent", "usage", "use", "used", "useful", "user", "usual", "usually",
}


def _starts_with_vowel_sound(word: str) -> bool:
    """Check if a word starts with a vowel sound (for a/an determination)."""
    if not word:
        return False
    word_lower = word.lower().strip('*"\'.,;:!?()[]{}')
    if not word_lower:
        return False

    first = word_lower[0]
    # Consonant letters that can start vowel sounds (silent h words)
    if first == "h":
        return word_lower in VOWEL_SOUND_WORDS

    # Regular consonants -> consonant sound
    if first not in "aeiou":
        return False

    # Starts with a, e, i, o -> vowel sound
    if first in "aeio":
        return True

    # Starts with 'u' — tricky: 'u' can be vowel sound (umbrella, ugly)
    # or consonant 'yu' sound (useful, union, university)
    if len(word_lower) >= 2:
        second = word_lower[1]
        # 'u' + vowel = definite vowel sound (but this is rare: 'u' + vowel)
        if second in "aeiou":
            return True
        # Common 'yu' consonant-sound prefixes
        yu_prefixes = ("uni", "use", "usu", "ube", "uph", "uto", "uri", "uga")
        if word_lower.startswith(yu_prefixes):
            return False
        # Common vowel-sound 'u' prefixes
        vowel_u_prefixes = ("un", "um", "ur", "ug", "ul", "up", "ut", "us", "ud")
        if word_lower.startswith(vowel_u_prefixes):
            return True
        # Default for 'u' + consonant: assume vowel sound (umbrella, ugly, etc.)
        return True

    return True  # Single 'u' -> vowel sound ("U" as in "a U-turn" -> consonant, but rare)


def fix_articles(text: str) -> str:
    """
    Fix 'a'/'an' usage after word substitutions.

    Corrects patterns like 'a important' -> 'an important'
    and 'an useful' -> 'a useful'.
    """
    # Fix 'a' before vowel sound -> 'an'
    # Match 'a' (possibly inside **markers**) followed by a vowel-sound word
    result = text

    # Case 1: 'a **word**' where word starts with vowel sound
    pattern_a_marked = re.compile(
        r'\ba\b(\s+)(\*\*)([^*]+)(\*\*)',
        re.IGNORECASE,
    )

    def _fix_a_marked(match: re.Match) -> str:
        word = match.group(3)
        if _starts_with_vowel_sound(word):
            return "an" + match.group(1) + match.group(2) + word + match.group(4)
        return match.group(0)

    result = pattern_a_marked.sub(_fix_a_marked, result)

    # Case 2: 'a word' where word starts with vowel sound (not inside markers)
    pattern_a_plain = re.compile(
        r'\ba\b(\s+)([a-zA-Z][a-zA-Z]*)',
        re.IGNORECASE,
    )

    def _fix_a_plain(match: re.Match) -> str:
        word = match.group(2)
        if _starts_with_vowel_sound(word):
            return "an" + match.group(1) + word
        return match.group(0)

    result = pattern_a_plain.sub(_fix_a_plain, result)

    # Fix 'an' before consonant sound (not vowel sound) -> 'a'
    # This handles cases like 'an useful' -> 'a useful'
    pattern_an = re.compile(
        r'\ban\b(\s+)([a-zA-Z][a-zA-Z]*)',
        re.IGNORECASE,
    )

    def _fix_an(match: re.Match) -> str:
        word = match.group(2)
        if not _starts_with_vowel_sound(word):
            return "a" + match.group(1) + word
        return match.group(0)

    # Only apply 'an' -> 'a' fix for words NOT starting with vowel sound
    result = pattern_an.sub(_fix_an, result)

    return result


def fix_capitalization(text: str) -> str:
    """
    Ensure the first character of the text is capitalized,
    and the first character after sentence-ending punctuation is capitalized.
    """
    if not text:
        return text

    lines = text.split("\n")
    fixed_lines: list[str] = []

    for line in lines:
        if not line.strip():
            fixed_lines.append(line)
            continue

        # Split on sentence boundaries, keeping the delimiter
        parts = re.split(r'((?<=[.!?])\s+(?=[a-z]))', line)
        fixed_line = ""
        prev_was_delimiter = True  # Treat start of line as sentence start

        for i, part in enumerate(parts):
            if not part:
                fixed_line += part
                continue

            # Check if this is a whitespace delimiter
            if re.match(r'^\s+$', part):
                prev_was_delimiter = True
                fixed_line += part
                continue

            # This is a text part — capitalize if it starts a sentence
            if prev_was_delimiter and part and part[0].isalpha() and part[0].islower():
                part = part[0].upper() + part[1:]

            fixed_line += part
            prev_was_delimiter = False

        fixed_lines.append(fixed_line)

    return "\n".join(fixed_lines)


def post_process_simplified(text: str) -> str:
    """
    Apply all grammar-aware post-processing fixes to simplified text.

    These are lightweight heuristics that reduce common grammar issues
    introduced by mechanical word substitution. All fixes should be
    conservative — when in doubt, leave the text unchanged.

    Args:
        text: Simplified text (with **markers** for changed words).

    Returns:
        Text with grammar fixes applied.
    """
    result = text

    # Fix a/an article agreement
    result = fix_articles(result)

    # Fix capitalization
    result = fix_capitalization(result)

    return result
