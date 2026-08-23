# Research — address-merge

## Discovery input

From `homescout-brief.md` sections 5.2 and 12, which calls this the messiest part of the project
and says to budget real time for it:

- The same house appears on all three sources with different address formatting. The brief's own
  example: `1747 S Roosevelt Rd 10 1/2` against `1747 South Roosevelt Road 10 1/2`.
- Normalized street plus ZIP is the primary key to attempt. Coordinates within roughly fifty metres
  confirm or break a tie. A parcel number, where a source supplies one, is the strongest signal
  available and is preferred over both.
- The failure mode the brief names first is a bad merge, and its mitigation is threefold: never
  destroy source rows, flag ambiguity for a human instead of guessing, and persist the human's
  decisions.
- The stated first real use is acreage in New Mexico, where a large share of listings are land with
  no street address at all, so an address-keyed strategy has to have an answer for properties that
  have no address to key on.

## Problem brief

### Problem statement

Someone consolidating listings from several sources struggles to tell whether two rows describe
the same house because every source formats addresses differently, some supply coordinates and
some do not, and a meaningful share of rural and land listings carry no usable street address at
all, which results in either the same property counted and reviewed several times or, far worse,
two different properties silently fused into one record whose history is then nonsense. A solution
should merge confidently where the evidence is strong, refuse to guess where it is not, and make
every merge inspectable and reversible, without ever destroying the source rows the merge was
built from.

### Target users

- **The person running searches** (primary): wants one row per house, and wants to be asked rather
  than guessed at when the tool is unsure.
- **The same person six months later** (primary, differently): needs to look at a suspicious record
  and see exactly which source rows produced it and why they were joined.

### Jobs to be done

- Recognize the same property across sources despite formatting differences.
- Refuse to merge when the evidence is weak, and put that decision in front of a person.
- Let a person merge or separate records by hand, and never re-litigate that decision afterwards.
- Show why any two rows were joined.
- Undo a merge without losing anything, including the user's own notes.

### Success signals

- A property listed on all three sources appears once.
- No two distinct properties are ever fused without a human having said so.
- A human's merge or separation decision is still honored after arbitrarily many later runs.
- Every canonical record can be traced back to the source rows underneath it.

### Constraints

- Source rows are never destroyed, edited, or hidden. Canonical records are built on top of them.
- Ambiguity is surfaced, never resolved by guessing.
- Annotations attached to a record must survive both a merge and its undo, which the store
  guarantees and this feature must not defeat.
- Land and rural listings without a street address are in scope for the product's first real use,
  so they cannot be treated as an exotic edge case.

### Explicitly out of scope

- Fetching (feat-002, feat-005) and storage mechanics (feat-001).
- The interface a person uses to review ambiguous pairs. This feature owns the queue and the
  decision record; the browser interface (feat-010) owns the screen.
- Deduplicating rows within a single source's single response, which the source adapters handle.

### Open questions

- The coordinate tolerance is stated in the brief as roughly fifty metres. Whether that is the
  right number for rural parcels, where a listing's point can sit anywhere on a large lot, is worth
  revisiting once there is real data. It is a tunable, not a redesign.
