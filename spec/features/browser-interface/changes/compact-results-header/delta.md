# Delta: browser-interface

> The change expressed against the current spec as explicit operations.

## ADDED

One acceptance criterion, taking the next stable id when folded into `spec.md`: AC-114.

**User story.** As the person deciding between houses, I want the Results table to have most of
the window, so that I can compare twenty rows rather than ten without anything I have set being
out of sight.

- AC-114: On the Results page the furniture above the table is compact, and nothing is removed.
  The trail, the page heading, the four screens about the search and the "How this table works"
  disclosure share one line that wraps. The three control groups keep their names, written inline
  before their controls. Drive-time filtering, when the search has drive-time areas, is a "Drive
  time" button in the Which rows group, closed on every visit and not remembered, whose text names
  every range in force (for example "Drive time: Church 0-25 min", "Church ≤25 min",
  "Work ≥55 min", several joined by semicolons, with to or from added only when two locations
  share a name), says when a selected location has an entry that cannot be used, and says when
  estimates are being calculated. The button reports its state as expanded or collapsed. Opening
  it shows the existing controls inline under the controls row, one line per location (checkbox,
  name and direction, address, Min, Max, clear and its inline error) with the explanation in one
  line, the completeness facts and the Retry button, and pushes the table down. Its inputs exist
  while it is closed, so values and listeners survive. The count, the yellow incomplete notice
  when shown, the "Showing only" chips with "clear all filters", the Drive to Church note and the
  routing credit share one wrapping bar directly above the table. The credit (openrouteservice by
  HeiGIT, OpenStreetMap, CC-BY-SA 4.0) appears once on the page, in small text, always visible.
  The yellow notice appears only while results are incomplete (pending or unavailable estimates,
  a calculation running, a failure or another pass); when every estimate is in, its facts are
  said in the panel instead. At a 1920x950 window on la-near-church the table shows at least
  twice the listing rows it showed before, and at about 1280 px and phone widths nothing
  overlaps. The Map, What changed and Edit pages are unchanged.


## MODIFIED

None. The criteria below keep their wording, and this is how each stays satisfied:

- **AC-53.** The table box is still measured from where it falls. Opening or closing the Drive
  time panel, the button's text changing width and the yellow notice appearing or going all
  re-measure it.
- **AC-72.** The groups are still three, still named in words and still open; only the name moves
  beside its controls. The Drive time button is a control inside Which rows, not a menu standing
  in for a group, and what it holds is never hidden in effect: every range in force is in its
  text and in the chips, and the controls are one press away, as AC-78 already allows for
  explanation.
- **AC-78.** "How this table works" is the same disclosure with the same remembered state, now
  beside the heading.
- **AC-110.** The Results page still identifies Old Zion Hill Baptist Church, its address, the
  house-to-church direction, estimated driving without live traffic and the openrouteservice by
  HeiGIT / OpenStreetMap credit, in the bar above the table.
- **AC-111.** The controls are hidden when the search has no drive-time areas (no button, no
  panel). Selection, labels, independent bounds, inline errors and inert invalid drafts are the
  same controls.
- **AC-112.** Matching is untouched. The incomplete notice is as prominent as before whenever
  results are incomplete, with separate pending and unavailable counts, safe failure details and
  explicit Retry, and Retry is also in the panel.
- **AC-113.** Chips, individual clearing and Clear all behave as before, and the provider credit
  and the no-live-traffic explanation are still shown, once.

## REMOVED

None.
