## Why

No free listing source exposes trustworthy history, so every question worth asking about a
property market ("what is new", "what got cheaper", "what came back", "what quietly vanished") has
to be answered from observations this tool made itself. This feature is the record of those
observations and the arithmetic over it. Everything else in the product either writes into it or
reads out of it, which is why its two guarantees, that history is never rewritten and that user
judgment is never lost, are stated as constitution non-negotiables rather than as requirements
here. The problem brief is in `research.md`.

## Vocabulary used in this feature

Two different things are called "status" in this domain, so this spec names them apart and uses
only these names:

- **Presence** is this tool's own judgment about whether a property is still being offered. It is
  either `observed` or `disappeared`.
- **Listing status** is whatever the source itself reported (for sale, pending, sold, and so on).
  It is source data. This feature stores and compares it but never infers it.

A **difference event** is what a comparison between two points in time reports about one canonical
listing. There are exactly five: `new`, `changed`, `unchanged`, `gone`, `returned`.

## User stories

- As the person running searches, I want every run to record what it saw, so that I can ask later
  what changed even for a question I had not thought to ask at the time.
- As the person running searches, I want price cuts, price increases, listing-status changes,
  disappearances, and returns surfaced to me, so that I stop re-reading listings I have already
  judged.
- As the person running searches, I want my rank, verdict, red flags, summary, next step, and free
  notes about a property to survive every future run, merge, and unmerge, so that the tool can
  replace my spreadsheet instead of merely feeding it.
- As the person running searches, I want to see the source rows behind any change the tool
  reports, so that I can tell a real price cut from a source bug.
- As a scheduled automated agent, I want the difference between two points in time to be
  reproducible, so that a digest generated today about last week matches the one generated last
  week.
- As the person running searches, I want a run in which a source failed to be recorded as exactly
  that, so that a source outage never reads as a market that emptied out.

## Behavior & scenarios

- **Scenario: first observation of a property**
  - Given a saved search that has never completed a run
  - When a run completes and at least one source returned a property
  - Then a canonical listing exists for it, its first-observed time is the run's start time, its
    presence is `observed`, and the run's comparison reports it as `new`

- **Scenario: a property observed again with no changes**
  - Given a canonical listing observed in the previous run
  - When a later run observes it with every compared field identical
  - Then its observed state for the later run is recorded, the comparison reports it as
    `unchanged`, and no earlier record is altered

- **Scenario: a price cut**
  - Given a canonical listing last observed at 449,000
  - When a run observes it at 435,000
  - Then the comparison reports it as `changed` with a price difference of 14,000 in the `down`
    direction, and both the previous and the new price remain individually recoverable

- **Scenario: a price increase**
  - Given a canonical listing last observed at 435,000
  - When a run observes it at 449,000
  - Then the comparison reports it as `changed` with a price difference of 14,000 in the `up`
    direction

- **Scenario: a listing-status change**
  - Given a canonical listing whose last observed listing status was for sale
  - When a run observes its listing status as pending
  - Then the comparison reports it as `changed`, identifying listing status as the changed field
    with its before and after values

- **Scenario: a property missing from one source but present in another**
  - Given a canonical listing backed by rows from two sources
  - When a run observes it from only one of them and the other source reported success
  - Then its presence stays `observed` and it is not reported as `gone`

- **Scenario: a property missing from every source in a successful run**
  - Given a canonical listing observed in the previous run
  - When a run in which every configured source reported success observes it from none of them
  - Then its presence becomes `disappeared`, the comparison reports it as `gone`, and the
    canonical listing and all of its history are retained and remain readable

- **Scenario: a property missing only because a source failed**
  - Given a canonical listing backed solely by rows from one source
  - When a run in which that source reported a failure observes it from no source
  - Then its presence stays `observed`, the comparison does not report it as `gone`, and the run
    records that source's failure

- **Scenario: a disappeared property comes back**
  - Given a canonical listing whose presence is `disappeared`
  - When a later run observes it again
  - Then its presence returns to `observed`, the comparison reports it as `returned`, and its
    timeline shows the disappearance and the return as separate dated events

- **Scenario: a source revises a field it previously reported**
  - Given a run that recorded a property's lot size as 1.0 acres
  - When a later run observes the same property with a lot size of 2.5 acres
  - Then the later value is recorded as a new observation, the earlier observation still reads
    1.0 acres, and no row is updated in place

- **Scenario: days on market is computed locally**
  - Given a property first observed by this tool 40 days ago
  - When a source reports its own days-on-market as 400
  - Then the tool's days on market for that property is 40, and the source's own value, if stored
    at all, is never substituted for it

- **Scenario: an annotation survives future runs**
  - Given a canonical listing annotated with a rank, a verdict, and free notes
  - When any number of further runs observe, change, or lose sight of that property
  - Then the annotation is unchanged and still attached to the same canonical listing

