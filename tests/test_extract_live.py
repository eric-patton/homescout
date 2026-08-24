"""The one question only a real model can answer: does the request shape still work?

Marked slow and skipped unless the environment names a model, so it costs nothing on a machine that
has not configured one and nothing in the default suite. Everything else about this feature is
proved offline, which is what keeps the suite fast and keeps the tool from spending somebody's
credit to check itself.

Point it at whatever you have. `HOMESCOUT_EXTRACT_BASE_URL=http://localhost:1234/v1` with LM Studio
running costs nothing at all and proves the same thing, which is the whole point of AC-9.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from homescout.extract import NAMES, read_prose
from homescout.extract.model import ask
from homescout.extract.settings import ExtractionMisconfigured, account, pacing
from homescout.sources import default_session

pytestmark = pytest.mark.slow

#: Deliberately plain, deliberately unambiguous, and deliberately not from the corpus: what is being
#: checked is that the request shape works and the answer parses, not that a model is clever.
PLAIN = (
    "Comfortable three bedroom home on two acres just outside town. The property is served by a "
    "private well and has its own septic system. A durable metal roof was installed in 2021, and "
    "the house is heated and cooled by a central heat and air system."
)

NOTHING = (
    "Charming two bedroom cottage within walking distance of the square. Fresh paint throughout, "
    "new flooring in the living areas, and a fenced back garden with mature fruit trees."
)


def live_account():
    root = Path.cwd()
    try:
        return account(root, os.environ)
    except ExtractionMisconfigured as exc:
        pytest.skip(f"no model configured: {exc}")


def live_session():
    return default_session(config=pacing())


def test_the_configured_model_answers_the_shape_this_client_sends() -> None:
    """feat-009/AC-9: one client, whatever backend the environment names."""
    answer = ask(live_session(), live_account(), read_prose(PLAIN), NAMES)

    assert answer.values, f"nothing came back; rejections were {answer.rejected}"
    # Not asserting every field: which ones a given model finds is the model's business. That the
    # answer is well shaped, in the vocabulary, and attributable to the text is this tool's.
    for name, (_value, quote) in answer.values.items():
        assert name in NAMES
        assert quote and quote.casefold() in " ".join(PLAIN.split()).casefold()


def test_a_real_model_is_still_held_to_the_attribution_rule() -> None:
    """feat-009/AC-13: a description that says nothing must not produce values.

    The most useful thing this test can catch is a model that helpfully infers a septic system from
    "just outside town", and the mechanism that stops it is the quote check rather than the prompt.
    """
    answer = ask(live_session(), live_account(), read_prose(NOTHING), NAMES)

    for name, (value, quote) in answer.values.items():
        assert quote.casefold() in " ".join(NOTHING.split()).casefold(), (
            f"{name}={value} was attributed to {quote!r}, which is not in the description"
        )
