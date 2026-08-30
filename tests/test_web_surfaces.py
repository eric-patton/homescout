"""What each surface actually shows, checked where each one can be.

Some of these are about the server's answer and some are about what the script does with it. The
second kind is checked by reading the script rather than by rendering, except where a browser is the
only honest place, which is `test_web_browser.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

from homescout import api
from homescout.rules.definition import Rule
from homescout.rules.parse import parse
from homescout.rules.verdicts import record
from homescout.store import Store
from web_fakes import (
    STATIC,
    client,
    held_workspace,
    listing,
    load,
    ours,
    reading,
    shared_store,
)


def rule(expression: str, rule_id: str, severity: str) -> Rule:
    return Rule(id=rule_id, when=expression, severity=severity, expression=parse(expression))


def script(name: str) -> str:
    return (STATIC / f"{name}.js").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The results table
# ---------------------------------------------------------------------------


def test_the_table_is_served_every_column_in_one_answer(store: Store, db_path: Path) -> None:
    """feat-010/AC-7: every available column, and no round trip for an interaction.

    One answer carrying every row and every column is what makes sorting and filtering local. It was
    measured as free: 3.45MB of JSON parses in 18ms over a loopback interface.
    """
    load(store, [listing(f"p{n}") for n in range(5)])
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        found = browser.get("/api/results/portales", headers=reading()).json()

    assert len(found["columns"]) >= 32
    assert len(found["rows"]) == 5
    assert all(len(row["values"]) == len(found["columns"]) for row in found["rows"])

    # And the script never asks again for a sort or a filter.
    results = script("results")
    body = results[results.index("function apply"):results.index("function compare")]
    assert "ask(" not in body and "fetch" not in body


def test_the_criteria_that_fired_are_carried_as_badges(store: Store, db_path: Path) -> None:
    """feat-010/AC-8: a badge names the criterion, and the order reflects boost and demote."""
    loaded = load(store, [listing("cheap", price=90_000), listing("dear", price=800_000)])
    record(
        store,
        [
            rule("price < 100000", "a-bargain", "flag"),
            rule("price < 100000", "worth-a-look", "boost"),
            rule("price > 500000", "too-dear", "demote"),
        ],
        loaded.run_id,
    )
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        rows = browser.get("/api/results/portales", headers=reading()).json()["rows"]

    by_id = {row["listing_id"]: row for row in rows}
    assert by_id[loaded["cheap"]]["flags"] == ["a-bargain"]
    assert by_id[loaded["dear"]]["flags"] == []
    # Boosted first, demoted last, which is the core's own default order carried through unchanged.
    assert rows[0]["listing_id"] == loaded["cheap"]

    assert 'badge(flag, "flag")' in script("results")


def test_a_property_that_disappeared_is_hidden_and_counted(store: Store, db_path: Path) -> None:
    """feat-010/AC-20: hidden by default, shown by a filter that is there and says how many."""
    load(store, [listing("a"), listing("b")])
    load(store, [listing("a")])  # b was not seen this time
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        rows = browser.get("/api/results/portales", headers=reading()).json()["rows"]

    assert any(row["presence"] == "disappeared" for row in rows), "the server carries both"

    results = script("results")
    assert "state.showGone" in results
    assert 'row.presence !== "disappeared"' in results, "hidden unless asked for"
    assert 'id: "showgone"' in results, "the filter is always available"
    # The count is still said, and now it is said where every other reason a row is missing is
    # said: in the bar above the table, in words, with its own control to lift it. AC-20 asks for
    # the number and no longer counts the controls on the screen, because the two that hide rows
    # became one and this one moved.
    assert "holding back the ones that came off the market" in results, "and it can be lifted"
    # The phrasing itself lives in the shared file, because AC-67 says the map and the table say
    # this in the same words and two copies of a sentence is how two surfaces come to differ.
    assert "off the market, hidden" in script("common"), "said as a reason, not as a tally"
    assert "off the market, hidden" not in results, "and said in exactly one place"
    assert "heldBack(offMarket" in results, "which the table asks for rather than restating"


def test_an_annotation_survives_a_later_run_that_changes_the_price(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-5: the test this criterion asks for by name.

    Non-negotiable 7 says losing a person's judgment is the one failure this tool cannot have,
    because judgment is what the tool replaces.
    """
    loaded = load(store, [listing("a", price=250_000)])
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        browser.post(
            f"/api/listings/{loaded['a']}/annotation",
            json={"verdict": "worth a look", "rank": 1, "notes": "the well is old"},
            headers=ours(),
        )

        # A later run, which also changes what the property costs.
        load(store, [listing("a", price=199_000)])
        found = browser.get(f"/api/listings/{loaded['a']}", headers=reading()).json()["listing"]

    assert found["fields"]["price"] == 199_000, "the run happened"
    assert found["annotation"]["verdict"] == "worth a look"
    assert found["annotation"]["rank"] == 1
    assert found["annotation"]["notes"] == "the well is old"


