"""What the household has already said it wants, gathered from where it already said it.

Nothing here authors a criterion. Every line sent to the model is something somebody wrote
deliberately somewhere else, and the best of it is the part nothing currently reads: eight exclusion
areas in one saved search, each carrying a paragraph explaining the actual worry rather than a label
on a polygon. Dairy odor. Flaring and truck traffic and the waste repository. Mining-affected
groundwater that reaches Gallup. Booms that carry across the whole basin rather than one part of it.
That is a better statement of taste than any instruction anybody would write for this.

**The exclusion reasons are context and not tests, and the distinction is load-bearing.** The
polygons have already removed what the household decided to remove, so a property being assessed is
outside every one of them. The reasons go along to explain what this household is worried about; a
concern may be raised only where the property's own evidence supports it. Without that sentence the
failure mode is obvious and expensive: a model reads "dairy odor" and flags every property in the
eastern half of the state.

**The sample of past judgments is calibration, not instruction.** 812 decisions with reasons say
more about this household's taste than a paragraph could. They are deliberately outside the
staleness fingerprint: they change every time anybody passes on a house, and folding them in would
mean one click reassessing everything, at cost, over a change nobody made to what they wanted.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

#: How many kept and passed properties to show. Enough to calibrate, few enough that the criteria do
#: not crowd out the property being asked about, which is the thing the request is actually for.
SHOWN_KEPT = 6
SHOWN_PASSED = 10

#: A reason longer than this is a paragraph somebody wrote for themselves rather than a criterion.
#: Cut rather than dropped, so a long reason still says what it was about.
REASON_LIMIT = 400


@dataclass(frozen=True, slots=True)
class Criteria:
    """What this household wants, in its own words.

    Split into what was stated and what is illustrative, because only the first belongs in the
    fingerprint that decides whether an assessment has gone stale.
    """

    #: What the saved search says it is for.
    about: str | None
    #: Why each area is excluded, in the person's own words. The most valuable part of this.
    avoided: tuple[tuple[str, str], ...]
    #: The rules, as written, with the severity each carries.
    rules: tuple[tuple[str, str, str], ...]
    #: The installation's and the search's notes for the model.
    notes: tuple[str, ...]
    #: Illustrative and deliberately outside the fingerprint. See the module docstring.
    kept: tuple[tuple[str, str | None], ...] = ()
    passed: tuple[tuple[str, str | None], ...] = ()

    def stated(self) -> dict[str, Any]:
        """The half that invalidates an assessment when it changes.

        Everything somebody wrote on purpose. The examples are not in here, which is the whole point
        of the split: they change constantly and mean nothing has changed about what is wanted.
        """
        return {
            "about": self.about,
            "avoided": [list(pair) for pair in self.avoided],
            "rules": [list(three) for three in self.rules],
            "notes": list(self.notes),
        }


def criteria_for(
    definition: Any,
    *,
    notes: Sequence[str] = (),
    kept: Sequence[tuple[str, str | None]] = (),
    passed: Sequence[tuple[str, str | None]] = (),
) -> Criteria:
    """Gather one saved search's criteria.

    `definition` is a `SearchDefinition`. Everything is read off it as the person wrote it; nothing
    is normalised, reworded or ranked, because the wording is the content. A rule named
    `fire-could-reach-the-house` tells a reader more than any restatement of its expression would,
    and it is a name they can go and look up in their own file.
    """
    avoided: list[tuple[str, str]] = []
    for area in getattr(definition, "exclusions", ()) or ():
        reason = (getattr(area, "reason", None) or "").strip()
        if not reason:
            continue
        # A drawn polygon carries the name somebody gave it; a named place carries the place. Both
        # are what the person would recognise, and neither is always the one that is set.
        name = (
            getattr(area, "name", None)
            or getattr(area, "value", None)
            or getattr(area, "label", None)
            or "an area"
        )
        avoided.append((str(name), _trimmed(reason)))

    rules: list[tuple[str, str, str]] = []
    for rule in getattr(definition, "rules", ()) or ():
        rules.append(
            (
                str(getattr(rule, "id", "") or getattr(rule, "rule_id", "")),
                str(getattr(rule, "severity", "") or ""),
                str(getattr(rule, "when", "") or getattr(rule, "expression", "") or ""),
            )
        )

    return Criteria(
        about=_trimmed((getattr(definition, "description", None) or "").strip()) or None,
        avoided=tuple(avoided),
        rules=tuple(rules),
        notes=tuple(_trimmed(n.strip()) for n in notes if n and n.strip()),
        kept=tuple(kept)[:SHOWN_KEPT],
        passed=tuple(passed)[:SHOWN_PASSED],
    )


def _trimmed(text: str) -> str:
    if len(text) <= REASON_LIMIT:
        return " ".join(text.split())
    return " ".join(text[:REASON_LIMIT].split()) + "…"


def examples_from(rows: Sequence[Any]) -> tuple[
    tuple[tuple[str, str | None], ...], tuple[tuple[str, str | None], ...]
]:
    """A handful of kept and passed properties, with the reason recorded at the time.

    The reason matters more than the property. "Screened out: off-grid and solar-reliant" and
    "Screened out: a production builder's plan home" are criteria this household applied and never
    wrote into a rule, because no rule could express them, and they are sitting in the annotations
    where nothing reads them.
    """
    kept: list[tuple[str, str | None]] = []
    passed: list[tuple[str, str | None]] = []
    for row in rows:
        annotation = getattr(row, "annotation", None)
        if annotation is None:
            continue
        judgment = getattr(annotation, "judgment", None)
        if judgment not in ("keep", "pass"):
            continue
        said = getattr(annotation, "verdict", None) or getattr(annotation, "notes", None)
        where = getattr(row.fields, "address_line", None) or row.listing_id
        entry = (str(where), _trimmed(said.strip()) if said and said.strip() else None)
        # A judgment with no reason teaches nothing, so the ones that carry one come first.
        (kept if judgment == "keep" else passed).append(entry)

    kept.sort(key=lambda e: e[1] is None)
    passed.sort(key=lambda e: e[1] is None)
    return tuple(kept[:SHOWN_KEPT]), tuple(passed[:SHOWN_PASSED])
