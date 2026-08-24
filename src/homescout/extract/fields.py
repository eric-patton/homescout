"""The six fields this feature recovers, and the closed set of values each may hold.

One table, read by both backends, and that is the point of it existing. The deterministic patterns
answer from it, and a model's answer is checked against it, so the two can never disagree about what
a value is called and a model cannot invent a seventh field or a value nobody downstream knows how
to read. It is also, in D-8's terms, the reason a prompt injection has nowhere to go: the widest
thing a successful one could achieve is a wrong member of one of these sets.

Every value here is a *kind*, not a condition. `new roof` is the most common roof phrase in real
listings and is not in this table, because it says nothing about what the roof is made of. A bare
`A/C` is not here either, for the same reason: it names no kind. Both are coverage given up
deliberately rather than filled with the most likely answer, which is product invariant 10 applied
to the thing this feature is most tempted to guess at.

`none` is a value, and a different thing from an empty field. "No natural gas at the road" is
knowledge about a property; nobody mentioning gas is not.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The value a field takes when the text says the property does not have the thing. A real answer,
#: recorded, and not to be confused with the field being empty.
NONE = "none"


@dataclass(frozen=True, slots=True)
class Field:
    """One recoverable field, and everything it may say.

    `evidenced` is the subset the 1,176-description corpus this feature was measured against
    actually contains. The rest are reachable but rare, and are kept so a model reading "the house
    is on a cistern" can say so rather than be rejected for a word the patterns had no phrase for.
    """

    name: str
    values: tuple[str, ...]
    evidenced: tuple[str, ...]

    def allows(self, value: str) -> bool:
        return value in self.values


FIELDS: tuple[Field, ...] = (
    Field(
        "water_source",
        ("well", "city", "co-op", "cistern", "irrigation", NONE),
        ("well", "city", "co-op", "irrigation", NONE),
    ),
    Field("sewer", ("septic", "city", "lagoon", NONE), ("septic", "city", NONE)),
    Field(
        "heating",
        (
            "central",
            "heat pump",
            "radiant",
            "wood stove",
            "pellet stove",
            "baseboard",
            "boiler",
            "mini-split",
            "furnace",
            NONE,
        ),
        ("central", "radiant", "wood stove", "pellet stove", "baseboard", "boiler", "mini-split",
         NONE),
    ),
    Field(
        "cooling",
        ("refrigerated", "evaporative", "central", "mini-split", "window", NONE),
        ("refrigerated", "evaporative", "central", "mini-split", NONE),
    ),
    Field("gas", ("natural", "propane", NONE), ("natural", "propane", NONE)),
    Field(
        "roof",
        ("metal", "shingle", "tile", "flat", "foam"),
        ("metal", "shingle", "tile", "flat"),
    ),
)

BY_NAME: dict[str, Field] = {field.name: field for field in FIELDS}

#: Every field name, in a stable order, for anything that has to list them.
NAMES: tuple[str, ...] = tuple(field.name for field in FIELDS)


def find(name: str) -> Field | None:
    return BY_NAME.get(name)


def _check_against_the_namespace() -> None:
    """Every field here is a name a criterion can use, and every extracted name has a filler.

    The same two-way check the enrichment registry makes, for the same two reasons: a value no
    criterion can name is work nobody can use, and a name the rule engine declares with nothing
    filling it is a promise the tool cannot keep.
    """
    from ..rules import namespace as ns

    for field in FIELDS:
        declared = ns.find(field.name)
        if declared is None or declared.origin != "extracted":
            raise AssertionError(
                f"{field.name!r} is recovered from prose but is not an extracted field in the rule "
                "engine's namespace. A value no criterion can name is work nobody can use."
            )

    promised = {name for name, field in ns.FIELDS.items() if field.origin == "extracted"}
    if promised - set(NAMES):
        raise AssertionError(
            "the rule engine declares extracted fields nothing fills: "
            f"{sorted(promised - set(NAMES))}"
        )


_check_against_the_namespace()
