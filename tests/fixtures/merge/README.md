# One real run over three sources, with the properties made up

`three-sources.json` is 140 rows as Realtor.com, Zillow and Redfin returned them for one town on
2026-08-24, containing 45 groups where two or three sources describe the same property. It is the
test data for address matching, because no invented corpus would have produced the disagreements
that are actually in it.

**The properties are not real.** Street names are replaced with invented ones, house numbers are
shifted, the town and the postal code are made up, and every coordinate is moved by a fixed offset.
Collected listing data is local data and does not belong in a repository, and none of it was what
made this corpus worth keeping.

**What is real, exactly as it arrived, is every disagreement between the sources**, which is the
whole point:

- the same house with a different street type from different sources: `2016 N Sable Ave` against
  `2016 N Sable St`;
- one source dropping the street type entirely: `1414 Gable` against `1414 Gable Cir`;
- one source repeating it: `405 N Ave DOVETAIL Ave` against `405 N Avenue DOVETAIL`;
- one house in three formats at once: `2139 S Willow Rd 7`, `2139 S Willow Rd S #7`,
  `2139 S Willow Road 7`;
- units written four ways: `Unit B`, `# 7`, `# G`, `Lot 2`;
- land with no street address at all: `Bigler Addition Block 2 Lot 3`;
- a house number carrying a letter: `2128B Verity` against `2128 B Verity`;
- coordinates for the same property differing by seven to thirty-eight metres;
- prices for the same property differing by a few thousand, which is why price is not a matching
  signal;
- and **no parcel numbers at all**, on any row, from any source.

The offsets that were applied are fixed, so distances between two sources' coordinates for one
property are exactly what they were.
