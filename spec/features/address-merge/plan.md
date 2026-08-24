# Plan — Address matching and merge review (feat-006)

The spec's WHAT, turned into a HOW. Read `spec.md` first; this file only decides how to satisfy it.

## What was measured first

Two measurements, both before any design: what the address parser actually does with the forms this
tool meets, and what the three shipped sources actually say about the same house. The second one is
the more valuable, and it exists because the sources shipped one feature ago: **a real run over
Portales, New Mexico on 2026-08-24 produced 140 rows across all three sources, 45 groups of them
describing the same property.** That corpus is committed as `tests/fixtures/merge/three-sources.json`
and every decision below is answerable against it.

Nine things came out of it, and each one changes the design.

- **M-1: the brief's example pair parses into aligned components.** `1747 S Roosevelt Rd 10 1/2` and
  `1747 South Roosevelt Road 10 1/2` both give `AddressNumber 1747`, `StreetName Roosevelt`, and
  `OccupancyIdentifier 10 1/2`; only the directional and the street type differ, and both of those
  are abbreviations of each other. So expanding abbreviations is the whole of what AC-1 needs.
- **M-2: the same house number splits two ways.** `1828B Redwine` gives `AddressNumber 1828B`;
  `1828 B Redwine` gives `AddressNumber 1828` plus `AddressNumberSuffix B`. The key has to fold the
  suffix back in or the two never meet.
- **M-3: the parser raises on some real addresses.** `Lot 14 Blk 2 Curry Road AA` raises
  `RepeatedLabelError` rather than returning anything. AC-22 requires the row to survive that, so
  every call is wrapped and a failure produces a row with no address key rather than no row.
- **M-4: land has no address to key on, and says so in a placeholder.** Real rows from the run read
  `Bigler Addition Block 2 Lot 3` and `000 TBD Bigler Addition Block 2 Lot 2 Rd`. A house number of
  `000` or `TBD` is the source saying there is none, and treating it as a number would match every
  parcel in the subdivision to every other.
- **M-5: no source supplies a parcel number.** Zero of 140 rows. The brief calls the parcel number
  the strongest signal available and the spec gives it two criteria; today it never fires, because
  none of the three sources carries one in a search response. It is built anyway (AC-4, AC-5, and a
  future source or a detail fetch may supply one) and this is written down so nobody later reads the
  parcel logic as load-bearing when it has never once run outside a test.
- **M-6: sources disagree about the street type of the same house.** `2016 N Sable Ave` from
  Zillow against `2016 N Sable St` from the other two (as the corpus names them), at coordinates 38 metres apart and the same
  price. `1414 Gable` from Realtor.com against `1414 Gable Cir` from the other two. `405 N Avenue
  DOVETAIL` against `405 N Ave DOVETAIL Ave`. **A street type that disagrees, or is missing on one side, cannot be
  allowed to force `distinct`.** This is the finding that most changes the design: the obvious
  implementation, one normalized string compared for equality, gets three of the corpus's forty-five
  groups wrong, silently, in the direction of duplicates.
- **M-7: coordinates for a true match agree to within tens of metres.** Seven metres for one pair,
  thirty-eight for the Sable pair, which is the widest in the corpus. The
  brief's fifty metres is the right default and the widest pair in the corpus is inside it by twelve.
- **M-8: prices disagree between sources for the same property**, routinely. `$255,000` against
  `$259,000` for one house; `$175,000` against `$179,000` for another. Price is not a matching
  signal and must not become one, however tempting it looks in a corpus this small.
- **M-9: the ZIP code is present on every row in the corpus.** Every one of the 140. The spec's
  edge case about a missing ZIP is real in principle and rare in practice, so it is handled and not
  optimized for.

## Design decisions

### D-1: layout

A new package, `src/homescout/merge/`, above the store and below the surfaces.

| file | holds |
|---|---|
| `merge/address.py` | one address, parsed and reduced to comparable parts. The only module that touches `usaddress`. |
| `merge/signals.py` | one comparison of two candidates: what agreed, what conflicted, what could not be checked. |
| `merge/compare.py` | the outcome, from the signals: `matched`, `ambiguous`, or `distinct`. |
| `merge/candidates.py` | which pairs are worth comparing at all, so a run is not quadratic. |
| `merge/pass_.py` | the pass: candidates, comparison, merges, and the queue. |
| `merge/queue.py` | the review queue, backed by the store rather than by memory. |

The existing `homescout/matches.py` (the port both surfaces already work against) stays exactly as
it is, and this feature supplies the real implementation behind it. That port was written for this,
and the two commands that read it (`matches list`, `matches resolve`) already work.

### D-2: an address is reduced to parts, never to one string

