"""What the verdicts mean for what a person sees: shown, badged, ordered, or removed and explained.

Every test here reads the recorded verdicts rather than re-evaluating, which is what makes what a
surface shows and what the database says the same thing by construction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import do_run, prop
from homescout.rules.definition import read
from homescout.rules.results import excluded, exclusion_counts, results
from homescout.rules.verdicts import record
from homescout.store import Store


def rules(*entries):
    made, problems = read(list(entries))
    assert not [p for p in problems if p.severity == "problem"], problems
    return made


def run_with(store: Store, entries, properties):
    run = do_run(store, sources={"realtor": list(properties)})
    record(store, rules(*entries), run.id)
    return run


def address_of(result) -> str:
    return result.fields.address_line


def test_a_dropped_property_leaves_the_results_and_keeps_its_history(store: Store) -> None:
    """feat-008/AC-3: excluded, never deleted. The whole point of a criterion you can change."""
    run = run_with(
        store,
        [{"id": "too-dear", "when": "price > 500000", "severity": "drop"}],
        [prop("a1", price=900_000), prop("a2", price=300_000)],
    )

    kept = results(store, run.id)

    assert [address_of(r) for r in kept] == ["a2 Example Road"]
    assert len(store.listings()) == 2, "both are still stored"
    assert len(store.snapshots_for_run(run.id)) == 2, "both were still observed"
    assert store.history(store.listings()[0].id).prices, "and still have their history"


def test_what_was_dropped_can_be_asked_for_by_name(store: Store) -> None:
    """feat-008/AC-4: a criterion that removes something must be auditable, or it is a black box."""
    run = run_with(
        store,
        [{"id": "too-dear", "when": "price > 500000", "severity": "drop"}],
        [prop("a1", price=900_000), prop("a2", price=300_000)],
    )

    removed = excluded(store, run.id)

    assert [address_of(r) for r in removed] == ["a1 Example Road"]
    assert removed[0].rules == ("too-dear",)
    assert exclusion_counts(store, run.id) == {"too-dear": 1}


def test_a_flag_marks_without_removing(store: Store) -> None:
    """feat-008/AC-5: a badge means look closer, not go away."""
    run = run_with(
        store,
        [{"id": "pricey", "when": "price > 500000", "severity": "flag"}],
        [prop("a1", price=900_000), prop("a2", price=300_000)],
    )

    kept = {address_of(r): r for r in results(store, run.id)}

    assert set(kept) == {"a1 Example Road", "a2 Example Road"}
    assert kept["a1 Example Road"].flags == ("pricey",)
    assert kept["a2 Example Road"].flags == ()


def test_boost_and_demote_decide_the_default_order_and_nothing_else(store: Store) -> None:
    """feat-008/AC-6: two otherwise equivalent properties, one boosted and one demoted."""
    run = run_with(
        store,
        [
            {"id": "cheap", "when": "price < 300000", "severity": "boost"},
            {"id": "tiny", "when": "sqft < 1000", "severity": "demote"},
        ],
        [
            prop("a1", price=250_000, sqft=2000),
            prop("a2", price=400_000, sqft=800),
            prop("a3", price=400_000, sqft=2000),
        ],
    )

    order = [address_of(r) for r in results(store, run.id)]

    assert order == ["a1 Example Road", "a3 Example Road", "a2 Example Road"]
    assert [r.score for r in results(store, run.id)] == [1, 0, -1]


def test_a_sort_the_user_asks_for_replaces_the_default_order(store: Store) -> None:
    """feat-008/AC-6: an explicit sort takes precedence over both boost and demote."""
    run = run_with(
        store,
        [{"id": "cheap", "when": "price < 300000", "severity": "boost"}],
        [prop("a1", price=250_000), prop("a2", price=400_000), prop("a3", price=100_000)],
    )

    ascending = [r.fields.price for r in results(store, run.id, sort="price")]
    descending = [r.fields.price for r in results(store, run.id, sort="price", descending=True)]

    assert ascending == [100_000, 250_000, 400_000]
    assert descending == [400_000, 250_000, 100_000]


def test_a_property_with_no_value_for_the_chosen_sort_goes_last_either_way(store: Store) -> None:
    """feat-008/AC-6: a missing price is not the cheapest house, and not the dearest one either."""
    run = run_with(store, [], [prop("a1", price=250_000), prop("a2", price=None)])

    for descending in (False, True):
        found = results(store, run.id, sort="price", descending=descending)
        assert [r.fields.price for r in found][-1] is None


def test_a_property_can_carry_several_verdicts_at_once(store: Store) -> None:
    """feat-008/AC-7: any number of flags, and boosts and demotes together, deterministically."""
    run = run_with(
        store,
        [
            {"id": "pricey", "when": "price > 300000", "severity": "flag"},
            {"id": "old", "when": "year_built < 2000", "severity": "flag"},
            {"id": "cheap-per-foot", "when": "price / sqft < 300", "severity": "boost"},
            {"id": "tiny", "when": "sqft < 3000", "severity": "demote"},
        ],
        [prop("a1", price=350_000, sqft=1800, year_built=1995)],
    )

    only = results(store, run.id)[0]

    assert only.flags == ("old", "pricey"), "sorted, so a badge list is stable"
    assert only.boosted == ("cheap-per-foot",)
    assert only.demoted == ("tiny",)
    assert only.score == 0, "one up and one down settle at nothing, which is documented and stable"


def test_a_drop_beats_everything_else_on_the_same_property(store: Store) -> None:
    """feat-008/AC-8: and the other verdicts are still recorded, so the reason is still visible."""
    run = run_with(
        store,
        [
            {"id": "too-dear", "when": "price > 300000", "severity": "drop"},
            {"id": "pricey", "when": "price > 300000", "severity": "flag"},
            {"id": "cheap-per-foot", "when": "price / sqft < 300", "severity": "boost"},
        ],
        [prop("a1", price=350_000, sqft=1800)],
    )

    assert results(store, run.id) == ()
    assert excluded(store, run.id)[0].rules == ("too-dear",)
    assert {v.rule_id for v in store.verdicts(run.id) if v.verdict == "fired"} == {
        "too-dear",
        "pricey",
        "cheap-per-foot",
    }


def test_a_verdict_nobody_could_reach_excludes_nothing_and_orders_nothing(store: Store) -> None:
    """feat-008/AC-10: undetermined is not a quiet no, and it does not nudge anything either."""
    run = run_with(
        store,
        [
            {"id": "no-fiber", "when": "upload_mbps < 100", "severity": "drop"},
            {"id": "far", "when": "elevation_ft > 6000", "severity": "demote"},
        ],
        [prop("a1")],
    )

    only = results(store, run.id)[0]

    assert only.score == 0
    assert only.flags == ()
    assert set(only.undetermined) == {"no-fiber", "far"}
    assert only.undetermined["no-fiber"] == ("upload_mbps",)
    assert exclusion_counts(store, run.id) == {}


def test_a_search_that_drops_everything_says_why(store: Store) -> None:
    """feat-008/AC-4: the spec's edge case, and the difference between a bug and a bad rule.

    An empty table with the counts beside it is a criterion working exactly as written. An empty
    table on its own is indistinguishable from a market that emptied out overnight.
    """
    run = run_with(
        store,
        [{"id": "everything", "when": "price > 0", "severity": "drop"}],
        [prop("a1"), prop("a2"), prop("a3")],
    )

    assert results(store, run.id) == ()
    assert exclusion_counts(store, run.id) == {"everything": 3}
    assert len(excluded(store, run.id)) == 3


def test_the_digest_reports_what_newly_tripped_a_criterion(tmp_path: Path) -> None:
    """feat-008/AC-22: through the command line, which is what a scheduled agent reads."""
    from cli_fakes import FakeSource, invoke, row
    from searches_fakes import sourced, write

    write(
        tmp_path / "searches",
        "criteria",
        text='name: criteria\nareas:\n  - {type: zip, value: "88130"}\nsources: [fake]\n'
        "rules:\n  - {id: pricey, when: 'price > 300000', severity: flag}\n"
        "  - {id: rejected, when: 'sqft < 100', severity: drop}\n",
    )
    db = tmp_path / "homescout.db"

    with sourced("fake"):
        from homescout.sources import register

        register("fake", lambda _s: FakeSource(rows=[row("a", price=250_000)]), replace=True)
        code, first, err = invoke(["run", "criteria", "--json", "--no-images"], db=db)
        assert code == 0, err
        assert json.loads(first)["searches"][0]["flagged"] == []

        register("fake", lambda _s: FakeSource(rows=[row("a", price=450_000)]), replace=True)
        code, second, err = invoke(["run", "criteria", "--json", "--no-images"], db=db)
        assert code == 0, err

    entry = json.loads(second)["searches"][0]
    assert entry["counts"]["flagged"] == 1
    assert entry["flagged"][0]["rules"] == ["pricey"]
    assert entry["excluded"] == {}, "nothing was dropped, and the section says so rather than lying"


def test_the_rules_section_survives_the_file_untouched(tmp_path: Path) -> None:
    """feat-008/AC-24: criteria round-trip losslessly, comments and all.

    The file format already guarantees this for everything it carries; what this asserts is that
    reading and checking the rules section did not quietly rewrite it on the way through.
    """
    from searches_fakes import catalog, sourced, write

    original = (
        "name: kept\n"
        "areas:\n"
        '  - {type: zip, value: "88130"}\n'
        "sources: [fake]\n"
        "rules:\n"
        "  # the one that matters most\n"
        "  - {id: stale, when: 'dom > 180', severity: flag}\n"
        "  - {id: no-fiber, when: 'upload_mbps < 100', severity: drop}\n"
    )
    path = write(tmp_path / "searches", "kept", text=original)

    with sourced("fake"):
        definition = catalog(tmp_path / "searches").load("kept")
        definition.document.write()

        assert path.read_text(encoding="utf-8") == original
        assert [rule.id for rule in definition.rules] == ["stale", "no-fiber"]


@pytest.fixture(autouse=True)
def _registered():
    from searches_fakes import sourced

    with sourced("fake"):
        yield
