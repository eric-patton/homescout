"""One address, reduced to the parts that can honestly be compared.

The obvious implementation is to normalize an address into one string and compare strings. It is
wrong, and the corpus this feature is tested against says exactly how wrong: three sources describe
the same house as `2016 N Sable Ave`, `2016 N Sable St` and `2016 N Sable St`. One calls it an
avenue, two call it a street, the coordinates agree to within forty metres and the price is
identical. A string comparison calls that two properties, silently, and the duplicate sits in the
table forever.

So an address becomes parts, and each part carries the weight it has earned:

- **the house number, the street name, the unit and the postal code are strong.** Every source
  agrees on these when they agree at all, and a difference in the unit is a different property.
- **the street type and the directional are weak.** Sources disagree about them, drop them, and
  occasionally repeat them (`405 N Ave DOVETAIL Ave` against `405 N Avenue DOVETAIL`).

The parser is `usaddress`, and two of its behaviours shape this module. It splits a lettered house
number two ways depending on spacing (`1828B` against `1828 B`), so the suffix is folded back in.
And it raises on some real addresses rather than returning anything, so every call is wrapped: a row
whose address cannot be read keeps its text and loses only its key.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import usaddress

#: An address longer than this is not an address. Truncated before parsing rather than after,
#: because the point is not to hand a conditional random field a value whose length was chosen by
#: somebody else. The original text is kept on the row; only the parsing is bounded.
MAX_LENGTH = 200

#: House numbers that mean "there is no house number". Land listings carry these constantly, and
#: treating `000` as a number would match every parcel in a subdivision to every other one.
NO_NUMBER = frozenset({"", "0", "00", "000", "0000", "tbd", "tba", "na", "n/a", "none", "xxx"})

#: Street types, in both directions, folded to one short form. Sources use both, so both are here
#: and neither is preferred: `Road` and `Rd` are the same thing said twice.
STREET_TYPES: dict[str, str] = {
    "street": "st", "st": "st",
    "avenue": "ave", "ave": "ave", "av": "ave",
    "road": "rd", "rd": "rd",
    "drive": "dr", "dr": "dr",
    "circle": "cir", "cir": "cir", "circ": "cir",
    "lane": "ln", "ln": "ln",
    "court": "ct", "ct": "ct",
    "place": "pl", "pl": "pl",
    "boulevard": "blvd", "blvd": "blvd", "boul": "blvd",
    "parkway": "pkwy", "pkwy": "pkwy", "pky": "pkwy",
    "trail": "trl", "trl": "trl",
    "highway": "hwy", "hwy": "hwy",
    "terrace": "ter", "ter": "ter",
    "loop": "loop",
    "way": "way",
    "square": "sq", "sq": "sq",
    "run": "run",
    "path": "path",
    "point": "pt", "pt": "pt",
    "ridge": "rdg", "rdg": "rdg",
    "crossing": "xing", "xing": "xing",
}

#: The same, for the eight directions plus their long forms.
DIRECTIONS: dict[str, str] = {
    "north": "n", "n": "n",
    "south": "s", "s": "s",
    "east": "e", "e": "e",
    "west": "w", "w": "w",
    "northeast": "ne", "ne": "ne",
    "northwest": "nw", "nw": "nw",
    "southeast": "se", "se": "se",
    "southwest": "sw", "sw": "sw",
}

#: Words that decorate a unit rather than name one. `Unit B`, `# B` and `B` are one unit.
UNIT_WORDS = frozenset({"unit", "apt", "apartment", "suite", "ste", "no", "number", "#"})

#: Words that mean "this is a parcel in a subdivision", not "this is a street". Land listings are
#: written this way constantly (`Bigler Addition Block 2 Lot 3`), and the parser does its best with
#: them: it read `Block 2` as a house number and `Lot` as a street name. A street name made only of
#: these is not a street name, and a row with no street name is never matched on coordinates alone,
#: which is what the spec asks for land.
NOT_A_STREET = frozenset(
    {"lot", "lots", "block", "blk", "addition", "add", "tract", "parcel", "unit", "units",
     "subdivision", "sub", "tbd", "tba", "na", "unassigned", "unknown", "acreage", "acres"}
)

#: Which of the parser's labels feed which part. Everything it can return that is not here is
#: ignored on purpose: a city, a state and a postal code come from the row's own fields, which are
#: cleaner than anything parsed out of a free-text line.
_NUMBER_LABELS = ("AddressNumber",)
_SUFFIX_LABELS = ("AddressNumberSuffix", "AddressNumberPrefix")
_STREET_LABELS = ("StreetNamePreModifier", "StreetNamePreType", "StreetName")
_TYPE_LABELS = ("StreetNamePostType",)
_DIRECTION_LABELS = ("StreetNamePreDirectional", "StreetNamePostDirectional")
_UNIT_LABELS = ("OccupancyIdentifier", "SubaddressIdentifier")
_UNIT_TYPE_LABELS = ("OccupancyType", "SubaddressType")


@dataclass(frozen=True, slots=True)
class Address:
    """One address in comparable pieces, with a note of whether it could be read at all.

    Every field is lower case and stripped of punctuation, and an absent one is the empty string.
    Absent is not a value: two addresses that both have no unit have not agreed about the unit, they
    have simply not disagreed, and the comparison treats those differently.
    """

    number: str = ""
    street: str = ""
    street_type: str = ""
    direction: str = ""
    unit: str = ""
    postal: str = ""
    #: False when the parser refused the text outright. The row still exists and still has whatever
    #: could be salvaged; what it does not have is a key.
    parsed: bool = True
    #: What was handed in, so a person looking at a queued pair sees what the source actually said.
    raw: str = ""

    @property
    def has_street(self) -> bool:
        return bool(self.number and self.street)

    def key(self) -> str | None:
        """The blocking and matching key, or nothing.

        Number, street, unit and postal code. **Not the street type and not the directional**: those
        are the parts sources disagree about, and a key built from a part sources disagree about is
        a key that separates a house from itself.

        `None` when there is no number or no street name, which is the land case. A row with no key
        is never matched on coordinates alone.
        """
        if not self.has_street:
            return None
        return "|".join((self.postal, self.number, self.street, self.unit))


def _clean(text: str) -> str:
    return re.sub(r"[^a-z0-9/ ]+", " ", text.lower()).strip()


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _unit_of(parts: dict[str, str]) -> str:
    """The unit, with the words that decorate it removed.

    `Unit B`, `# B`, `Apt B` and `B` are the same unit written four ways, and the corpus has all
    four. What is left after the decoration is what gets compared.
    """
    found = " ".join(parts.get(label, "") for label in _UNIT_LABELS).strip()
    if not found:
        return ""
    words = [word for word in _clean(found).split() if word not in UNIT_WORDS]
    return _collapse(" ".join(words))


def _substantial(words: list[str]) -> bool:
    """Is there anything here but street types and compass points?"""
    return any(
        word not in STREET_TYPES.values() and word not in DIRECTIONS for word in words
    )


def _street_name(line: str, number: str, unit: str) -> str:
    """The street's name, worked out by subtraction rather than by trusting a label.

    The parser is good at house numbers and units and unreliable about names, and the way it is
    unreliable matters here. The Southwest names streets `S Avenue B` and `N Ave N`, and the parser
    reads the *directional* as the name and `Avenue` as the type, leaving nothing at all.

    So the name is everything in the line that is not the house number, not a leading directional,
    and not the unit. Then every word is folded to one abbreviation, and **every street type is
    removed unless removing them leaves nothing but types and compass points**. That one rule does
    all the work:

    - `Sable Ave` and `Sable St` both become `sable`, which is the disagreement three sources have
      about one house;
    - `Halstead Parkway Dr` and `Halstead Pkwy` both become `halstead`, even though one carries two
      types;
    - `NM Highway 236` and `NM 236` both become `nm 236`;
    - `Ave N` stays `ave n`, because removing the type would leave a bare compass point, and the
      street really is called Avenue N.

    A name made only of subdivision words is no name, which is what keeps land out of the key.
    """
    words = _clean(line).split()
    if words and words[0].rstrip("abcdefghijklmnopqrstuvwxyz").isdigit():
        first = words[0]
        words = words[1:]
        # The letter of `1828 B Redwine` has already been folded into the number, so it must not
        # also be read as the start of the street name.
        if words and len(words[0]) == 1 and first.isdigit() and number.endswith(words[0]):
            words = words[1:]
    while words and words[0] in DIRECTIONS:
        words = words[1:]

    unit_words = set(unit.split()) | UNIT_WORDS
    while words and words[-1] in unit_words:
        words.pop()

    folded = [STREET_TYPES.get(word, word) for word in words]
    trimmed = [word for word in folded if word not in STREET_TYPES.values()]
    if _substantial(trimmed):
        folded = trimmed
    while len(folded) > 1 and folded[-1] in DIRECTIONS and _substantial(folded[:-1]):
        folded = folded[:-1]

    if not folded or all(word in NOT_A_STREET or word.isdigit() for word in folded):
        return ""
    return " ".join(folded)


def _tag(text: str) -> tuple[dict[str, str], bool]:
    """The parser's reading of one line, or a note that it would not read it.

    `usaddress` raises `RepeatedLabelError` on genuinely ambiguous text, which real land listings
    produce (`Lot 14 Blk 2 Curry Road AA`). That is not a failure of the run or even of the row: it
    means this address cannot be keyed, and the comparison falls to whatever other signals exist.
    """
    try:
        tagged, _kind = usaddress.tag(text)
    except (usaddress.RepeatedLabelError, UnicodeDecodeError):
        return {}, False
    except Exception:  # noqa: BLE001 - a third-party parser on text nobody controls
        return {}, False
    return dict(tagged), True


def parse(line: str | None, *, unit: str | None = None, postal: str | None = None) -> Address:
    """One address line, plus whatever the row carried separately, as comparable parts.

    The unit and the postal code are taken from the row's own fields when it has them, because a
    field is cleaner than anything parsed out of a free-text line, and folded in from the parse when
    it does not.
    """
    raw = (line or "").strip()
    postal_code = re.sub(r"[^0-9]", "", (postal or ""))[:5]

    if not raw:
        return Address(
            unit=_unit_of({"OccupancyIdentifier": unit or ""}),
            postal=postal_code,
            parsed=True,
            raw=raw,
        )

    # One bounded copy, used by everything that reads the text. The row keeps `raw` in full.
    bounded = raw[:MAX_LENGTH]
    parts, parsed = _tag(bounded)

    # Only when it is the first token of the line. `Bigler Addition Block 2 Lot 3` makes the
    # parser offer `2` from `Block 2`, and a house number that is not at the front of an American
    # address is not a house number: it is a parcel description, and those have no street to key on.
    first_token = _clean(bounded).split()[0] if _clean(bounded).split() else ""
    number = _clean(" ".join(parts.get(label, "") for label in _NUMBER_LABELS))
    if number and not first_token.startswith(number):
        number = ""
    suffix = _clean(" ".join(parts.get(label, "") for label in _SUFFIX_LABELS))
    # `1828B` and `1828 B` are the same house said two ways, and the parser splits them differently
    # depending on the space. Folding the suffix back in is what lets the two meet.
    number = _collapse(number + suffix).replace(" ", "")
    if number in NO_NUMBER:
        number = ""

    # Deferred until the unit is known, because the unit comes off the end of the line.
    street_type = STREET_TYPES.get(_clean(parts.get("StreetNamePostType", "")), "")
    direction = ""
    for label in _DIRECTION_LABELS:
        found = DIRECTIONS.get(_clean(parts.get(label, "")), "")
        if found:
            direction = found
            break

    from_line = _unit_of(parts)
    from_field = _unit_of({"OccupancyIdentifier": unit or ""})
    chosen = from_field or from_line
    street = _street_name(bounded, number, chosen)

    return Address(
        number=number,
        street=street,
        street_type=street_type,
        direction=direction,
        unit=chosen,
        postal=postal_code,
        parsed=parsed,
        raw=raw,
    )


def of(fields: object) -> Address:
    """The address of anything carrying the listing fields, which is what the pass works with."""
    return parse(
        getattr(fields, "address_line", None),
        unit=getattr(fields, "unit", None),
        postal=getattr(fields, "postal_code", None),
    )
