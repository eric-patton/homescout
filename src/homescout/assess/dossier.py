"""Everything about one property that goes into one request.

Assembled from what other features already collected. Nothing here fetches anything: the listing's
fields came from a source, the recovered fields from `extract`, the enrichment values and the map
tile from `enrich`, the verdicts from `rules`. If this module ever needs to go and get something,
the design is wrong, which is the same test feat-009's own pass applies to itself.

**Absence is stated rather than omitted.** A property with no coordinates has no hazard rating, no
elevation, no aquifer answer and no nearest weather station, and one with no photograph has no
picture. Each of those is named in what is sent, because a silent gap reads to a model exactly like
a thing that was checked and raised no concern, and invariant 10's rule that an undetermined field
is empty rather than guessed is worth nothing if the emptiness is invisible.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

#: What a person deciding on a rural property reads first, in the order they read it. The order is
#: not cosmetic: it is what the model sees first, and a dossier that opens with the parcel and the
#: price frames every later value as a fact about that place.
HEADLINE: tuple[str, ...] = (
    "address_line",
    "city",
    "state",
    "postal_code",
    "price",
    "beds",
    "baths",
    "sqft",
    "lot_sqft",
    "year_built",
    "property_type",
    "listing_status",
)

#: Read out of the description by `extract`, and carried with where each came from. A value a
#: pattern found and a value a model found are not the same kind of claim, and the assessment is
#: entitled to weigh them differently.
RECOVERED: tuple[str, ...] = ("water_source", "sewer", "heating", "cooling", "gas", "roof")


@dataclass(frozen=True, slots=True)
class Dossier:
    """One property, as it is sent.

    Deliberately a plain structure rather than a formatted string. What it is turned into is the
    request body's problem, and keeping the two apart is what lets the assembly be tested without a
    model and the wording be changed without touching the assembly.
    """

    listing_id: str
    #: The address. This is the field `extract` may not have and this pass is built around.
    headline: Mapping[str, Any]
    description: str | None
    recovered: Mapping[str, Mapping[str, Any]]
    enrichment: Mapping[str, Any]
    #: Which criteria fired, with the severity each carries, in the household's own rule ids.
    verdicts: tuple[tuple[str, str], ...]
    latitude: float | None = None
    longitude: float | None = None
    #: What nobody holds a value for. Named, because a gap that is not named reads as an all-clear.
    unknown: tuple[str, ...] = ()
    #: Said in words rather than left for the model to notice, for the same reason.
    absent_pictures: tuple[str, ...] = ()
    wind: Mapping[str, Any] | None = None
    tags: tuple[str, ...] = ()

    @property
    def has_place(self) -> bool:
        return self.latitude is not None and self.longitude is not None


def dossier_for(row: Any, *, wind: Mapping[str, Any] | None = None) -> Dossier:
    """Assemble one property's dossier from the row every other surface already reads.

    `row` is an `export.rows.Row`, which exists because a spreadsheet and a table had to agree about
    what a column is and where its value comes from. It already carries the listing's fields, the
    recovered values with their provenance, every enrichment value held for the property, and which
    rules fired. Reusing it is what keeps this pass reading the same property the table shows rather
    than a second assembly of one that can drift from it.
    """
    fields = row.fields
    headline = {name: getattr(fields, name, None) for name in HEADLINE}
    headline = {name: value for name, value in headline.items() if value not in (None, "")}

    recovered: dict[str, dict[str, Any]] = {}
    for name in RECOVERED:
        found = row.extracted.get(name)
        if found is None or getattr(found, "value", None) in (None, ""):
            continue
        recovered[name] = {
            "value": found.value,
            # Where it came from, because a pattern match and a model's reading are different
            # claims and the assessment may weigh them differently.
            "how": getattr(found, "provenance", None) or getattr(found, "origin", None),
            "evidence": getattr(found, "evidence", None),
        }

    enrichment = {
        name: value for name, value in dict(row.enriched or {}).items() if value not in (None, "")
    }

    latitude = getattr(fields, "latitude", None)
    longitude = getattr(fields, "longitude", None)

    return Dossier(
        listing_id=row.listing_id,
        headline=headline,
        description=getattr(fields, "description", None) or None,
        recovered=recovered,
        enrichment=enrichment,
        verdicts=_verdicts(row),
        latitude=latitude,
        longitude=longitude,
        unknown=_unknown(fields, recovered, enrichment),
        tags=tuple(row.tags or ()),
        wind=wind,
    )


def _verdicts(row: Any) -> tuple[tuple[str, str], ...]:
    """Which of the household's own criteria fired on this property.

    The rule id is kept rather than reworded. It is the name the person gave the rule in their own
    file, so a concern that cites `fire-could-reach-the-house` is citing something they can go and
    read, which is the whole standard of evidence this feature is held to.
    """
    found: list[tuple[str, str]] = []
    for flag in row.flags or ():
        if isinstance(flag, str):
            found.append((flag, "flag"))
            continue
        name = getattr(flag, "rule_id", None) or getattr(flag, "id", None) or str(flag)
        found.append((name, getattr(flag, "severity", None) or "flag"))
    return tuple(found)


def _unknown(
    fields: Any, recovered: Mapping[str, Any], enrichment: Mapping[str, Any]
) -> tuple[str, ...]:
    """What nobody holds a value for, named.

    Invariant 10 says a field that could not be determined is empty and never a guess. That rule
    protects the store and does nothing for a reader who cannot see the difference between "no flood
    zone was determined for this address" and "this address has no flood risk". So the emptiness is
    said out loud, and AC-14 requires no concern to be raised or dismissed on the strength of it.
    """
    missing: list[str] = []
    if getattr(fields, "latitude", None) is None or getattr(fields, "longitude", None) is None:
        # The one absence that causes the others: every layer here is sampled at a point.
        missing.append("coordinates, so no hazard rating, elevation, aquifer answer or wind")
    for name in ("flood_zone", "wildfire_hazard", "wildland_urban_interface", "elevation_ft"):
        if name not in enrichment:
            missing.append(name)
    for name in RECOVERED:
        if name not in recovered:
            missing.append(f"{name} (the description does not say)")
    if not getattr(fields, "description", None):
        missing.append("any description at all")
    return tuple(missing)
