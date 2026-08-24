# Description corpus

`descriptions.json` is 263 real listing descriptions, and it is the test for the deterministic
pattern extraction in `src/homescout/extract/patterns.py`. Two halves, and which is which matters.

## What is real

**The prose.** Every sentence that carries one of the six extracted fields, or one of the phrases
that looks like it does and does not, is exactly as a real estate agent wrote it. That is the point
of the fixture: this feature exists to read prose written by people who were not thinking about it,
and prose written by somebody who was thinking about it proves nothing.

It is why the corpus contains all of these, verbatim:

- `Water well, electricity, and septic needed.` A property with none of those three.
- `Utilities such as electric, water, and sewer are nearby.` Nearby is not connected.
- `CO-OP WATER IS IN THE ROAD NEXT TO THE LAND BUT NO METER CONNECTION.`
- `The propane tank was removed from property.`
- `Three mini-splits efficiently heat and cool this all-electric home-no propane required.`
- `a designated spot for a wood-burning stove`, which is somewhere to put one.
- `Existing well, but no pump.`
- Thirty-six occurrences of `well-maintained` and thirty-one of `as well as`, none of which is a
  water supply.

## What is not

Everything that would make one of these rows a real property was replaced before it was committed,
because the constitution says collected listing data stays on the local machine:

| what | becomes |
|---|---|
| street addresses, with or without a house number | `Example Street`, `NNN Example` |
| numbered highways, state routes and county roads | `Example Highway` |
| prices and any other dollar amount | `$XXX,XXX` |
| postal codes | `88888` |
| telephone numbers | `XXX-XXX-XXXX` |
| listing service numbers | `MLS #000000` |
| web addresses and email addresses | `example.invalid` |
| the agent a description asks you to ring | `contact the agent` |

Town names, counties and acreage are left alone. They are the market this tool was pointed at, not
the identity of a property in it.

## Where it came from

1,231 listings pulled on 2026-08-24 from Portales, Clovis, Roosevelt County, Curry County, Silver
City and Truth or Consequences, of which 1,176 carried a description and 701 were distinct. The 263
here are the distinct descriptions that mention any of the six fields or any of the phrases that
resemble them. The rest are not interesting to this feature and were not kept.

The measurements those 1,176 produced are in `spec/features/field-extraction/plan.md`, and the two
that shaped the design most are worth repeating here: about one in seven occurrences of `well` is
about water, and about three in ten mentions of a utility are hedged, negated or prospective rather
than an assertion that the property has one.