# ---------------------------------------------------------------------------
# One property
# ---------------------------------------------------------------------------


def test_one_property_carries_its_whole_picture(store: Store, db_path: Path) -> None:
    """feat-010/AC-9: photographs, description, enrichment, links, timeline, and provenance."""
    loaded = load(
        store,
        [
            listing(
                "a",
                description="The property has its own private well and a new septic system.",
                photo_urls=("https://photos.example.invalid/1.jpg",),
            )
        ],
    )
    store.store_preview_image(loaded["a"], b"\x89PNG\r\n\x1a\nnope", extension="png")
    # A second run, so there is a price timeline. The same values, because a source that stops
    # returning a description has told us the description is gone, not that this test is over.
    load(
        store,
        [
            listing(
                "a",
                price=199_000,
                description="The property has its own private well and a new septic system.",
                photo_urls=("https://photos.example.invalid/1.jpg",),
            )
        ],
    )

    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        found = browser.get(f"/api/listings/{loaded['a']}", headers=reading()).json()["listing"]

    assert found["has_image"] is True
    assert found["photo_urls"] == ["https://photos.example.invalid/1.jpg"]
    assert "private well" in found["fields"]["description"]
    assert found["fields"]["listing_url"].startswith("https://")
    assert len(found["prices"]) == 2, "the price timeline"
    assert found["extracted"]["water_source"]["value"] == "well"
    assert found["extracted"]["water_source"]["evidence"], "and where it says so"
    assert found["sources"], "the rows the record was built from"
    assert "join_signal" in found["sources"][0], "with the signal that joined each"


