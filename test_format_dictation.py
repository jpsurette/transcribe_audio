"""
Regression tests for format_dictation.format_transcript.

Run with:
    python -m unittest test_format_dictation

When a real dictation formats wrong, add its raw text and the output you expected to CASES.
Full transcripts live in test_fixtures/ as <name>.raw.txt with a matching <name>.expected.md.
The API punctuates the same audio differently between runs, so keep each run as its own fixture.
"""

import unittest
from pathlib import Path

from format_dictation import format_transcript

FIXTURES_DIR = Path(__file__).resolve().parent / "test_fixtures"

# (raw transcript, expected cleaned output)
CASES = [
    # Punctuation
    ("hello comma world period", "hello, world. "),
    ("call me open paren maybe close paren", "call me (maybe) "),
    ("Open parentheses close parentheses", "() "),

    # New line / paragraph (including punctuation the API inserts around commands)
    ("first new line second", "first\nSecond"),
    ("Testing, new line, new line. Starting", "Testing\n\nStarting"),
    ("one thought new paragraph another", "one thought\n\nAnother"),

    # Bullets, checkboxes, nesting
    ("new line hyphen buy milk", "\n-Buy milk"),
    ("bullet buy milk bullet eggs", "- Buy milk\n- Eggs"),
    ("Milk. Bullet. Eggs.", "Milk.\n- Eggs."),
    ("Groceries. Bullet point, milk. Bullet point, eggs.", "Groceries.\n- Milk.\n- Eggs."),
    ("bullet fruit new line indent bullet apples", "- Fruit\n\t- Apples"),
    ("checkbox call the bank", "- [ ] Call the bank"),

    # Headings
    ("heading one project notes new line body", "# Project notes\nBody"),
    ("intro heading two details", "intro\n## Details"),
    ("Heading 3, summary", "### Summary"),

    # Tags
    ("ideas hashtag project", "ideas #project"),
    ("ideas pound sign project", "ideas #project"),

    # Links
    ("see open link my note close link here", "see [[my note]] here"),
    ("see open bracket open bracket my note close bracket close bracket here", "see [[my note]] here"),
    ("new line open link daily close link", "\n[[Daily]] "),

    # Punctuation the API inserts around commands
    ("Open parentheses. Close parentheses. Left bracket. Right bracket.", "() [] "),
    ("Dot, dot, dot underscore", "..._"),
    ("New line, new line. Exclamation. New line", "\n\n!\n"),
    ("exclamation!", "! "),
    ("comma, slash", ",/"),
    ("Done. Period. Next", "Done. Next"),

    # Bold / highlight
    ("this is begin bold important end bold okay", "this is **important** okay"),
    ("a bold idea", "a bold idea"),
    ("note begin highlight key idea end highlight done", "note ==key idea== done"),
]


class FormatTranscriptTests(unittest.TestCase):
    def test_cases(self):
        for raw, expected in CASES:
            with self.subTest(raw=raw):
                self.assertEqual(format_transcript(raw), expected)

    def test_fixtures(self):
        raw_files = sorted(FIXTURES_DIR.glob("*.raw.txt"))
        self.assertTrue(raw_files, f"No fixtures found in {FIXTURES_DIR}")
        for raw_path in raw_files:
            expected_path = raw_path.with_name(raw_path.name.replace(".raw.txt", ".expected.md"))
            with self.subTest(fixture=raw_path.name):
                self.assertEqual(
                    format_transcript(raw_path.read_text(encoding="utf-8")),
                    expected_path.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
