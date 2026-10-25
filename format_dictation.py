"""
Converts spoken punctuation/formatting phrases
(eg "open paren", "period", "new line") into literal characters.

Usable standalone against any .txt file, or imported by transcribe.py to clean API output.

CLI usage:
    python format_dictation.py path/to/raw_transcript.txt
    python format_dictation.py path/to/raw_transcript.txt --output path/to/cleaned.txt
    python format_dictation.py path/to/raw_transcript.txt --stdout
    python format_dictation.py path/to/raw_transcript.txt --format txt
"""

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from config import CLEANED_DIR, GLOSSARY_PATH, RAW_DIR


# The API inserts its own punctuation between the words of a spoken command
# ("Dot, dot, dot", "new line. New line"), so word gaps in patterns allow it.
WORD_GAP = r"[\s,.;:!?]+"


def _pat(p: str) -> re.Pattern:
    return re.compile(p.replace(r"\s+", WORD_GAP), re.IGNORECASE)


# (pattern, symbol, before, after, capitalize_next)
#   before: 'strip' (remove spaces before symbol) | 'space' (force exactly one space before)
#           | 'line' (strip spaces and start a new line if not already at one) | 'natural' (leave as-is)
#   after:  'none' (attach directly to next word) | 'space' (force exactly one space) | 'natural' (leave as-is)
# Only spaces are stripped, never newlines or tabs produced by earlier commands.
# Punctuation the API inserted around a command is dropped (see format_transcript).
# Order matters where one phrase is a prefix of another (e.g. ellipsis vs. dot).
TOKENS = [
    # Line structure (Markdown / Obsidian)
    (_pat(r"\bnew\s+paragraph\b"), "\n\n", "strip", "none", True),
    (_pat(r"\bnew\s+line\b"), "\n", "strip", "none", True),
    (_pat(r"\bcheck\s*box\b"), "- [ ] ", "line", "none", True),
    (_pat(r"\bbullet(\s+point)?\b"), "- ", "line", "none", True),
    (_pat(r"\bheading\s+(one|1)\b"), "# ", "line", "none", True),
    (_pat(r"\bheading\s+(two|2)\b"), "## ", "line", "none", True),
    (_pat(r"\bheading\s+(three|3)\b"), "### ", "line", "none", True),
    (_pat(r"\bindent\b"), "\t", "natural", "none", False),

    # Obsidian inline syntax
    (_pat(r"\bhash\s*tag\b"), "#", "space", "none", False),
    (_pat(r"\b(open|begin)\s+link\b"), "[[", "space", "none", False),
    (_pat(r"\b(close|end)\s+link\b"), "]]", "strip", "space", False),
    (_pat(r"\b(begin|start)\s+bold\b"), "**", "space", "none", False),
    (_pat(r"\bend\s+bold\b"), "**", "strip", "space", False),
    (_pat(r"\b(begin|start)\s+highlight\b"), "==", "space", "none", False),
    (_pat(r"\bend\s+highlight\b"), "==", "strip", "space", False),

    (_pat(r"\b(dot\s+dot\s+dot|ellipsis)\b"), "...", "strip", "space", False),
    (_pat(r"\bapostrophe[\s-]?(ess|s)\b"), "'s", "strip", "natural", False),
    (_pat(r"\boptional\s+s\b"), "(s)", "strip", "natural", False),

    (_pat(r"\bperiod\b"), ".", "strip", "space", True),
    (_pat(r"\bdot\b"), ".", "strip", "none", False),

    (_pat(r"\b(open|left)\s+(paren|parenthesis|parentheses)\b"), "(", "space", "none", False),
    (_pat(r"\b(close|right)\s+(paren|parenthesis|parentheses)\b"), ")", "strip", "space", False),

    (_pat(r"\b(left(\s+square)?|open)\s+bracket\b"), "[", "space", "none", False),
    (_pat(r"\b(right(\s+square)?|close)\s+bracket\b"), "]", "strip", "space", False),

    (_pat(r"\b(open|left)\s+((curly\s+)?brace|curly\s+bracket)\b"), "{", "space", "none", False),
    (_pat(r"\b(close|right)\s+((curly\s+)?brace|curly\s+bracket)\b"), "}", "strip", "space", False),

    (_pat(r"\b(left\s+angle\s+bracket|less\s+than\s+sign|open\s+angle\s+bracket)\b"), "<", "space", "none", False),
    (_pat(r"\b(right\s+angle\s+bracket|greater\s+than\s+sign|close\s+angle\s+bracket)\b"), ">", "strip", "space", False),

    (_pat(r"\bexclamation(\s+(mark|point))?\b"), "!", "strip", "space", False),
    (_pat(r"\bquestion\s+mark\b"), "?", "strip", "space", False),

    (_pat(r"\b(begin|open)\s+(double\s+)?(quote|quotes)\b"), '"', "space", "none", False),
    (_pat(r"\b(end|close)\s+(double\s+)?(quote|quotes)\b"), '"', "strip", "space", False),
    (_pat(r"\b(begin|open)\s+single\s+quote\b"), "'", "space", "none", False),
    (_pat(r"\b(end|close)\s+single\s+quote\b"), "'", "strip", "space", False),

    (_pat(r"\bcolon\b"), ":", "strip", "space", False),
    (_pat(r"\bsemicolon\b"), ";", "strip", "space", False),

    (_pat(r"\b(pound|number)\s+sign\b"), "#", "space", "none", False),
    (_pat(r"\bdollar\s+sign\b"), "$", "space", "none", False),
    (_pat(r"\bpercent\s+sign\b"), "%", "strip", "space", False),
    (_pat(r"\b(and\s+sign|ampersand)\b"), "&", "space", "space", False),
    (_pat(r"\bat\s+sign\b"), "@", "strip", "none", False),
    (_pat(r"\bcopyright\s+sign\b"), "©", "space", "space", False),
    (_pat(r"\bregistered\s+sign\b"), "®", "space", "space", False),
    (_pat(r"\bsection\s+sign\b"), "§", "space", "space", False),
    (_pat(r"\bcaret\b"), "^", "strip", "none", False),
    (_pat(r"\bapostrophe\b"), "'", "strip", "none", False),
    (_pat(r"\basterisk\b"), "*", "strip", "none", False),
    (_pat(r"\bplus\s+sign\b"), "+", "space", "space", False),
    (_pat(r"\bcomma\b"), ",", "strip", "space", False),
    (_pat(r"\bback\s*slash\b"), "\\", "strip", "none", False),
    (_pat(r"\b(forward\s+)?slash\b"), "/", "strip", "none", False),
    (_pat(r"\bunderscore\b"), "_", "strip", "none", False),
    (_pat(r"\bdash\b"), "--", "space", "space", False),
    (_pat(r"\b(hyphen|minus\s+sign)\b"), "-", "strip", "none", False),
    (_pat(r"\bequal\s+sign\b"), "=", "space", "space", False),
    (_pat(r"\bvertical\s+bar\b"), "|", "space", "space", False),

]

