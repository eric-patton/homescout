"""The deterministic baseline: what a description says, without asking anybody.

Always on, no configuration, no key, no network (AC-1). This is the part of the feature that has to
be right, because it is the part that always runs.

**Matching a noun is not extraction.** That is the one idea here, and it came out of measuring 1,176
real listings rather than out of taste. Roughly three in ten mentions of a utility in real prose are
not assertions that the property has one: `Water well, electricity, and septic needed`,
`Utilities such as electric, water, and sewer are nearby`, `City water is available`,
`can be annexed into the city which would give the buyer city water & sewer`,
`The propane tank was removed from property`. A pattern that matches `septic` and stops has a
measured error rate of about a third, in the direction that sends somebody to look at land they
cannot build on.

So every field is read in two stages. A **claim** is a phrase from that field's vocabulary, found
inside one sentence. The **window** around it, sixty characters either side and never past the
sentence, then decides which of three things happened:

- nothing disqualifying: the value, with its sentence as evidence
- the claim is negated: the value `none`, which is knowledge and not an absence
- the claim is a prospect (needed, nearby, available, would, future): **no value at all**

The second and third are different on purpose. "There is no gas" is a fact about a property. "Gas is
available at the road" is a sales pitch about a possibility, and recording it as gas service is how
this tool would tell somebody a bare lot is connected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import fields as fx
from .text import Prose, window

#: How far either side of a claim to look for something that disqualifies it. Sixty characters is
#: about a clause. The window never leaves the sentence, so a claim in one and a hedge in the next
#: are two statements rather than one.
WINDOW = 60

X = re.IGNORECASE | re.VERBOSE


@dataclass(frozen=True, slots=True)
class Claim:
    """One phrase, and the value it asserts when nothing disqualifies it."""

    pattern: re.Pattern[str]
    value: str


# ---------------------------------------------------------------------------
# The one hard pattern
# ---------------------------------------------------------------------------

# `well` occurs 301 times in the measured corpus and roughly one in seven of those is about water.
# The rest are `well-maintained`, `as well as`, `well-appointed`, `well-established`, `well-kept`,
# `well cared for`, `well built`, `well sized`. A keyword match here would report a private water
# source for a quarter of every market this tool searches, which is worse than reporting nothing.
#
# The discriminator is grammar, not a longer keyword list, and it is two rules that must both hold:
#
# 1. It must not be the adverb. A following hyphen rules it out absolutely, and so does a following
#    participle or adjective, which is mostly `-ed` and `-ing` plus a short list of the irregulars
#    that actually occur (`kept`, `built`, `lit`, `known`, `worth`, `as`).
# 2. It must be used as a noun: introduced by a determiner or a domain word, or followed by
#    something only a noun is followed by.
# Two halves, because they look in opposite directions and a lookbehind only sees what is behind the
# position it is written at. Putting the `as well` test after `\bwell\b` was an earlier bug: at that
# point the three characters behind are "ell", so it never fired and `as well` matched thirteen
# times over the corpus as a water supply.
_NOT_AS_WELL = r"(?<! \b as \s )"

_NOT_THE_ADVERB = r"""
    (?! \s* - )                       # "well-maintained"
    (?! \s+ \w+ (?: ed | ing ) \b )   # "well maintained", "well appointed", "well designed"
    (?! \s+ (?: kept | built | lit | known | worth | as | able | past | over | under
              | below | above | into | within | beyond | suited | versed | sized ) \b )
"""

# Each of these is wrapped in its own group on purpose. They are interpolated into a larger pattern,
# and a bare alternation reaches out past whatever it was meant to qualify: an earlier draft of the
# pattern below matched every "a " in every listing, thirteen thousand times over the corpus,
# because this `|` was not enclosed and so was alternating with the whole rest of the expression.
_A_NOUN_BEFORE = r"""
  (?:
      (?: \b (?: a | an | the | its | our | your | their | his | her | own | one | two
               | private | domestic | water | shared | community | existing | producing
               | submersible | irrigation | windmill | solar | electric | deep | good
               | working | operating | new | old | second | additional | onsite | on-site )
          \s+ (?: \w+ \s+ )? )
    | (?: \d+ \s* gpm \s+ )
  )
"""

_A_NOUN_AFTER = r"""
  (?:
      (?: \s* [,.;!?)] )
    | (?: \s+ (?: is | was | are | were | and | with | plus | for | on | at | in
                | that | which | already | has | had | provides? | serves?
                | supplies | pumps? | produces? ) \b )
  )