- **Scenario: an annotation survives a merge and an unmerge**
  - Given two canonical listings, each carrying its own annotation, that are later merged into one
  - When the merge is subsequently undone
  - Then no annotation content was destroyed at any point, and after the unmerge each annotation is
    attached to the canonical listing it originally described

- **Scenario: a difference from an arbitrary point in time**
  - Given a saved search with several completed runs
  - When a comparison is requested between the current state and a named past run or date
  - Then every affected canonical listing is reported with exactly one difference event, and
    repeating the same request later returns the same answer

- **Scenario: a run that fails partway through**
  - Given a run that has written some observations
  - When the run is interrupted before it finishes
  - Then no partially-written run is treated as a completed observation for comparison purposes,
    and the previous completed run remains the basis for the next comparison

- **Scenario: a property offered twice in a short window**
  - Given a canonical listing that was observed as sold and later observed as for sale again
  - When its timeline is read
  - Then both listing-status transitions appear as separate dated events with the observations
    that produced them

## Acceptance criteria

- [ ] AC-1: After a run completes, the observed state of every matching property at that run is
      recoverable exactly, and re-reading it after any number of later runs returns identical
      field values.
- [ ] AC-2: No operation in this feature updates or deletes a row representing a past observation.
      A test that attempts an in-place update of a recorded observation fails.
- [ ] AC-3: A first-ever run over N properties reports exactly N `new` events and zero `changed`,
      `gone`, `returned`, or `unchanged` events.
- [ ] AC-4: A repeated run over an unchanged result set reports zero `new`, `changed`, `gone`, and
      `returned` events, and N `unchanged` events.
- [ ] AC-5: A price change is reported with the previous value, the new value, the absolute
      difference, and a direction of `up` or `down` that matches the sign of the change.
- [ ] AC-6: Every compared field that differs between two observations is named in the `changed`
      event with its before and after values. A field the tool does not compare never appears.
- [ ] AC-7: A property absent from one source's results while at least one other configured source
      reported success and did return it keeps presence `observed` and produces no `gone` event.
- [ ] AC-8: A property absent from all sources in a run where every configured source reported
      success has presence `disappeared` and produces exactly one `gone` event.
- [ ] AC-9: A property absent from all sources in a run where any configured source reported a
      failure keeps presence `observed` and produces no `gone` event.
- [ ] AC-10: A `disappeared` property observed again has presence `observed`, produces exactly one
      `returned` event, and its history contains both the disappearance and the return with
      distinct timestamps.
- [ ] AC-11: A canonical listing whose presence is `disappeared` is still readable, still carries
      its full history, and is still returned by queries unless the caller excludes it explicitly.
- [ ] AC-12: Days on market is derived from the tool's own first observation. Given a source
      reporting a contradictory value, the tool's value is used and the source's value never
      overwrites it.
- [ ] AC-13: Every canonical listing resolves to the set of raw source rows it was built from, and
      each raw row records which source produced it and when it was fetched.
- [ ] AC-14: A raw source row is never modified or deleted after it is written, including when the
      canonical listing above it is merged, unmerged, or marked disappeared.
- [ ] AC-15: An annotation written against a canonical listing is returned unchanged after any
      number of subsequent runs that observe, change, or lose that property.
- [ ] AC-16: After a merge followed by an unmerge, every annotation that existed beforehand still
      exists with identical content, attached to the canonical listing it originally described.
- [ ] AC-17: An annotation is never created, modified, or deleted by a run. Only an explicit user
      action changes one.
- [ ] AC-18: A run records its identifier, the search it ran, its start and finish times, and for
      each configured source a success or failure result plus the number of rows that source
      contributed.
- [ ] AC-19: A run interrupted before completion is not used as either side of a comparison, and
      the next comparison uses the last completed run instead.
- [ ] AC-20: The same comparison request between two fixed points in time returns identical results
      when repeated at any later date, regardless of how many runs happened in between.
- [ ] AC-21: Every canonical listing appears in a comparison result at most once, carrying exactly
      one difference event.
- [ ] AC-22: The database records its schema version, and opening a database written by an earlier
      version either migrates it forward or refuses to open with a message naming both versions.
      It never operates against a schema it does not recognize.
- [ ] AC-23: All timestamps are stored in UTC, and a run that spans a daylight-saving transition
      produces the same ordering of events as one that does not.
- [ ] AC-24: A property returned more than once within a single source's response for a single run
      is recorded once per distinct source row and produces exactly one difference event.