LINE_BREAKS = ("\n", "\t")
OPENERS = ("(", "[", "{", "[[")
API_PUNCTUATION = ",.;:!?"
JOINER_PUNCTUATION = ",;:"


# ------------------------------------------------------------------------------------- #
# Numbers and dates — run before the token pass
# ------------------------------------------------------------------------------------- #
# Number words only become digits inside a number expression (numbers joined by a spoken
# dash/slash/colon/dot) or a "date" command, so ordinary speech ("one thought") is untouched.

UNITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
WORD_VALUES = (
    {w: i for i, w in enumerate(UNITS)}
    | {w: i + 10 for i, w in enumerate(TEENS)}
    | {w: (i + 2) * 10 for i, w in enumerate(TENS)}
)

_NUM_WORD = (
    rf"\b(?:(?:{'|'.join(TENS)})(?:[\s-]+(?:{'|'.join(UNITS[1:])}))?"
    rf"|{'|'.join(TEENS)}|{'|'.join(UNITS)}|hundred|thousand)\b"
)
NUM = rf"(?:\b\d+\b|{_NUM_WORD}(?:\s+{_NUM_WORD})*)"

NUMBER_JOINERS = {"dash": "-", "hyphen": "-", "slash": "/", "colon": ":", "dot": "."}
# Spoken joiner (API punctuation allowed around it), or a literal - / : touching a digit.
_SPOKEN_JOINER = r"[\s,.;]*\b(dash|hyphen|(?:forward\s+)?slash|colon|dot)\b[\s,.;]*"
_LITERAL_JOINER = r"((?<=\d)[-/:]|[-/:](?=\d))"
JOINER = rf"(?:{_SPOKEN_JOINER}|{_LITERAL_JOINER})"

