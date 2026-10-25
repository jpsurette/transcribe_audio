"""
Regression tests for format_dictation.format_transcript.

Run with:
    python -m unittest test_format_dictation

When a real dictation formats wrong, add its raw text and the output you expected to CASES.
"""

import unittest

from format_dictation import format_transcript

# (raw transcript, expected cleaned output)
CASES = [
    # Punctuation
    ("hello comma world period", "hello, world. "),
    ("call me open paren maybe close paren", "call me (maybe) "),
    ("Open parentheses close parentheses", "() "),

    # New line / paragraph (including punctuation the API inserts around commands)
    ("first new line second", "first\nSecond"),
    ("Testing, new line, new line. Starting", "Testing,\n\nStarting"),
    ("one thought new paragraph another", "one thought\n\nAnother"),

    # Bullets, checkboxes, nesting
    ("new line hyphen buy milk", "\n-Buy milk"),
    ("bullet buy milk bullet eggs", "- Buy milk\n- Eggs"),
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


if __name__ == "__main__":
    unittest.main()
