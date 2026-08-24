"""What each surface actually shows, checked where each one can be.

Some of these are about the server's answer and some are about what the script does with it. The
second kind is checked by reading the script rather than by rendering, except where a browser is the
only honest place, which is `test_web_browser.py`.
"""

from __future__ import annotations

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
    assert "disappeared and hidden" in results, "and the count is said"
    assert 'id: "showgone"' in results, "the filter is always available"


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