NUMBER_EXPRESSION_RE = re.compile(rf"{NUM}(?:{JOINER}{NUM})+", re.IGNORECASE)
DATE_RE = re.compile(
    rf"\bdate[\s,.:]+(?:(?P<today>today)\b|(?P<parts>{NUM}(?:(?:{JOINER}|[\s,.]+){NUM})*))",
    re.IGNORECASE,
)
FILENAME_DATE_RE = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)")


def _number_chunks(text: str) -> list[tuple[int, int]]:
    """Parse digits and number words into (value, end offset) chunks.

    "twenty six" -> [26], "two thousand twenty six" -> [2026], "twenty twenty six" -> [20, 26]
    """
    chunks: list[tuple[int, int]] = []
    can_add = 0  # the last chunk absorbs a following value smaller than this
    for m in re.finditer(r"\d+|[a-z]+", text, re.IGNORECASE):
        token = m.group().lower()
        if token.isdigit():
            chunks.append((int(token), m.end()))
            can_add = 0
        elif token in ("hundred", "thousand") and chunks:
            scale = 100 if token == "hundred" else 1000
            chunks[-1] = (chunks[-1][0] * scale, m.end())
            can_add = scale
        elif token in WORD_VALUES:
            value = WORD_VALUES[token]
            if chunks and value < can_add:
                chunks[-1] = (chunks[-1][0] + value, m.end())
            else:
                chunks.append((value, m.end()))
            can_add = 10 if value >= 20 and value % 10 == 0 else 0
    return chunks


def _number_to_digits(text: str) -> str:
    if text.strip().isdigit():
        return text.strip()  # keep as written, e.g. the leading zero in "05"
    return "".join(str(value) for value, _ in _number_chunks(text))


def _convert_number_expression(m: re.Match) -> str:
    parts = re.split(JOINER, m.group(), flags=re.IGNORECASE)
    # re.split returns [num, spoken, literal, num, spoken, literal, num, ...]
    out = _number_to_digits(parts[0])
    for i in range(1, len(parts), 3):
        spoken, literal, number = parts[i], parts[i + 1], parts[i + 2]
        joiner = literal or NUMBER_JOINERS[spoken.lower().split()[-1]]
        out += joiner + _number_to_digits(number)
    return out


def _convert_date(m: re.Match, recorded_on: date | None) -> str:
    if m.group("today"):
        return recorded_on.isoformat() if recorded_on else m.group()

    parts = m.group("parts")
    chunks = _number_chunks(parts)
    values = [value for value, _ in chunks]
    if len(values) >= 3 and values[0] >= 1000:
        (year, month, day), used = values[:3], 3
    elif len(values) >= 4 and 10 <= values[0] <= 99 and values[1] <= 99:
        year, month, day, used = values[0] * 100 + values[1], values[2], values[3], 4
    else:
        return m.group()

    try:
        iso = date(year, month, day).isoformat()
    except ValueError:
        return m.group()
    leftover = parts[chunks[used - 1][1]:]
    return iso + leftover


