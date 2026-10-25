"""
Regression tests for format_dictation.format_transcript.

Run with:
    python -m unittest test_format_dictation

When a real dictation formats wrong, add its raw text and the output you expected to CASES.
Full transcripts live in test_fixtures/ as <name>.raw.txt with a matching <name>.expected.md.
The API punctuates the same audio differently between runs, so keep each run as its own fixture.
"""

import unittest
from datetime import date
from pathlib import Path

from format_dictation import date_from_filename, format_transcript, load_glossary, parse_glossary

FIXTURES_DIR = Path(__file__).resolve().parent / "test_fixtures"
FIXTURE_GLOSSARY = load_glossary(FIXTURES_DIR / "glossary.txt")

GLOSSARY = parse_glossary("""
# comment lines and blank lines are ignored

Omoplata: omoplatte, omo plata
De la Riva: della riva, de la reeva
Kimura
""")

# (raw transcript, expected cleaned output) with GLOSSARY applied
GLOSSARY_CASES = [
    ("omoplatte class", "Omoplata class"),
    ("OMOPLATTE", "Omoplata"),
    ("omo plata and omo-plata", "Omoplata and Omoplata"),
    ("omoplata", "Omoplata"),
    ("della riva guard", "De la Riva guard"),
    ("from de la reeva", "from De la Riva"),
    ("kimura grip", "Kimura grip"),
    ("omoplattes", "omoplattes"),
    ("hashtag omoplatte", "#Omoplata"),
    ("omoplatte period", "Omoplata. "),
]

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

    # Number expressions
    ("2026 dash, ten dash, 20, class", "2026-10-20, class"),
    ("pages 5 dash 10", "pages 5-10"),
    ("a dash of salt", "a -- of salt"),
    ("ten slash 20", "10/20"),
    ("three point five", "three point five"),
    ("three dot five", "3.5"),
    ("key point", "key point"),
    ("meet at ten colon thirty", "meet at 10:30"),
    ("twenty-six dash thirty", "26-30"),
    ("fifty hyphen fifty", "50-50"),
    ("one hundred twenty dash two hundred", "120-200"),
    ("code 007 dash 12", "code 007-12"),
    ("one thought", "one thought"),
    ("1-2-3", "1-2-3"),
    ("one, two, three.", "one, two, three."),
    ("file dot txt", "file.txt"),

    # Date command
    ("date 2026 10 20", "2026-10-20"),
    ("date twenty twenty six, ten, twenty", "2026-10-20"),
    ("date two thousand twenty six dash ten dash five", "2026-10-05"),
    ("date 2026 10 20 two people", "2026-10-20 two people"),
    ("date 2026 13 40", "date 2026 13 40"),
    ("up to date", "up to date"),
    ("date today", "date today"),  # no recording date available

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

    def test_glossary(self):
        for raw, expected in GLOSSARY_CASES:
            with self.subTest(raw=raw):
                self.assertEqual(format_transcript(raw, glossary=GLOSSARY), expected)

    def test_no_glossary(self):
        self.assertEqual(format_transcript("omoplatte class"), "omoplatte class")
        self.assertIsNone(parse_glossary("# only comments\n\n"))
        self.assertIsNone(load_glossary(FIXTURES_DIR / "does_not_exist.txt"))

    def test_date_today(self):
        recorded = date(2026, 10, 25)
        self.assertEqual(format_transcript("date today", recorded), "2026-10-25")
        self.assertEqual(format_transcript("open link date today close link", recorded), "[[2026-10-25]] ")

    def test_date_from_filename(self):
        self.assertEqual(date_from_filename("20261025_1407.m4a"), date(2026, 10, 25))
        self.assertEqual(date_from_filename("20261025_1407.raw_transcript.txt"), date(2026, 10, 25))
        self.assertIsNone(date_from_filename("punctuation_experiment.MP3"))
        self.assertIsNone(date_from_filename("20261399_0000.m4a"))

    def test_fixtures(self):
        raw_files = sorted(FIXTURES_DIR.glob("*.raw.txt"))
        self.assertTrue(raw_files, f"No fixtures found in {FIXTURES_DIR}")
        for raw_path in raw_files:
            expected_path = raw_path.with_name(raw_path.name.replace(".raw.txt", ".expected.md"))
            with self.subTest(fixture=raw_path.name):
                self.assertEqual(
                    format_transcript(
                        raw_path.read_text(encoding="utf-8"), date_from_filename(raw_path.name), FIXTURE_GLOSSARY
                    ),
                    expected_path.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