```python
@dataclass(frozen=True, slots=True)
class Address:
    number: str          # "1747", "1828b"; empty when there is none
    street: str          # "roosevelt", "abilene"; the name alone
    street_type: str     # "rd", "st"; expanded then abbreviated, and WEAK (D-4)
    direction: str       # "s"; expanded then abbreviated
    unit: str            # "10 1/2", "b"; STRONG (D-5)
    postal: str
    parsed: bool         # False when the parser refused, which is not a failure
```

One string compared for equality is the obvious implementation and M-6 is why it is wrong: three of
the corpus's forty-five groups disagree about the street type and one drops it entirely. Comparing
parts lets each part carry the weight it deserves.

Abbreviations are expanded and then re-abbreviated to one canonical short form (`Road` and `Rd` both
become `rd`, `South` and `S` both become `s`), because the sources use both directions.

A number of `000`, `tbd`, `na` or empty is no number (M-4). This is checked before the parser, not
after, because `000 TBD Bigler Addition...` parses perfectly well into a number that means nothing.

### D-3: the address key, and what a key is for

```python
def key(address) -> str | None:      # "88130|1747|roosevelt|10 1/2"
```

Number, street name, unit, ZIP. **Not the street type and not the directional.** It is a blocking
key (D-6) and a strong-signal component, and both jobs want the parts every source agrees on.

`None` when there is no number or no street name, which is the land case, and a row with no key is
never matched on coordinates alone (AC-8).

### D-4: the street type and the directional are corroborating, not deciding

Agreement adds confidence. Disagreement subtracts it. Neither alone decides anything, because M-6
found real houses where they disagree.

Concretely: two rows agreeing on number, street name, unit and ZIP are `matched` when nothing
contradicts, and a disagreeing street type is not a contradiction, it is one fewer agreement. What
*is* a contradiction is a unit that differs (D-5), a parcel number that differs (AC-4), or
coordinates further apart than the tolerance (AC-6).

### D-5: a unit that differs is a different property, and an absent one is not a unit

AC-3, and it is the one place where a difference in a weakly-formatted field is decisive: unit 4 and
unit 5 of the same building are two properties whatever else agrees. So a unit present on both sides
and different is `distinct`.

A unit present on one side and absent on the other is **not** a contradiction. The corpus shows why:
Realtor.com writes `2128 Verity Unit B` with unit `Unit B`, Redfin writes the same house with no
unit field at all. Treating that as a difference would refuse every merge involving a source that
does not break the unit out.

### D-6: candidates come from a key, so a run is not quadratic

The performance requirement says 5,000 rows must not be compared against every other row. They are
not: rows are bucketed by a blocking key and only rows sharing a bucket are compared. Two buckets,
because one is not enough:

- **the address key** (D-3), which catches everything with an address;
- **a rounded coordinate cell**, three decimal places, about 110 metres, which catches the rows an
  address key cannot: land, and the pairs where one side's street name is spelled differently.

A row appears in both buckets when it has both. Comparisons are then bounded by bucket size rather
than by the size of the run, and the corpus's largest bucket is three.

### D-7: the outcome, and what makes each one

| outcome | when |
|---|---|
| `distinct` | parcel numbers present on both sides and different; or units present on both sides and different |
| `matched` | parcel numbers agree; **or** the address keys agree and no contradiction and (coordinates agree or are unavailable) |
| `ambiguous` | everything else that is not obviously unrelated: an address key match with coordinates that contradict it, a coordinate-only match with no address, a row matching more than one existing record |
| nothing | no shared signal at all; the pair is not a pair and never enters anything |

`ambiguous` is the important one and it is deliberately easy to reach. Failing to merge costs a
duplicate row; merging wrongly fuses two price histories into fiction. The spec opens by saying that
asymmetry is what everything follows from, and this table is where it is actually decided.

### D-8: coordinates that are obviously wrong are absent, not contradictory

Null island (0, 0), a whole-degree pair, and a state centroid are all real values that mean "we do
not know". The spec's edge case asks for them to be treated as absent, and the reason is that one
bad coordinate would otherwise make every pair involving that row ambiguous. Tolerance is
`HOMESCOUT_MERGE_TOLERANCE_METRES`, defaulting to the brief's **50** (AC-7, M-7).

### D-9: a person's decision outranks everything, forever

Schema version 5, one table:

```sql
CREATE TABLE merge_decisions (
    id          TEXT PRIMARY KEY,
    pair_key    TEXT NOT NULL UNIQUE,  -- the two listing ids, sorted, so a pair has one decision
    listing_ids TEXT NOT NULL,
    verdict     TEXT NOT NULL,         -- 'same' | 'different'
    decided_at  TEXT NOT NULL,
    decided_by  TEXT NOT NULL DEFAULT 'human',
    merged_id   TEXT,
    note        TEXT
);
```

Consulted **before** any automatic signal, in both directions (AC-12), and it is what keeps a pair
out of the queue forever (AC-13). Append-only like the rest: a person changing their mind is a new
row, and the latest one for a pair wins, so "they said different in March and same in June" stays
readable.

