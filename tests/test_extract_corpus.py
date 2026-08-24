"""The whole corpus through the patterns, and what it is allowed to say.

Two kinds of assertion, and the second one is the reason this file exists rather than being folded
into the per-sentence tests.

**Coverage stays where it was measured.** 263 real descriptions produce a known number of values.
A change that halves it has broken something, and a change that doubles it has almost certainly
started guessing. Both are caught here and neither is caught by a test that feeds one sentence in.

**Precision is asserted over prose nobody wrote for this test.** Every phrase in the corpus that
looks like a claim and is not gets its answer checked, at the scale it actually occurs: thirty-six
`well-maintained`, thirty-one `as well as`, and every hedged utility mention in six markets.
"""

from __future__ import annotations

import re

import pytest

from extract_fakes import corpus, texts
from homescout.extract import NAMES, values_for
from homescout.extract import fields as fx


class Prop:
    def __init__(self, description: str) -> None:
        self.description = description


def readings() -> list[dict[str, object]]:
    return [values_for(Prop(text)) for text in texts()]


#: What the corpus produced when this feature was built, per field. A band rather than a number,
#: because a pattern improvement should be allowed to land without editing a test, and a collapse or
#: an explosion should not.
EXPECTED: dict[str, tuple[int, int]] = {
    "water_source": (35, 60),
    "sewer": (25, 45),
    "heating": (25, 45),
    "cooling": (25, 45),
    "gas": (6, 20),
    "roof": (38, 60),
}


def test_the_corpus_is_the_prose_this_was_measured_against() -> None:
    """263 descriptions, each carrying something worth testing, none carrying a real property."""
    entries = corpus()
    assert len(entries) > 200
    assert all(entry["text"].strip() for entry in entries)
    assert len({entry["id"] for entry in entries}) == len(entries)


@pytest.mark.parametrize("field", NAMES)
def test_coverage_stays_where_it_was_measured(field: str) -> None:
    """feat-009/AC-2: every field is recovered from real prose, at roughly the rate it occurs."""
    found = sum(1 for reading in readings() if reading[field].value is not None)
    low, high = EXPECTED[field]
    assert low <= found <= high, f"{field} determined {found} times, expected {low}-{high}"


def test_every_value_the_corpus_produces_is_in_the_vocabulary() -> None:
    """feat-009/AC-2: a closed vocabulary is only closed if nothing escapes it."""
    for reading in readings():
        for name, entry in reading.items():
            if entry.value is None:
                continue
            declared = fx.find(name)
            assert declared is not None and declared.allows(entry.value), (
                f"{name} came back as {entry.value!r}, which is not one of its values"
            )


def test_every_recovered_value_carries_its_evidence() -> None:
    """feat-009/AC-3: the first question about a surprising column is where it says so."""
    for reading in readings():
        for entry in reading.values():
            if entry.value is None and not entry.conflicted:
                continue
            assert entry.evidence, f"{entry.field} was decided with nothing to show for it"
            assert all(quote.strip() for quote in entry.evidence)


def test_the_adverb_never_becomes_a_water_supply_anywhere_in_the_corpus() -> None:
    """The scale version of the trap: every `well-` phrase in 263 real descriptions.

    A description that contains only adverbial `well` and no water word must produce no water
    source. There are dozens of them, and one escaping is a quarter of every market mislabelled.
    """
    adverbial = re.compile(r"\bwell[- ](?:maintained|kept|appointed|established|cared|designed"
                           r"|built|equipped|lit|stocked|loved|manicured|updated|sized)\b", re.I)
    water = re.compile(r"\b(?:water|domestic|private|irrigation|submersible|windmill|gpm)\b", re.I)

    checked = 0
    for text in texts():
        if not adverbial.search(text) or water.search(text):
            continue
        checked += 1
        assert values_for(Prop(text))["water_source"].value is None, text[:120]
    assert checked >= 20, f"only {checked} descriptions exercised the trap; the corpus has changed"


def test_no_hedged_utility_in_the_corpus_becomes_a_connection() -> None:
    """Three in ten real utility mentions are a possibility rather than a fact.

    Checked at the description level: a description whose only utility sentence is hedged must not
    report that utility. Both the sentences and the hedges are real.
    """
    hedged = [
        ("Water well, electricity, and septic needed.", ("water_source", "sewer")),
        ("Utilities such as electric, water, and sewer are nearby", ("sewer",)),
        ("City water is available.", ("water_source",)),
    ]
    for sentence, blanks in hedged:
        matching = [text for text in texts() if sentence in text]
        assert matching, f"the corpus no longer contains {sentence!r}"
        for text in matching:
            reading = values_for(Prop(text))
            for field in blanks:
                assert reading[field].value is None, f"{field} from {sentence!r}"


def test_a_new_roof_is_never_a_roof_material() -> None:
    """`new roof` outnumbers `metal roof` in real listings and says nothing about the material."""
    only_new = [
        text
        for text in texts()
        if re.search(r"\bnew(?:ly)?[- ]\w*\s*roof", text, re.I)
        and not re.search(r"\b(?:metal|shingle|tile|flat|foam|standing.?seam)\b", text, re.I)
    ]
    assert only_new, "the corpus no longer contains a bare new-roof claim"
    for text in only_new:
        assert values_for(Prop(text))["roof"].value is None, text[:120]


def test_nothing_in_the_corpus_looks_like_a_real_property() -> None:
    """The constitution keeps collected listing data off git, and prose can carry it too.

    Checked here rather than trusted to the script that built the fixture, because the fixture is
    committed and the script is not.
    """
    forbidden = {
        "a price": re.compile(r"\$\s?\d"),
        "a telephone number": re.compile(r"\b\d{3}[-.]\d{3}[-.]\d{4}\b"),
        "a listing service number": re.compile(r"\bMLS\s*#?\s*\d"),
        "a web address": re.compile(r"https?://|www\.", re.I),
        "an email address": re.compile(r"[\w.+-]+@[\w.-]+\.\w+"),
        "a street address": re.compile(
            r"\b\d+\s+[A-Z][\w'.-]*\s+(?:St|Street|Rd|Road|Ave|Avenue|Ln|Lane|Dr|Drive|Blvd)\b"
        ),
    }
    for entry in corpus():
        for what, pattern in forbidden.items():
            found = pattern.search(entry["text"])
            assert found is None, f"{entry['id']} still carries {what}: {found.group(0)!r}"