- [ ] AC-25: At most one preview image is retained per canonical listing. It is stored on disk
      outside the database and referenced by path, survives the property becoming `disappeared`, and
      is never overwritten by a later failed retrieval. Full-size image addresses are recorded but
      the images themselves are not retained.

      A picture is retrieved against whichever record was being looked at when it was retrieved, and
      merging moves nothing, so a merged property reads its picture from the records merged into it
      and does so however many merges deep they lie. Nothing is copied and nothing is moved: this is
      what a merged property is asked, not what it is made to hold, which is why undoing a merge
      cannot lose a picture. A property whose picture is on this machine must never report having
      none, because "no photograph" is a thing this tool says about a listing that carried none and
      it has to keep meaning that.
- [ ] AC-26: Notes about an area or a town are stored independently of any property, are addressed
      by the area they describe, and survive every run exactly as property annotations do. They are
      never created or modified by a run.
- [ ] AC-27: A source link carries the address the source row can be read at, alongside the source's
      name and the source's own identifier. A property assembled from rows on several sites reports
      one address per site rather than one address in total, because the sites are not
      interchangeable to anyone keeping a list on one of them, and a site the property was never
      seen on contributes no address rather than a broken one.
- [ ] AC-28: A property carries any number of **tags**, which are words the household makes up.
      Keeping and passing answer this tool's own question, which is whether a house is still in;
      tags are for every other thing somebody wants to say about a house in one word, and a fixed
      field per idea would be a schema change per thought. A tag is a thing in its own right rather
      than text on a property, so it exists before anything carries it and outlives the last thing
      that did. Two spellings that differ only in case are one tag, and the spelling first written
      down is the one kept and shown: nobody remembers the capitalisation they used a week ago, and
      a store that disagrees hands them two piles of houses that should have been one. A tag may not
      contain a comma, refused where it is created and said why, because a tag is printed comma
      separated everywhere it is written down and one with a comma inside reads as two. Setting a
      property's tags means giving the whole list: anything left out comes off.
- [ ] AC-29: A tag can be renamed everywhere it is used in one action, keeping every property that
      carried it, and renaming onto a name that already exists merges the two. A tag can be deleted
      from the vocabulary and from every property at once, and the deletion answers with how many
      properties lost it, because that is the number somebody wants after doing it and the only way
      to know it afterwards would be to have remembered it. A vocabulary that cannot be corrected in
      one action is a vocabulary nobody corrects, which is how it turns into a list of near
      synonyms.
- [ ] AC-30: A merged property presents the tags of everything merged into it, gathered rather than
      moved, exactly as it presents their annotations and for the same reason. Removing a tag from a
      merged property reaches the record it was actually written on, because a tag somebody can see
      and cannot take off reads as the tool ignoring the click. Whatever is kept stays exactly where
      it is: nothing a person wrote moves between records, which is what carries their work through
      a merge and back out of one again.

## Edge cases & errors

- A source returns a property with no price. It is stored with an absent price, and a later
  observation that carries a price is a `changed` event from absent to present, not a price cut
  from zero.
- A source returns a property with no coordinates. It is stored and compared normally; features
  that need coordinates (location enrichment, polygon filtering) mark it as unresolvable rather
  than this feature rejecting it.
- Two runs of the same search start within the same clock second. Run identity does not depend on
  timestamp resolution.
- A run returns zero results, with every source reporting success. This is a valid completed run,
  and every previously-observed property in it correctly becomes `gone`.
- The database file is locked by another process, which is routine on Windows when the browser
  interface is open. The operation reports a clear, actionable error rather than corrupting or
  silently skipping the write.
- The database file is missing or empty. It is created at the current schema version, and the
  first run behaves as a first-ever run.
- The database was written by a newer version of the tool. Opening it is refused with a message
  naming both versions rather than attempted.
- Disk fills during a run. The interrupted run is not treated as complete, per AC-19, and no
  earlier data is damaged.
- A source's identifier for a property changes between runs (a relisting under a new number). This
  feature treats it as a distinct raw row and does not attempt to reconcile it. Reconciliation is
  address matching and merge review (feat-006).
- A comparison is requested against a date before any run exists. It reports that no baseline
  exists rather than returning everything as `new`.

## Non-functional requirements

- Performance: writing one run's observations for 5,000 properties completes in under 10 seconds,
  and computing a comparison between two runs of that size completes in under 5 seconds, on the
  development machine. A year of daily runs over 5,000 properties remains in one file and does not
  degrade the comparison beyond that bound.
- Security: the store holds no credentials and no executable content. Nothing read from a source
  is ever evaluated or interpreted as code.
- Reliability: any single write failure leaves the database readable and internally consistent,
  with the previous completed run intact and usable as a comparison baseline.
- Accessibility: none. This feature has no user-facing surface.

## Open questions

- Whether a run's observations are written incrementally as sources return, or in one commit at the
  end, is a plan-level decision. Either satisfies AC-19; they differ in behavior when a very long
  run is interrupted, and in how much work is lost.
