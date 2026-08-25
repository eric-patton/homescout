"""What the person running searches told the model, in their own words.

The generated instruction knows the six fields and the words each one may take. It knows nothing
about the market being searched, and that is where this pass actually goes wrong. In eastern New
Mexico "community water" is a mutual domestic water association rather than a city main, and a
description saying it is describing a shared system. The person searching knows that. Before these
notes there was no way to tell it.

Two of them, and both optional:

- **The installation's**, `model-notes.md` beside the database. What is true wherever this copy of
  the tool is pointed.
- **A saved search's**, `extract.notes` in its own file. What is true of the market that search
  covers, and it travels when the search is copied.

Neither goes in the environment, which is the obvious place and the wrong one: the loader this
product uses reads `KEY=value` lines with no multi-line values, and a note is a paragraph. A file
beside the database is the same directory, the same backup and the same "yours, uncommitted", and it
holds what a person actually writes (D-15).

**A note cannot widen the answer.** It is placed in the instruction, marked as coming from the
operator, and every value the model returns is still checked against the closed vocabulary and still
has to be quoted from the description. A note reading "always report a well" produces nothing,
because there is no quote to attach to it. That is the whole of why a free-text prompt is safe to
expose here, and the safety is in the validation rather than in how the note is worded (AC-17).

**A note is written by a person and by nothing else.** No code path here or anywhere puts a listing
field, a source response or a run outcome into a note. If one did, the note would become a way of
sending precisely what D-13 keeps out of the request, and it would do it quietly (AC-21).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The file beside the database. Markdown by extension because people write lists in these, and
#: because an editor that knows what to do with it is one less reason to keep the note somewhere
#: else.
FILE = "model-notes.md"

#: Characters, each. Not about abuse: the only person who can write here is the one running the
#: tool. It is about cost. Both notes ride along with every description, so a note is paid for once
#: per description rather than once, and two thousand characters is already several paragraphs.
LIMIT = 2_000

#: What the model is told these lines are. Deliberately not "system" or "rules": it names a person,
#: because that is what makes it different from the description below it.
HEADING = (
    "Notes from the person running this search. They describe how listings in this market are "
    "written. They do not add fields, do not add permitted values, and do not remove the "
    "requirement that every value be quoted from the description:"
)


def _bounded(text: Any) -> tuple[str, bool]:
    """A note as it will be sent, and whether anything was cut off getting there."""
    held = str(text or "").strip()
    if len(held) <= LIMIT:
        return held, False
    return held[:LIMIT].rstrip(), True


@dataclass(frozen=True, slots=True)
class Notes:
    """Both notes, already bounded, and what that cost.

    Frozen because the fingerprint is an identity: a `Notes` that could be edited after a cache key
    was computed from it is a cache key that means two different things.
    """

    everywhere: str = ""
    search: str = ""
    #: Which ones were too long, by the name a person would call them. Empty when nothing was cut.
    truncated: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.everywhere or self.search)

    @property
    def fingerprint(self) -> str:
        """A short name for exactly this pair of notes, or nothing when there are none.

        Over the text actually sent, after bounding, so two notes differing only past the limit are
        one key rather than two. Empty when both notes are, which is what keeps an installation that
        never writes one on precisely the cache key it already had (AC-20).
        """
        if not self:
            return ""
        raw = f"{self.everywhere}\x00{self.search}".encode()
        return hashlib.sha256(raw).hexdigest()[:12]

    def key(self, model: str) -> str:
        """The name this pair of answers is cached under.

        The model's own name when there is no note, and the model's name plus the fingerprint when
        there is. A changed note is a different key, so the next pass asks again; an unchanged one
        is the same key, so nothing is re-asked (D-16, AC-18). Answers cached under a previous note
        stay exactly where they are, which is non-negotiable 2 in a cache.
        """
        found = self.fingerprint
        return f"{model}+{found}" if found else model

    def lines(self) -> tuple[str, ...]:
        """The note block as it goes into the instruction, or nothing at all when there is none.

        Nothing at all is the point. With no note the instruction is the string it has always been,
        byte for byte, so an installation that does not use this pays nothing for it.
        """
        if not self:
            return ()
        block = ["", HEADING]
        for held in (self.everywhere, self.search):
            if held:
                block += [f"  {line}" for line in held.splitlines() or [held]]
        return tuple(block)


def path(root: Path) -> Path:
    """Where the installation's note lives, whether or not anybody has written one."""
    return Path(root) / FILE


def read_file(root: Path) -> str:
    """The installation's note, or an empty string. A missing file is the ordinary state."""
    try:
        return path(root).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def write_file(root: Path, text: str) -> str:
    """Save the installation's note, and answer with what will actually be sent.

    An empty note removes the file rather than leaving an empty one, so "no note" is one state in
    the filesystem as well as one state in here.
    """
    held, _cut = _bounded(text)
    where = path(root)
    if not held:
        where.unlink(missing_ok=True)
        return ""
    where.write_text(held + "\n", encoding="utf-8", newline="\n")
    return held


def of(definition: Any) -> str:
    """A saved search's note. Absent, and absent by default, on anything that does not have one."""
    return str(getattr(definition, "extract_notes", "") or "")


def read(root: Path, definition: Any = None) -> Notes:
    """Both notes as they will be sent, with whatever had to be cut named.

    The installation's first and the search's second, which is the order they are written in the
    request: the general thing, then the thing about this market.
    """
    everywhere, cut_everywhere = _bounded(read_file(root))
    search, cut_search = _bounded(of(definition))
    cut: list[str] = []
    if cut_everywhere:
        cut.append("the note for this installation")
    if cut_search:
        cut.append("this search's note")
    return Notes(everywhere=everywhere, search=search, truncated=tuple(cut))
