"""
Converts spoken punctuation/formatting phrases
(eg "open paren", "period", "new line") into literal characters.

Usable standalone against any .txt file, or imported by transcribe.py to clean API output.

CLI usage:
    python dictation_format.py path/to/raw_transcript.txt
    python dictation_format.py path/to/raw_transcript.txt --output path/to/cleaned.txt
    python dictation_format.py path/to/raw_transcript.txt --stdout
"""

import argparse
import re
import sys
from pathlib import Path


def _pat(p: str) -> re.Pattern:
    return re.compile(p, re.IGNORECASE)


# (pattern, symbol, before, after, capitalize_next)
#   before: 'strip' (remove space before symbol) | 'space' (force exactly one space before)
#   after:  'none' (attach directly to next word) | 'space' (force exactly one space) | 'natural' (leave as-is)
# Order matters where one phrase is a prefix of another (e.g. ellipsis vs. dot).
TOKENS = [
    (_pat(r"\b(dot\s+dot\s+dot|ellipsis)\b"), "...", "strip", "space", False),
    (_pat(r"\bapostrophe[\s-]?(ess|s)\b"), "'s", "strip", "natural", False),
    (_pat(r"\boptional\s+s\b"), "(s)", "strip", "natural", False),

    (_pat(r"\bperiod\b"), ".", "strip", "space", True),
    (_pat(r"\b(point|dot)\b"), ".", "strip", "none", False),

    (_pat(r"\b(open|left)\s+(paren|parenthesis)\b"), "(", "space", "none", False),
    (_pat(r"\b(close|right)\s+(paren|parenthesis)\b"), ")", "strip", "space", False),

    (_pat(r"\b(left(\s+square)?|open)\s+bracket\b"), "[", "space", "none", False),
    (_pat(r"\b(right(\s+square)?|close)\s+bracket\b"), "]", "strip", "space", False),

    (_pat(r"\b(open|left)\s+((curly\s+)?brace|curly\s+bracket)\b"), "{", "space", "none", False),
    (_pat(r"\b(close|right)\s+((curly\s+)?brace|curly\s+bracket)\b"), "}", "strip", "space", False),

    (_pat(r"\b(left\s+angle\s+bracket|less\s+than\s+sign|open\s+angle\s+bracket)\b"), "<", "space", "none", False),
    (_pat(r"\b(right\s+angle\s+bracket|greater\s+than\s+sign|close\s+angle\s+bracket)\b"), ">", "strip", "space", False),

    (_pat(r"\bexclamation\s+(mark|point)\b"), "!", "strip", "space", False),
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

    # Formatting terms beyond the punctuation table
    (_pat(r"\bnew\s+line\b"), "\n", "strip", "none", True),
    (_pat(r"\bindent\b"), "\t", "natural", "none", False),
]


def format_transcript(text: str) -> str:
    """Convert spoken punctuation/formatting phrases into literal characters."""
    out: list[str] = []
    i, n = 0, len(text)
    capitalize_next = False

    while i < n:
        matched = False
        for pattern, symbol, before, after, cap_next in TOKENS:
            m = pattern.match(text, i)
            if not m:
                continue

            if before in ("strip", "space"):
                while out and out[-1].isspace():
                    out.pop()
            if before == "space" and out:
                out.append(" ")

            out.append(symbol)
            i = m.end()

            if after in ("none", "space"):
                while i < n and text[i].isspace():
                    i += 1
            if after == "space":
                out.append(" ")

            if cap_next:
                capitalize_next = True

            matched = True
            break

        if matched:
            continue

        ch = text[i]
        if capitalize_next and ch.isalpha():
            out.append(ch.upper())
            capitalize_next = False
        else:
            out.append(ch)
        i += 1

    return "".join(out)


# ------------------------------------------------------------------------------------- #
# CLI entrypoint — run this module directly against any .txt file
# ------------------------------------------------------------------------------------- #

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RAW_DIR = SCRIPT_DIR / "outputs" / "raw"
DEFAULT_CLEANED_DIR = SCRIPT_DIR / "outputs" / "cleaned"


def _default_output_path(input_path: Path) -> Path:
    """outputs/raw/foo.raw_transcript.txt -> outputs/cleaned/foo.txt"""
    stem = input_path.stem
    if stem.endswith(".raw_transcript"):
        stem = stem[: -len(".raw_transcript")]
    return DEFAULT_CLEANED_DIR / f"{stem}.txt"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert spoken punctuation/formatting phrases in a transcript into literal characters."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help=f"Path to a raw transcript .txt file. If omitted, processes every .txt file "
             f"in {DEFAULT_RAW_DIR}.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write the cleaned transcript to. Defaults to outputs/cleaned/<name>.txt "
             "(with any '.raw_transcript' suffix stripped).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the cleaned transcript to stdout instead of writing a file.",
    )
    return parser


def _process_file(input_path: Path, output_arg: str | None, to_stdout: bool) -> None:
    if not input_path.is_file():
        sys.exit(f"Error: input file not found: {input_path}")

    raw_text = input_path.read_text(encoding="utf-8")
    cleaned_text = format_transcript(raw_text)

    if to_stdout:
        print(cleaned_text)
        return

    output_path = Path(output_arg) if output_arg else _default_output_path(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(cleaned_text, encoding="utf-8")
    print(f"Cleaned transcript written to: {output_path}")


def main() -> None:
    args = build_parser().parse_args()

    if args.input_file:
        _process_file(Path(args.input_file), args.output, args.stdout)
        return

    # No file given -> batch-process everything in outputs/raw/
    if args.output and not args.stdout:
        sys.exit("Error: --output can only be used with a single input_file, not in batch mode.")

    if not DEFAULT_RAW_DIR.is_dir():
        sys.exit(f"Error: default raw directory not found: {DEFAULT_RAW_DIR}")

    txt_files = sorted(DEFAULT_RAW_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {DEFAULT_RAW_DIR}")
        return

    for input_path in txt_files:
        _process_file(input_path, output_arg=None, to_stdout=args.stdout)


if __name__ == "__main__":
    main()