The pair key is the two listing ids sorted, so the same decision is found whichever order a later
run compares them in. Merges chain, so the key is computed over the *original* constituent ids the
decision was made about, which the store already keeps.

### D-10: new evidence contradicts a decision without overruling it

AC-14. A pair a person merged, later observed with different parcel numbers, produces a
**contradiction**: recorded, surfaced in the digest and the queue's own listing, and acted on by
nobody. The merge state does not change.

This is a separate thing from an ambiguous pair and must not be put in the same list, because the
question is different: an ambiguous pair asks "which is it?", a contradiction says "you decided
this, and here is something that disagrees".

### D-11: merging is order-independent, and that is arranged rather than hoped for

AC-20. The pass sorts candidate pairs by a stable key before deciding any of them, and a pair's
outcome depends only on the two rows and the recorded decisions, never on what has already been
merged in this pass. A row matching two existing records is `ambiguous` (AC-21) rather than joining
whichever it met first, which is the other half of the same property.

### D-12: what this feature does not own

- **The store's merge machinery.** `supersede`, `undo_merge`, `listing_sources` with its
  `join_signal` and `decided_by`, and the guarantee that annotations survive both, all already
  exist and are already tested. This feature decides *whether* to merge; it does not reimplement
  *how*. AC-15, AC-16, AC-17 and AC-18 are largely assertions that this feature does not defeat
  guarantees the store already makes, and their tests say so in those words.
- **The queue's presentation.** `matches list` and `matches resolve` already exist and already work
  against the port. This feature fills the port in.
- **Deciding what to do about a duplicate the user has not reviewed.** Both rows stay, separate and
  visible, until a person says otherwise (AC-10).

## Verification approach

- **The real corpus is the test data.** 140 rows from three sources over one town, committed, with
  the 45 cross-source groups in it. The headline test is that the whole corpus reduces to the right
  number of properties with no wrong merge, and the pairs M-6 named are in it by name.
- **Every scenario in the spec becomes a test with the spec's own values**, including the brief's
  example pair, which is what AC-1 asks for.
- **Order independence is tested by shuffling.** The same corpus in several orders must produce the
  same canonical listings, which is AC-20 stated as an experiment rather than an argument.
- **The performance requirement is a slow test** over 5,000 synthetic rows, asserting the comparison
  count stays near-linear rather than quadratic, because "does not require comparing every row
  against every other" is a claim about the algorithm and is worth measuring.
- **The human-decision criteria are tested against a decision that contradicts the automatic
  conclusion**, in both directions, which is what AC-12 asks for by name.

## Added after the pre-build check

Two decisions the first draft did not make, and one thing it did that it should not have. All three
came out of the gate, which is what the gate is for: the first is a correctness hole that would have
produced exactly the silent bad merge this whole feature is organized against.

### D-13: matches chain, and a chain with a contradiction in it is not a merge

The first draft compared pairs and merged the ones that came back `matched`, and said nothing about
what happens when the pairs overlap. They do. A row from Realtor.com matches one from Zillow, that
Zillow row matches one from Redfin, and the Realtor.com and Redfin rows may not match each other at
all: different units, or coordinates further apart than either individual comparison saw.

Merging pair by pair would then fuse all three, and *which* three depends on the order the pairs
were considered in, which also breaks AC-20. Both problems have one answer:

1. Compare every candidate pair first, deciding nothing.
2. Build the connected components of the `matched` pairs.
3. **A component containing any `distinct` pair is not merged.** The whole component becomes one
   `ambiguous` entry naming every row in it and the pair that contradicts.
4. A component with no contradiction merges as a unit, in one call, with every row in it.

This makes order-independence structural rather than careful: components are the same set whatever
order the pairs arrived in, and nothing is decided until every pair has been compared.

It also lands the spec's own duplex edge case correctly. Two flats with the identical address and
no unit designation, each matching a third row, become one component with a contradiction in it, and
a person is asked about the group rather than told about three separate pairs.

### D-14: an address is bounded before it is parsed

`usaddress` runs a conditional random field over the tokens of a string a listing site wrote. It is
linear in tokens and this is not a hostile input problem in the way the rule engine's was, but the
cheap bound belongs here for the same reason it belongs there: nothing in this product should have
its running time set by the length of a value somebody else chose. An address longer than 200
characters is not an address; it is truncated for parsing, and the row keeps its original text.

### D-15: the corpus is real disagreements about invented properties

The first draft committed 140 rows exactly as three sources returned them, including the addresses,
prices and coordinates of real houses. The constitution says collected data is local and is not
committed, and a corpus of real listings in a repository is that, whatever it is labelled.

None of it was what made the corpus worth keeping. Street names are replaced with invented ones,
house numbers shifted, the town and postal code made up, and every coordinate moved by one fixed
offset so the distances *between* two sources' readings of one property are untouched. Every
disagreement between the sources survives exactly, which is the entire test value, and
`tests/fixtures/merge/README.md` lists them.