def date_from_filename(name: str) -> date | None:
    """Recording date from a YYYYMMDD timestamp in a filename, e.g. 20261025_1407.m4a."""
    m = FILENAME_DATE_RE.search(name)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def convert_numbers(text: str, recorded_on: date | None = None) -> str:
    """Apply "date" commands, then turn number expressions into digits."""
    text = DATE_RE.sub(lambda m: _convert_date(m, recorded_on), text)
    return NUMBER_EXPRESSION_RE.sub(_convert_number_expression, text)



# ------------------------------------------------------------------------------------- #
# Glossary — fix known misspellings of specialist terms, run before everything else
# ------------------------------------------------------------------------------------- #
# File format, one term per line:
#     Canonical Spelling: misspelling, other misspelling
# Matching is whole-word and case-insensitive; spaces and hyphens in a variant match either.
# The canonical spelling is matched too, so its capitalization is always normalized.
# Blank lines and lines starting with # are ignored. See glossary.example.txt.

@dataclass
class Glossary:
    pattern: re.Pattern
    replacements: dict[str, str]  # normalized variant -> canonical spelling

    def apply(self, text: str) -> str:
        return self.pattern.sub(lambda m: self.replacements[_normalize_term(m.group())], text)


def _normalize_term(term: str) -> str:
    return re.sub(r"[\s-]+", " ", term.strip().lower())


def parse_glossary(text: str) -> Glossary | None:
    replacements: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        canonical, _, variants = line.partition(":")
        canonical = canonical.strip()
        for term in [canonical, *variants.split(",")]:
            if term.strip():
                replacements[_normalize_term(term)] = canonical
    if not replacements:
        return None

    # Longest first so "de la riva" wins over a shorter overlapping entry.
    alternatives = [
        r"[\s-]+".join(re.escape(word) for word in variant.split())
        for variant in sorted(replacements, key=len, reverse=True)
    ]
    pattern = re.compile(rf"\b(?:{'|'.join(alternatives)})\b", re.IGNORECASE)
    return Glossary(pattern, replacements)


def load_glossary(path: Path | None) -> Glossary | None:
    """Load a glossary file; returns None if there is no file (the glossary is optional)."""
    if path is None or not path.is_file():
        return None
    return parse_glossary(path.read_text(encoding="utf-8"))


def format_transcript(text: str, recorded_on: date | None = None, glossary: Glossary | None = None) -> str:
    """Convert spoken punctuation/formatting phrases into literal characters.

    recorded_on fills in "date today"; without it that phrase is left as spoken.
    glossary, if given, corrects known misspellings before any other formatting.
    """
    if glossary:
        text = glossary.apply(text)
    text = convert_numbers(text, recorded_on)

    # Each chunk is (text, from_command) so punctuation the API inserted can be told apart
    # from symbols produced by spoken commands.
    out: list[tuple[str, bool]] = []
    i, n = 0, len(text)
    capitalize_next = False

    def last() -> str:
        return out[-1][0] if out else ""

    def strip_spaces() -> None:
        while out and out[-1][0] == " ":
            out.pop()

    while i < n:
        matched = False
        for pattern, symbol, before, after, cap_next in TOKENS:
            m = pattern.match(text, i)
            if not m:
                continue

            # Drop API-inserted punctuation just before the command. Line-level commands
            # keep sentence enders (.!?) since a sentence often legitimately ends there.
            structural = before == "line" or symbol.startswith(LINE_BREAKS)
            droppable = JOINER_PUNCTUATION if structural else API_PUNCTUATION
            if before != "natural" or structural:
                strip_spaces()
                while out and not out[-1][1] and out[-1][0] in droppable:
                    out.pop()
                    strip_spaces()

            if before in ("strip", "space", "line"):
                strip_spaces()
            if before == "space" and out and not last().endswith(LINE_BREAKS + OPENERS):
                out.append((" ", False))
            if before == "line" and out and not last().endswith(LINE_BREAKS):
                out.append(("\n", True))

            out.append((symbol, True))
            i = m.end()

            # Drop API-inserted punctuation (and spacing) just after the command.
            if after in ("none", "space"):
                while i < n and (text[i].isspace() or text[i] in API_PUNCTUATION):
                    i += 1
            if after == "space":
                out.append((" ", False))

            if cap_next:
                capitalize_next = True

            matched = True
            break

        if matched:
            continue

        ch = text[i]
        if capitalize_next and ch.isalpha():
            out.append((ch.upper(), False))
            capitalize_next = False
        else:
            out.append((ch, False))
        i += 1

    return "".join(chunk for chunk, _ in out)


