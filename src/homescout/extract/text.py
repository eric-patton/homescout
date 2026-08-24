"""Reading listing prose safely: bounding it, cutting it into sentences, comparing it.

Nothing here interprets anything. It exists because three separate parts of this feature need the
same three operations on a string that came from a stranger, and having three opinions about where a
sentence ends is how a pattern matches across one and a quote check fails on the same text.

The bound is the one load-bearing part. A description is untrusted input of unbounded length, and it
is about to be put in a request body, so it is cut to a stated size before anything touches it and
the cut is recorded rather than being silent. The source measured for this feature truncates its own
descriptions at four thousand characters, so that is where this cuts too: matching it means the
bound almost never fires on real text and is there for the day something else arrives.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

#: What a description is cut to before anything reads it. See the module docstring for why this
#: number.
MAX_LENGTH = 4_000

#: Sentence ends, for the purpose of not letting a pattern match a claim in one sentence against a
#: disqualifier in the next. Deliberately crude: this is a boundary for a sixty-character window,
#: not a parser, and a decimal point inside `2.5 baths` splitting a sentence costs nothing here.
_SENTENCE_END = re.compile(r"(?<=[.!?])[\s ]+")

_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Prose:
    """One description, as this feature is willing to read it."""

    text: str
    truncated: bool = False

    @property
    def digest(self) -> str:
        """This text's identity, and the cache key every model answer is stored under.

        Of the *bounded* text, because the bounded text is what is sent. Two descriptions that
        differ only past the cut are one question, which is correct: they are one question.
        """
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def sentences(self) -> tuple[str, ...]:
        return tuple(part for part in _SENTENCE_END.split(self.text) if part.strip())

    def contains(self, quote: str) -> bool:
        """Does this text carry that quote, allowing for whitespace and case?

        The attribution check (AC-13), and the reason a model cannot assert a well that was never
        mentioned. Loose about whitespace and case because a model re-typing a quote will normalize
        both and neither changes what was said; strict about everything else, because everything
        else is what was said.
        """
        wanted = folded(quote)
        return bool(wanted) and wanted in folded(self.text)


def folded(text: str) -> str:
    """One line, single spaces, lower case. For comparing two pieces of the same prose."""
    return _WHITESPACE.sub(" ", text).strip().casefold()


def read(description: str | None) -> Prose | None:
    """A description, bounded, or nothing at all.

    Empty and absent are the same answer here and produce no values anywhere downstream, which is
    the spec's own edge case: extraction produces nothing and reports nothing unusual.
    """
    if description is None:
        return None
    text = description.strip()
    if not text:
        return None
    if len(text) > MAX_LENGTH:
        return Prose(text[:MAX_LENGTH], truncated=True)
    return Prose(text)


def window(sentence: str, start: int, end: int, *, span: int) -> str:
    """The text around a match, bounded by its own sentence.

    Bounded by the sentence on purpose. A claim in one sentence and a hedge in the next are two
    statements, and reading them as one is how `There is a septic system. City water is available.`
    would lose its septic tank.
    """
    return sentence[max(0, start - span) : end + span]