def test_a_missing_value_looks_different_from_a_known_negative(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-10, feat-010/AC-18: three states, three appearances, all of them words."""
    loaded = load(
        store,
        [
            listing("silent", description="A quiet home near the square."),
            listing("negative", description="The propane tank was removed from property."),
        ],
    )
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        silent = browser.get(f"/api/listings/{loaded['silent']}", headers=reading()).json()
        negative = browser.get(f"/api/listings/{loaded['negative']}", headers=reading()).json()

    assert silent["listing"]["extracted"]["gas"]["value"] is None
    assert negative["listing"]["extracted"]["gas"]["value"] == "none"

    common = (STATIC / "common.js").read_text(encoding="utf-8")
    assert '"not known"' in common, "nobody determined it, said in words"
    assert '"negative"' in common and '"none"' in common, "and a stated absence, said differently"


# ---------------------------------------------------------------------------
# The comparison and the queue
# ---------------------------------------------------------------------------


def test_a_comparison_here_is_the_comparison_a_terminal_makes(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-11: the same result for the same two points, because it is the same call."""
    load(store, [listing("a", price=250_000)])
    load(store, [listing("a", price=199_000), listing("b")])

    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        from_http = browser.get("/api/changes/portales", headers=reading()).json()
    from_core = api.changes(held, "portales")

    entry = from_http["searches"][0]
    assert entry["counts"]["new"] == from_core.counts["new"] == 1
    assert entry["counts"]["changed"] == from_core.counts["changed"] == 1
    assert len(entry["price_changes"]) == 1
    assert entry["price_changes"][0]["price_change"]["direction"] == "down"


def test_the_queue_carries_the_signals_and_a_decision_is_durable(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-12: the evidence both ways, and an answer later runs honour."""
    from homescout.matches import AmbiguousMatch, InMemoryQueue

    loaded = load(store, [listing("a"), listing("b")])
    queue = InMemoryQueue(
        [
            AmbiguousMatch(
                id="pair-1",
                listing_ids=(loaded["a"], loaded["b"]),
                agreed=("the same house number and street",),
                conflicted=("a hundred and two metres apart",),
            )
        ]
    )
    held = held_workspace(shared_store(db_path), queue=queue)
    with client(held) as browser:
        listed = browser.get("/api/matches", headers=reading()).json()["matches"]
        assert listed[0]["agreed"] == ["the same house number and street"]
        assert listed[0]["conflicted"] == ["a hundred and two metres apart"]

        answered = browser.post(
            "/api/matches/pair-1", json={"verdict": "different"}, headers=ours()
        )
        assert answered.status_code == 200, answered.text
        assert answered.json()["verdict"] == "different"

        assert browser.get("/api/matches", headers=reading()).json()["matches"] == []

    # Durable, and durability is the queue's own guarantee rather than this surface's: the real one
    # writes to the database, which address matching (feat-006) tests in its own suite. What this
    # surface owes is that the answer reaches the queue at all, and that the pair then leaves it.
    assert queue.verdicts["pair-1"][0] == "different"


def test_an_empty_queue_says_so_plainly() -> None:
    """The spec's own edge case: a surface that says nothing reads as broken."""
    matches = script("matches")
    assert "Nothing to review" in matches
    assert "clear enough to decide on its own" in matches


# ---------------------------------------------------------------------------
# Arranging the table


def two_sites(store: Store):
    """One property seen on two sites and merged, which is the case this section is about."""
    from conftest import do_run

    rows = {
        "realtor": [listing("a", listing_url="https://realtor.invalid/a")],
        "zillow": [listing("a", listing_url="https://zillow.invalid/a")],
    }
    do_run(store, "portales", sources=rows)
    merged = store.supersede(
        [held.id for held in store.listings()], join_signal="same address", decided_by="human"
    )
    # A run after the merge, so the latest run's row is the merged record rather than the two it
    # was made from. This is what a person actually looks at the morning after a merge.
    do_run(store, "portales", sources=rows)
    return merged


def test_a_row_offers_the_property_on_every_site_it_was_found_on(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-42: because the sites are not interchangeable to somebody keeping a list.

    A house on one site is not necessarily on another at all: in the statewide run of 2026-08-26
    Realtor returned 1,099 rows, Zillow 866 and Redfin 58, because Redfin's download excludes what
    its local MLS does not permit. Offering one address for a merged record leaves a person unable
    to reach the page on the site they actually use, and unable to tell that from the site not
    having the house.
    """
    merged = two_sites(store)
    held = held_workspace(shared_store(db_path))

    rows = api.results(held, "portales")["rows"]
    (row,) = [held_row for held_row in rows if held_row["listing_id"] == merged]

    assert {entry["source"] for entry in row["links"]} == {"realtor", "zillow"}
    assert {entry["url"] for entry in row["links"]} == {
        "https://realtor.invalid/a",
        "https://zillow.invalid/a",
    }
    assert "elsewhere" in script("results"), "the table draws them"


def test_a_row_says_whether_there_is_a_photograph_without_asking_for_it(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-43: one query for the whole table, not one request per row that 404s."""
    loaded = load(store, [listing("a"), listing("b")])
    store.store_preview_image(
        loaded["a"], b"not really a jpeg", source_url="https://pics.invalid/a"
    )
    held = held_workspace(shared_store(db_path))

    rows = {row["listing_id"]: row for row in api.results(held, "portales")["rows"]}

    assert rows[loaded["a"]]["has_image"] is True
    assert rows[loaded["b"]]["has_image"] is False


def test_the_photograph_the_table_draws_is_the_one_this_tool_stored() -> None:
    """feat-010/AC-43, feat-010/AC-51: drawing the table tells no listing site anything at all.

    The narrow claim, and the one worth pinning: what the table *renders* is served from this
    machine. A listing site's own addresses are reached only from inside the function that opens the
    gallery, which runs when somebody asks to see the rest of the photographs and never before, and
    they are not in the table's answer at all.
    """
    results = script("results")
    drawing = results.split("function thumbnail")[1].split("async function showPhotos")[0]
    opening = results.split("async function showPhotos")[1].split("function elsewhere")[0]

    assert "/api/listings/${encodeURIComponent(row.listing_id)}/image" in drawing
    assert "photo_urls" not in drawing, "a listing site's own address is never put in the table"
    assert "photo_urls" in opening, "the gallery has nothing to show"
    assert "await ask(" in opening, (
        "the addresses are fetched for the one property being asked about, rather than carried "
        "on every row of the table"
    )


def test_a_property_with_no_photograph_still_holds_the_space() -> None:
    """feat-010/AC-43: the rows are read by running an eye down a column, so they must line up."""
    results = script("results")

    assert 'el("span", {class: "thumb", "aria-hidden": "true"})' in results
    assert "hold the same space" in results


def test_every_column_is_either_filled_or_writable_and_says_which() -> None:
    """feat-010/AC-46: because an unmarked empty column was read as the tool knowing nothing.

    Five of the forty-two were a third kind: the household's own spreadsheet headings, filled by
    nobody and typed into by nobody either. `Fire/Egress/Terrain` reading empty on every row was
    taken to mean this tool had no fire data, while two columns of it sat off the right edge. They
    are annotation columns now, so every column is either something this tool fills or something
    the person writes, and the heading says which.
    """
    from homescout.export import columns as cols

    results = script("results")
    style = (STATIC / "app.css").read_text(encoding="utf-8")

    assert {column.origin for column in cols.COLUMNS} <= {
        "listing", "derived", "extracted", "enriched", "annotation",
        # The sixth, and its own rather than folded into one of the five. What a model made of a
        # property is not a reported value, a computed one, one read out of a description, public
        # data, or something the person wrote (feat-010/AC-86).
        "assessed",
    }, "a column that is neither filled by this tool nor writable by a person"
    assert "yours to write in" in results, "the heading does not say whose an empty column is"
    assert "th.yours" in style, "and it is not marked"
    for name, field in (("Annual Taxes", "taxes"), ("Fire/Egress/Terrain", "fire_egress"),
                        ("Crime/Safety", "crime")):
        assert f'"{name}": "{field}"' in results, f"{name} still cannot be typed into"


def test_the_row_height_is_published_from_one_place() -> None:
    """feat-010/AC-20's machinery: the virtual window's arithmetic and the stylesheet must agree.

    They did not. The script placed rows every 22 pixels and the stylesheet drew them 26 tall, so
    the drawn rows crept four pixels per row out from under the scrollbar and the last of them could
    not be reached at all. The height is now set by the script and read by the stylesheet, so there
    is one of it. A browser checks the result; this checks that the mechanism is still in place.
    """
    results = script("results")
    style = (STATIC / "app.css").read_text(encoding="utf-8")

    assert '--row-height' in results and 'setProperty("--row-height"' in results
    assert "height: var(--row-height)" in style
    assert "height: 22px" not in style


def test_the_shortlist_and_the_passed_list_are_one_question_asked_twice(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-49, feat-010/AC-39: keeping is the other half of a judgment that already existed.

    The store has held `keep` since the judgment was added and no surface ever wrote one, so the
    shortlist a person actually works from could not be built. Both halves are readable from the
    core, which is what product invariant 5 needs before either surface shows them.
    """
    loaded = load(store, [listing("a"), listing("b"), listing("c")])
    held = held_workspace(shared_store(db_path))

    api.annotate(held, loaded["a"], judgment="keep")
    api.annotate(held, loaded["b"], judgment="pass")

    kept, keeps = api.kept(held)
    passed, passes = api.passed(held)

    assert (keeps, passes) == (1, 1)
    assert [row["listing_id"] for row in kept] == [loaded["a"]]
    assert [row["listing_id"] for row in passed] == [loaded["b"]]
    # The third has no judgment and is in neither, which is the whole point of the third state.
    assert loaded["c"] not in {row["listing_id"] for row in (*kept, *passed)}


def test_keeping_a_property_hides_nothing(store: Store, db_path: Path) -> None:
    """feat-010/AC-49: passing takes a house out of the table; keeping must not."""
    loaded = load(store, [listing("a"), listing("b")])
    held = held_workspace(shared_store(db_path))
    api.annotate(held, loaded["a"], judgment="keep")

    rows = {row["listing_id"]: row for row in api.results(held, "portales")["rows"]}

    assert rows[loaded["a"]]["judgment"] == "keep"
    assert rows[loaded["a"]]["hidden_by_default"] is False


def test_the_controls_come_before_every_column_of_data() -> None:
    """feat-010/AC-49: and cannot be dragged away, so they are in one place on every row."""
    results = script("results")

    assert "return [PASS_COLUMN, ...ordered];" in results
    assert "if (name === PASS_COLUMN.name) return;" in results, "the control column cannot be moved"
    assert "Math.max(1, Math.min(to" in results, "nothing may be moved in front of it"


def test_passing_asks_first_and_keeping_asks_afterwards() -> None:
    """feat-010/AC-48, feat-010/AC-54: only one of them is worth stopping somebody for.

    Passing takes a house out of the table, so it asks before doing it. Keeping hides nothing and
    the same button undoes it, so it does it first and then offers the box. The difference is the
    order, not whether a reason is wanted: both want one.
    """
    results = script("results")
    keeping = results.split("function keepToggle")[1].split("/* What they liked")[0]

    assert "const asked = await confirmPass(" in results, "passing asks before it acts"
    assert "showModal()" in results, "a browser confirm() stops every pending save on the page"
    assert "confirmPass" not in keeping, "keeping a house stops to ask permission it does not need"
    assert 'await setJudgment(rows, undoing ? null : "keep", button)' in keeping, (
        "keeping does not record the keep before asking anything"
    )
    assert "askWhy(button, rows," in keeping, "keeping never asks why"
    assert "if (!undoing)" in keeping, "taking a house off the shortlist asks for a reason too"
    # And the same order holds for a batch: one dialog before passing forty, none before keeping
    # them. `rows` rather than `row` throughout is what makes both act on the selection.
    assert "const rows = actingOn(row);" in results


def test_a_town_note_can_be_written_from_a_row_and_belongs_to_the_town(
    store: Store, db_path: Path
) -> None:
    """feat-010/AC-19: the note is addressed by the place, and edited where the opinion forms.

    Every other cell on a row is about that one property, and this one is not: a town note is
    addressed by the town, so writing it from a row writes it for every property there. That is
    the point of it, and it is also the thing that must not surprise anybody, so the cell says
    whose the note is before it is opened and the other rows change under it when it is saved.
    """
    loaded = load(store, [listing("a", city="Portales"), listing("b", city="Portales"),
                          listing("c", city="Clovis")])
    held = held_workspace(shared_store(db_path))

    api.set_area_note(held, "city", "Portales", "the water here is hard")
    rows = {row["listing_id"]: row for row in api.results(held, "portales")["rows"]}

    assert rows[loaded["a"]]["values"]["Town Analysis Notes"] == "the water here is hard"
    assert rows[loaded["b"]]["values"]["Town Analysis Notes"] == "the water here is hard", (
        "a note about a town that only reaches one of its properties is a note nobody sees"
    )
    assert rows[loaded["c"]]["values"]["Town Analysis Notes"] is None, "it is not everybody's note"

    results = script("results")
    assert 'const TOWN_NOTE = "Town Analysis Notes"' in results
    assert '"/api/areas"' in results, "the table writes it to the town rather than to the property"
    assert "not about this house" in results, "the cell does not say whose note it is"


# ---------------------------------------------------------------------------
# feat-010/AC-71, AC-72, AC-73: named, grouped, and joined up
# ---------------------------------------------------------------------------


def test_the_table_controls_are_grouped_by_the_question_they_answer() -> None:
    """feat-010/AC-72: three questions, named, rather than eleven controls in one flow."""
    results = script("results")
    for name in ("Which rows", "Which columns", "Elsewhere"):
        assert f'group("{name}"' in results, f"{name} is a named group"
    assert 'class: "grouped"' in results, "and they are laid out as groups"
    # Grouping reorders and labels; it hides nothing.
    for control in ('id: "showgone"', 'id: "showphotos"', 'id: "wraptext"',
                    "chooseColumns", "format=xlsx", "format=csv"):
        assert control in results, f"{control} survived the regrouping"


def test_one_control_asks_which_properties_and_both_surfaces_use_it() -> None:
    """feat-010/AC-35, AC-49, AC-67: one field, one control, same words on both surfaces.

    Two checkboxes over the judgment could express a state the table could not be in, and had to be
    applied in a careful order so they could not contradict each other. AC-67 additionally says the
    map and the table hide the same properties with the same controls and the same words, so the
    control lives in the shared file and neither page owns a copy.
    """
    common = script("common")
    assert "function judgmentChooser(" in common
    for key in ('"play"', '"keep"', '"pass"', '"all"'):
        assert key in common, f"{key} is one of the answers the chooser holds"
    for answer in ("In play", "Kept", "Passed on", "All"):
        assert f'"{answer}"' in common, f"{answer} is one of the answers"

    for page in ("results", "fire"):
        body = script(page)
        assert "judgmentChooser(" in body, f"{page} uses the shared control"
        assert "showPassed" not in body, f"{page} no longer holds its own passed flag"
        assert "onlyKept" not in body, f"{page} no longer holds a second control over one field"


def test_every_reason_a_row_is_missing_is_in_the_one_bar() -> None:
    """feat-010/AC-36, AC-20, AC-57: the bar holds all of them, and one control lifts all of them.

    The bar was built because a table silently missing four hundred rows is the worst thing this
    screen can do, and it was built holding only the column filters and the search box, which are
    the two narrowings that hide the fewest rows.
    """
    results = script("results")
    assert "heldBack(behind" in results, "the judgment is named in the bar"
    assert "heldBack(offMarket" in results, "so are the ones off the market"
    assert "narrowing by what you decided" in results, "each with its own control to lift it"

    # And it is drawn on arrival, not only once somebody touches a filter: the judgment narrows the
    # table by default, so a bar that waited would be silent for exactly the person wondering why.
    load_body = results[results.index("async function load()"):results.index("function knownTags")]
    assert "showFilters();" in load_body

    # One control lifts all of them, which now means all of them.
    clearing = results[results.index("function clearFilters()"):results.index("function setJudgmentFilter")]
    assert 'state.judgment = "all"' in clearing
    assert "state.showGone = true" in clearing

    # The totals line keeps the totals and loses the rest, the render time included.
    counting = results[results.index("function counts()"):results.index("function window_")]
    assert "in the latest run of this search" in counting, (
        "the total says which properties it counts, since four screens count four populations"
    )
    assert "kept`" in counting
    assert "toFixed" not in counting and "performance" not in counting, (
        "the render time is a number for whoever is writing this table, not for whoever reads it"
    )
    assert "performance.now" not in script("results"), "and it is not measured either"


def test_every_screen_about_a_search_offers_the_others() -> None:
    """feat-010/AC-73: four screens, one strip, and no page that reaches none of them.

    The search builder reached none of the other three, and a property's page reached nothing at
    all. Five copies of a navigation is how one of them ends up missing the surface added last.
    """
    common = script("common")
    assert "function aboutSearch(" in common
    for said in ("Results", "What changed", "Map", "Edit"):
        assert f'"{said}"' in common

    for page, here in (("results", "results"), ("changes", "changes"),
                       ("fire", "map"), ("search", "search")):
        assert f'"{here}")' in script(page), f"{page} says which screen it is"
        assert "aboutSearch(" in script(page), f"{page} draws the strip"

    # A property's page is about a property rather than a search, so its way back is to the table it
    # was read from, carried in the address because a house can be in several searches.
    listing_body = script("listing")
    assert "fromSearch()" in listing_body
    assert 'class: "crumbs"' in listing_body
    assert "propertyLink(" in script("results"), "and the table hands it over when it links"


def test_the_listing_page_has_one_heading_per_section() -> None:
    """feat-010/AC-9: two sections called the same thing is one of them being unfindable.

    Every listing page carried two headed "Where it is": the hazard map, and the flood zone, the
    aquifer, the elevation and the speeds. The second is about the public record of the place
    rather than about where the place is.
    """
    listing_body = script("listing")
    assert '"What is around it"' in listing_body
    # The map section keeps the name, and the two ways it can be drawn are one section, not two.
    assert listing_body.count('el("h2", {}, "Where it is")') == 2, (
        "the map section and its no-location form, which never render together"
    )


# ---------------------------------------------------------------------------
# feat-010/AC-74, AC-75: a view to open on, and a chooser sorted by origin
# ---------------------------------------------------------------------------


def test_the_table_opens_on_a_view_rather_than_on_every_column(store: Store, db_path: Path) -> None:
    """feat-010/AC-74: forty-three columns is five screens, and nobody chose it.

    The views name columns the answer declares, so this checks the names against the real answer
    rather than against a list written twice.
    """
    load(store, [listing("a")])
    held = held_workspace(shared_store(db_path))
    with client(held) as browser:
        declared = browser.get("/api/results/portales", headers=reading()).json()["columns"]

    results = script("results")
    assert "const VIEWS" in results
    for said in ('"Deciding"', '"Hazards"', '"Everything"'):
        assert said in results

    named = set(re.findall(r'"([^"]+)"', results[results.index("const VIEWS"):results.index("const CUSTOM")]))
    declared_names = {column["name"] for column in declared}
    unknown = {
        one for one in named
        if one not in declared_names and one not in {"deciding", "Deciding", "hazards", "Hazards",
                                                     "everything", "Everything"}
    }
    assert not unknown, f"a view names columns the answer does not declare: {sorted(unknown)}"
    # And the point of the whole thing: the opening view is a fraction of what there is.
    assert len(declared) > 30, "this test is only interesting while the table is wide"


def test_a_remembered_arrangement_is_never_recomputed_from_a_view(store: Store, db_path: Path) -> None:
    """feat-010/AC-74, feat-010/AC-45: the load-bearing rule, asserted against how it is written.

    Two implementations satisfy "a remembered arrangement wins" and behave oppositely. Deriving the
    hidden set from the view's name on every load puts back the thirty-one columns somebody just
    deviated from, and lets a later edit to a view rearrange a table already in use. So the stored
    set is authoritative and the name is a label on it, and a view is applied at exactly two
    moments: nothing stored at all, and somebody picking one.
    """
    results = script("results")
    arranging = results[results.index("function arrange("):results.index("function visible(")]

    assert "const stored = Object.keys(held).length > 0;" in arranging
    assert "if (stored) {" in arranging, "anything stored is honoured as it stands"
    assert "held.view || (stored ? CUSTOM : " in arranging, (
        "a stored arrangement with no view name is somebody's own, not an invitation to impose one"
    )
    # The view is applied in exactly two places, and neither of them is a later load.
    assert results.count("function useView(") == 1
    assert "view: state.view," in results, "the name is written down beside the set, not instead"

    # Deviating leaves the view rather than being reasserted by it, both ways of doing it.
    hiding = results[results.index("function hide("):results.index("function sortable(")]
    assert hiding.count("state.view = CUSTOM;") == 2, "hide and show both drop to Custom"


def test_a_view_naming_a_column_that_is_gone_narrows_rather_than_breaks() -> None:
    """feat-010/AC-74: a view is a list of names, so a retired column shortens it."""
    results = script("results")
    body = results[results.index("function shownBy("):results.index("function useView(")]
    assert "wanted.has(column.name)" in body, "matched by name against what is declared"
    assert "found.length ? new Set" in body and "null" in body, (
        "a view that matched nothing falls back to every column rather than a blank table"
    )


def test_the_chooser_groups_columns_by_where_their_values_come_from() -> None:
    """feat-010/AC-75, feat-010/AC-86: a group per origin, in the words the headings already use."""
    results = script("results")
    assert "const ORIGIN_GROUPS" in results
    groups = results[results.index("const ORIGIN_GROUPS"):results.index("/* The named views")]
    for origin in ("listing", "derived", "extracted", "enriched", "annotation", "assessed"):
        assert f'["{origin}"' in groups, f"{origin} has a group"
    assert "column.origin === origin" in results, "sorted by the origin the answer declares"
    # Shown or put away as a group, which is the two most common of the thirty decisions.
    assert "put them all away" in results and "show them all" in results


def test_the_new_column_controls_answer_to_the_keyboard() -> None:
    """feat-010/AC-74, feat-010/AC-75, feat-010/AC-17: this whole surface is keyboard operable.

    A `select` and a `button`, which are keyboard operable without anything being written here, and
    that is why they were chosen over a row of divs with click handlers.
    """
    results = script("results")
    control = results[results.index("function viewControl("):results.index("function redrawViewControl(")]
    assert 'el("select"' in control, "the view control is a real select"
    assert '"aria-label": "Which columns to open on"' in control
    chooser = results[results.index("function chooseColumns("):results.index("function filterBox(")]
    assert 'el("button"' in chooser, "each group's show-or-hide is a real button"


# ---------------------------------------------------------------------------
# Defects found by reading the interface back
# ---------------------------------------------------------------------------


def test_the_map_counts_what_is_held_back_over_the_same_properties_as_the_table() -> None:
    """feat-010/AC-67: the same words carrying a different number is worse than different words.

    The map counted the passed and the disappeared over the rows it could draw, so a search with
    properties that have no coordinates said "22 passed on, hidden" where the table said "737
    passed on, hidden" in the same words. AC-67 allows the map to draw fewer, for a reason it says
    out loud, and that reason is the properties with no location, which it counts separately.
    """
    fire = script("fire")
    start = fire.index("function counts(drawn)")
    counting = fire[start:fire.index("function ", start + 20)]
    assert "const every = held.all || held.rows;" in counting, (
        "the held-back counts are read off every row the run found"
    )
    for reason in ("kept", "passed", "gone"):
        assert f"const {reason} = every.filter(" in counting, f"{reason} is counted over all of them"
    assert "held.without" in counting, "and the ones with no location are still said separately"
    assert "held.all = found.rows;" in fire, "which means the answer's own rows are kept"


def test_a_thumbnail_that_has_loaded_is_not_asked_for_again() -> None:
    """feat-010/AC-43: a picture beside the address, rather than a box that blinks.

    The virtual window replaces every visible row on each redraw and a redraw happens on every
    scroll, so a fresh element each time was a fresh load each time and the pictures flickered
    between blank and loaded while somebody scrolled.
    """
    results = script("results")
    assert "const PICTURES = new Map();" in results
    body = results[results.index("function thumbnail("):results.index("async function showPhotos(")]
    assert "PICTURES.get(row.listing_id)" in body, "an element already holding a picture is reused"
    assert "PICTURES.set(row.listing_id, picture)" in body


def test_a_merge_events_records_are_readable_rather_than_clipped() -> None:
    """feat-010/AC-9: the timeline shows what happened, which a cut-off identifier does not."""
    listing_body = script("listing")
    assert "function ids(" in listing_body
    assert '/^[0-9a-f]{32}(,[0-9a-f]{32})*$/' in listing_body, "recognised as identifiers, not text"
    assert 'count(many.length, "record")' in listing_body, "the count is the part somebody wants"
    assert "overflow-wrap: anywhere" in (STATIC / "app.css").read_text(encoding="utf-8")


def test_the_builder_opens_on_the_areas_it_is_for() -> None:
    """feat-010/AC-2: areas are drawn and edited on this map, which means being able to see them.

    The default view was a fixed point at zoom eleven. For a search covering a state that opens
    inside one of its own polygons: a flat wash of colour with no edge on screen and nothing to say
    it is a shape.
    """
    search_body = script("search")
    assert "const bounds = drawn.getBounds();" in search_body
    assert "if (bounds.isValid()) map.fitBounds(" in search_body, "only when there is one to fit"


# ---------------------------------------------------------------------------
# feat-010/AC-76 to AC-82: counting, naming, explaining, and working the table
# ---------------------------------------------------------------------------


def test_every_total_says_which_properties_it_counts() -> None:
    """feat-010/AC-76: four screens, four populations, and one noun on all of them read as a fault."""
    assert "properties across every search" in script("searches")
    assert "in the latest run of this search" in script("results")
    assert "matched against the earlier run" in script("changes")
    assert "on the map" in script("fire"), "the map already said what it was counting"


def test_a_property_with_no_address_is_named_for_what_is_known() -> None:
    """feat-010/AC-77: the identifier is exact, and is not a thing a person can read or say."""
    common = script("common")
    assert "function propertyName(" in common, "one rule, because four surfaces name a property"
    assert "Unnamed property in ${where}" in common
    assert 'slice(0, 8)' in common, "and where nothing at all is known, a short identifier"
    for page in ("listing", "changes", "results", "fire"):
        assert "propertyName(" in script(page), f"{page} uses it"
    # Kept, and not led with.
    assert '"record "' in script("listing"), "the identifier is still on the page"


def test_the_instructions_are_behind_something_that_says_what_it_holds() -> None:
    """feat-010/AC-78: read once, and furniture on every visit after."""
    common = script("common")
    assert "function howItWorks(" in common
    assert 'el("details"' in common, "a disclosure, which the keyboard reaches without help"
    assert "homescout:read:" in common, "remembered per browser, on AC-45's terms"
    assert 'howItWorks("results", "How this table works"' in script("results")
    # The criterion explanation is said once above the list rather than under each of fifteen.
    search_body = script("search")
    assert "function whatEachDoes(" in search_body
    assert 'el("p", {class: "meta"}, said)' not in search_body, "no longer under every criterion"


def test_what_you_configure_and_what_you_run_are_two_surfaces() -> None:
    """feat-010/AC-79: eight sections in one scroll, with the ones you come back for seventh."""
    settings_body = script("settings")
    assert "function drawTools(" in settings_body
    assert 'pathParts()[0] === "tools"' in settings_body, "one script, one of two pages"
    assert "toolsPanel()" in settings_body and "exportPanel()" in settings_body
    # Settings keeps its address, so nothing anybody bookmarked stops answering.
    from homescout.web.wire import PAGES
    assert PAGES["/settings"] == PAGES["/tools"]
    assert '["/tools", "Tools"]' in script("common"), "the navigation reaches both"


def test_a_figure_that_can_be_zero_is_drawn_at_zero() -> None:
    """feat-010/AC-80: a tile appearing is harder to notice than a number changing."""
    searches_body = script("searches")
    strip = searches_body[searches_body.index("function overview()"):searches_body.index("function figure(")]
    for label in ("waiting for your decision", "to fix before they run", "running right now"):
        assert f'label: "{label}"' in strip
    assert "waiting\n      ? figure(" not in strip, "no longer drawn only when non-zero"
    assert strip.count("? figure(") == 0, "every figure in the strip is drawn"


def test_a_judgment_can_be_set_on_a_range_of_rows() -> None:
    """feat-010/AC-81: passing is the daily work and it was one row at a time, each through a dialog."""
    results = script("results")
    assert "function actingOn(" in results, "the selection, or the row the control was pressed on"
    assert "function pickRange(" in results
    assert "event.shiftKey" in results, "a range from the pointer"
    assert "if (event.shiftKey && wantedRow !== row)" in results, "and from the keyboard"
    # One write, by the core, rather than a loop here.
    writing = results[results.index("async function setJudgment("):]
    assert 'send("/api/judgments"' in writing
    assert "listing_ids: held.map(" in writing
    assert "answered.refused" in writing, "a batch that did not entirely succeed says so"
    assert "were set." in writing, "and never reports only what worked"


def test_a_builder_panel_says_when_it_is_unsaved() -> None:
    """feat-010/AC-82: the page used to apologise for this in its own opening line."""
    search_body = script("search")
    assert "const unsaved = new Set();" in search_body
    assert "function watchForEdits(" in search_body, "one listener per panel, not one per control"
    assert 'window.addEventListener("beforeunload"' in search_body, "leaving says so first"
    assert "Nothing is saved until you press a save button" not in search_body, (
        "the apology in the lede goes, because the design no longer needs one"
    )
    assert 'dataset: {panel: "areas"}' in search_body
    assert "section.unsaved" in (STATIC / "app.css").read_text(encoding="utf-8")