# ------------------------------------------------------------------------------------- #
# CLI entrypoint — run this module directly against any .txt file
# ------------------------------------------------------------------------------------- #

def _default_output_path(input_path: Path, cleaned_dir: Path, file_format: str) -> Path:
    """raw/foo.raw_transcript.txt -> cleaned_dir/foo.<file_format>"""
    stem = input_path.stem
    if stem.endswith(".raw_transcript"):
        stem = stem[: -len(".raw_transcript")]
    return cleaned_dir / f"{stem}.{file_format}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert spoken punctuation/formatting phrases in a transcript into literal characters."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Path to a raw transcript .txt file. If omitted, processes every .txt file "
             "in --raw-dir.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the cleaned transcript to. Defaults to <cleaned-dir>/<name>.<format> "
             "(with any '.raw_transcript' suffix stripped).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the cleaned transcript to stdout instead of writing a file.",
    )
    parser.add_argument(
        "--format",
        choices=["md", "txt"],
        default="md",
        help="File type for the cleaned transcript when --output isn't given (default: md).",
    )
    parser.add_argument(
        "--glossary",
        type=Path,
        default=GLOSSARY_PATH,
        help=f"Glossary of term spellings to correct (default: {GLOSSARY_PATH}; skipped if missing)",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=RAW_DIR,
        help=f"Directory of raw transcripts for batch mode (default: {RAW_DIR})",
    )
    parser.add_argument(
        "--cleaned-dir",
        type=Path,
        default=CLEANED_DIR,
        help=f"Directory to write cleaned transcripts to (default: {CLEANED_DIR})",
    )
    return parser


def _process_file(
    input_path: Path,
    output_arg: str | None,
    to_stdout: bool,
    cleaned_dir: Path,
    file_format: str,
    glossary: Glossary | None,
) -> None:
    if not input_path.is_file():
        sys.exit(f"Error: input file not found: {input_path}")

    raw_text = input_path.read_text(encoding="utf-8")
    cleaned_text = format_transcript(raw_text, date_from_filename(input_path.name), glossary)

    if to_stdout:
        print(cleaned_text)
        return

    output_path = Path(output_arg) if output_arg else _default_output_path(input_path, cleaned_dir, file_format)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(cleaned_text, encoding="utf-8")
    print(f"Cleaned transcript written to: {output_path}")


def main() -> None:
    args = build_parser().parse_args()
    raw_dir = args.raw_dir.expanduser()
    cleaned_dir = args.cleaned_dir.expanduser()
    glossary = load_glossary(args.glossary.expanduser())

    if args.input_file:
        _process_file(Path(args.input_file), args.output, args.stdout, cleaned_dir, args.format, glossary)
        return

    # No file given -> batch-process everything in outputs/raw/
    if args.output and not args.stdout:
        sys.exit("Error: --output can only be used with a single input_file, not in batch mode.")

    if not raw_dir.is_dir():
        sys.exit(f"Error: raw directory not found: {raw_dir}")

    txt_files = sorted(raw_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {raw_dir}")
        return

    for input_path in txt_files:
        _process_file(input_path, output_arg=None, to_stdout=args.stdout, cleaned_dir=cleaned_dir, file_format=args.format, glossary=glossary)


if __name__ == "__main__":
    main()