"""

# The determiner is consumed rather than looked behind at, because Python's lookbehind wants a fixed
# width and "its own private" is not one. Consuming it costs nothing: the span is used to place the
# disqualifier window and to settle overlaps, and both are happier with the wider one.
WELL = re.compile(
    rf"(?: {_A_NOUN_BEFORE} {_NOT_AS_WELL} \b wells? \b {_NOT_THE_ADVERB} )"
    rf"| (?: {_NOT_AS_WELL} \b wells? \b {_NOT_THE_ADVERB} (?= {_A_NOUN_AFTER} ) )",
    X,
)

IRRIGATION_WELL = re.compile(r"\b irrigation \s+ wells? \b", X)


# ---------------------------------------------------------------------------
# The vocabulary, as phrases
# ---------------------------------------------------------------------------

CLAIMS: dict[str, tuple[Claim, ...]] = {
    "water_source": (
        # Longest first: overlapping matches are settled by span, and an irrigation well is a well
        # and is still not what comes out of the tap.
        Claim(IRRIGATION_WELL, "irrigation"),
        Claim(re.compile(r"\b (?: city | municipal | town ) \s+ water \b", X), "city"),
        # `water district` is deliberately absent. All four occurrences in the corpus are the Hot
        # Water District, which is a neighbourhood in Truth or Consequences and not a utility. A
        # phrase that is only ever a place name is not a claim about plumbing.
        Claim(
            re.compile(
                r"\b (?: co-?op \s+ water | water \s+ co-?op | community \s+ water"
                r"  | rural \s+ water | water \s+ association ) \b",
                X,
            ),
            "co-op",
        ),
        Claim(re.compile(r"\b cisterns? \b", X), "cistern"),
        Claim(WELL, "well"),
        Claim(re.compile(r"\b no \s+ (?: water \s+ )? wells? \b", X), fx.NONE),
    ),
    "sewer": (
        Claim(re.compile(r"\b (?: aerobic \s+ )? septics? \b", X), "septic"),
        Claim(re.compile(r"\b (?: sewage \s+ )? lagoons? \b", X), "lagoon"),
        Claim(re.compile(r"\b sewer \w* \b", X), "city"),
        Claim(re.compile(r"\b no \s+ (?: septic | sewer ) \b", X), fx.NONE),
    ),
    "heating": (
        Claim(re.compile(r"\b central \s+ (?: heat | heating | h/a ) \b", X), "central"),
        Claim(re.compile(r"\b heat \s* pumps? \b", X), "heat pump"),
        Claim(
            re.compile(
                r"\b radiant \s+"
                r"(?: heat \w* | floor \w* | in-? \s? floor \w* | ceiling | under \w* )",
                X,
            ),
            "radiant",
        ),
        Claim(re.compile(r"\b (?: wood | wood-? burning ) \s+ stoves? \b", X), "wood stove"),
        Claim(re.compile(r"\b pellet \s+ stoves? \b", X), "pellet stove"),
        Claim(re.compile(r"\b baseboard \s* (?: heat \w* )? \b", X), "baseboard"),
        Claim(re.compile(r"\b boilers? \b", X), "boiler"),
        # A mini-split is a heat pump and normally does both, but the corpus has four described
        # purely as cooling ("an energy-efficient mini split AC system", "a loft with a mini split
        # AC"). Where the text says which half it means, it is believed.
        Claim(
            re.compile(
                r"\b mini \s* -? \s* splits? \b (?! \s* (?: a/?c | air \s+ condition ) \b )", X
            ),
            "mini-split",
        ),
        Claim(
            re.compile(r"\b (?: gas | wall | floor | forced \s+ air ) \s+ furnace \b", X),
            "furnace",
        ),
        Claim(
            re.compile(r"\b no \s+ (?: permanent \s+ )? heat (?: ing | \s+ source )? \b", X),
            fx.NONE,
        ),
    ),
    "cooling": (
        Claim(
            re.compile(r"\b refrigerated (?: \s+ (?: air | a/?c | cooling ) )? \b", X),
            "refrigerated",
        ),
        Claim(re.compile(r"\b (?: evaporative \w* | swamp \s+ coolers? ) \b", X), "evaporative"),
        Claim(
            re.compile(
                r"\b central \s+ (?: air \b | a/?c \b | cooling \b"
                r"  | heat \s* (?: & | and ) \s* air \b )",
                X,
            ),
            "central",
        ),
        Claim(re.compile(r"\b mini \s* -? \s* splits? \b", X), "mini-split"),
        Claim(
            re.compile(r"\b window \s+ (?: units? | a/?c | air \s+ condition \w* ) \b", X),
            "window",
        ),
        Claim(
            re.compile(r"\b no \s+ (?: a/?c | air \s+ condition \w* | cooling ) \b", X),
            fx.NONE,
        ),
    ),
    "gas": (
        Claim(re.compile(r"\b natural \s+ gas \b", X), "natural"),
        Claim(re.compile(r"\b (?: propane | butane | lp \s+ gas ) \b", X), "propane"),
    ),
    "roof": (
        Claim(
            re.compile(
                r"\b (?: seamless \s+ )? metal \s+ roof \w* | \b standing \s* -? seam \b", X
            ),
            "metal",
        ),
        Claim(re.compile(r"\b shingle \w* \b", X), "shingle"),
        Claim(re.compile(r"\b (?: clay | concrete | ) \s* tile \s+ roof \w* \b", X), "tile"),
        Claim(re.compile(r"\b flat \s+ roof \w* \b", X), "flat"),
        Claim(re.compile(r"\b (?: spray \s+ )? foam \s+ roof \w* \b", X), "foam"),
    ),
}


# ---------------------------------------------------------------------------
# What disqualifies a claim
# ---------------------------------------------------------------------------

# A negation has to be *attached* to the claim, not merely present in the sentence. The corpus
# contains `Three mini-splits efficiently heat and cool this all-electric home-no propane required`,
# where a negation anywhere-in-the-window rule would read the "no" as denying the mini-splits and
# report a house with no heating and no cooling. So the negator must sit immediately before the
# claim, or a word of disuse immediately after it.
#
# The gap is small and may not cross a comma. Both bounds were set by reading real output: with
# twenty characters and commas allowed, `AN OLD HOUSE ON THE PROPERTY BUT IT IS NOT RESTORED, CO-OP
# WATER IS IN THE ROAD` reached back across the clause boundary and read "not" as denying the water
# rather than the restoration. It reached the right answer for the wrong reason, which is the kind
# of luck that stops being lucky on the next listing.
_NEGATED_BEFORE = re.compile(
    r"\b (?: no | not | never | without | lacks? | lacking | minus ) \b [^.;,]{0,12} $", X
)
_NEGATED_AFTER = re.compile(
    r"^ [^.;]{0,24} \b (?: removed | abandoned | disconnected | capped | dry"
    r"  | non-? functional | inoperable | not \s+ working | does \s+ not \s+ work"
    r"  | no \s+ longer ) \b",
    X,
)

# A prospect is somebody describing what could be true, and it may sit on either side of the claim,
# so this one reads the whole window. `available` alone accounts for thirteen of the thirty-five
# hedged mentions in the corpus.
_A_PROSPECT = re.compile(
    r"\b (?: needed | needs | need | required \s+ to | nearby | available | availability"
    r"  | would | could | will \s+ be | can \s+ be | must \s+ be | to \s+ be \s+ \w+ ed"
    r"  | future | planned | proposed | in \s+ the \s+ road | at \s+ the \s+ road"
    r"  | to \s+ the \s+ (?: lot | property ) \s+ line"
    # A service on its way to you is not a service. `There is a city water line coming down Apache
    # St approximately 600-700 ft`, `City water is in the subdivision, but not on this street yet`
    # and `City water extends down Mountain View Rd` are three land listings in the corpus, and all
    # three would otherwise read as a connected supply.
    r"  | yet | coming | extends | extending | approximately | \d+ \s* (?: ft | feet | miles? ) \b"
    # Somewhere to put one is not one. `a designated spot for a wood-burning stove` and
    # `venting for a pellet or wood stove` are both in the corpus, and both describe an absence.
    r"  | (?: spot | space | venting | vent | plumbing | plumbed | wiring | wired"
    r"    | roughed \s+ in | stubbed \s+ (?: in | out ) ) \s+ for ) \b",
    X,
)


@dataclass(frozen=True, slots=True)
class Found:
    """One thing a description said about one field."""

    field: str
    value: str
    evidence: str


def _matches(sentence: str) -> list[tuple[int, int, str, str]]:
    """Every claim any field makes in this sentence, with overlaps settled by specificity.

    Longer match wins, which is what makes `irrigation well` an irrigation well rather than both an
    irrigation well and a well, and `city water` a city supply rather than a bare `water` match it
    would otherwise also produce. Settled per field, because two fields legitimately claim the same
    words: `central heat & air` is a central heating system and a central cooling system, and
    `mini-split` is both at once.
    """
    found: list[tuple[int, int, str, str]] = []
    for name, claims in CLAIMS.items():
        spans: list[tuple[int, int, str, str]] = []
        for claim in claims:
            for match in claim.pattern.finditer(sentence):
                spans.append((match.start(), match.end(), name, claim.value))
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        taken: list[tuple[int, int, str, str]] = []
        for span in spans:
            if any(span[0] < end and start < span[1] for start, end, _, _ in taken):
                continue
            taken.append(span)
        found.extend(taken)
    return found


def _verdict(sentence: str, start: int, end: int, value: str) -> str | None:
    """What this claim actually asserts: its value, `none`, or nothing.

    Negation is checked first and wins. "No natural gas at the road" is a property with no gas, and
    the fact that the road is also mentioned does not turn knowledge back into a possibility.
    """
    before = sentence[:start]
    after = sentence[end:]
    if _NEGATED_BEFORE.search(before) or _NEGATED_AFTER.search(after):
        # A negated negative is not a positive. "No septic needed" says nothing useful and is not
        # an assertion that the property has one.
        return None if value == fx.NONE else fx.NONE
    if value == fx.NONE:
        return fx.NONE
    if _A_PROSPECT.search(window(sentence, start, end, span=WINDOW)):
        return None
    return value


def read(prose: Prose) -> dict[str, list[Found]]:
    """Everything this description says about the six fields, one entry per claim it makes.

    Conflicts are not resolved here and are not resolved anywhere: this returns what was said, and
    `values_for` decides that two different answers for one field is not an answer.
    """
    found: dict[str, list[Found]] = {}
    for sentence in prose.sentences():
        for start, end, name, value in _matches(sentence):
            verdict = _verdict(sentence, start, end, value)
            if verdict is None:
                continue
            found.setdefault(name, []).append(
                Found(field=name, value=verdict, evidence=" ".join(sentence.split()))
            )
    return found
