"""Recording what a run's criteria decided, and leaving it recorded.

The reason verdicts are written down rather than recomputed is one test in this file: editing a
criterion must not change what an earlier run decided. Everything else here is in service of that.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import do_run, prop
from homescout.rules.definition import read
from homescout.rules.results import newly_fired
from homescout.rules.verdicts import evaluate_run, record, values_for
from homescout.store import Store


def rules(*entries):
    made, problems = read(list(entries))
    assert not [p for p in problems if p.severity == "problem"], problems
    return made


STALE = {"id": "stale", "when": "dom > 180", "severity": "flag"}
CHEAP = {"id": "cheap", "when": "price < 300000", "severity": "boost"}
NO_FIBER = {"id": "no-fiber", "when": "upload_mbps < 100", "severity": "drop"}


def test_a_run_records_a_verdict_for_every_property_and_every_criterion(store: Store) -> None:
    """feat-008/AC-22: the run's decisions, written down where a later run can compare them."""
    run = do_run(store, sources={"realtor": [prop("a1"), prop("a2", price=250_000)]})

    recorded = record(store, rules(STALE, CHEAP), run.id)

    assert len(recorded) == 4, "two properties, two criteria"
    assert {v.rule_id for v in recorded} == {"stale", "cheap"}
    # Read back by property and then by criterion, which is a stable order and not the order the
    # rules happen to be written in.
    assert store.verdicts(run.id) == sorted(recorded, key=lambda v: (v.listing_id, v.rule_id))


def test_a_verdict_nobody_could_reach_records_what_was_missing(store: Store) -> None:
    """feat-008/AC-11: which rule, and which field, so a person knows what to go and fetch."""
    run = do_run(store, sources={"realtor": [prop("a1")]})

    record(store, rules(NO_FIBER), run.id)

    found = store.verdicts(run.id)[0]
    assert found.verdict == "undetermined"
    assert found.missing == ("upload_mbps",)


def test_recorded_verdicts_cannot_be_rewritten(store: Store) -> None:
    """feat-008/AC-23: enforced by the database, not by a convention in a module somewhere."""
    import sqlite3

    run = do_run(store, sources={"realtor": [prop("a1")]})
    record(store, rules(STALE), run.id)

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.connection.execute("UPDATE rule_verdicts SET verdict = 'fired'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.connection.execute("DELETE FROM rule_verdicts")


def test_editing_a_criterion_changes_the_next_run_and_not_the_last_one(store: Store) -> None:
    """feat-008/AC-23: what a run decided is history, and history here is never rewritten.

    Recomputing verdicts on demand would fail this: today's criterion applied to last week's
    snapshot would silently restate what that run reported, and every digest already sent would
    disagree with the database it came from.
    """
    first = do_run(store, sources={"realtor": [prop("a1", price=350_000)]})
    record(store, rules({"id": "pricey", "when": "price > 300000", "severity": "flag"}), first.id)

    second = do_run(store, sources={"realtor": [prop("a1", price=350_000)]})
    record(store, rules({"id": "pricey", "when": "price > 400000", "severity": "flag"}), second.id)

    assert [v.verdict for v in store.verdicts(first.id)] == ["fired"]
    assert [v.verdict for v in store.verdicts(second.id)] == ["not-fired"]


def test_what_newly_fired_is_computable_between_any_two_runs(store: Store) -> None:
    """feat-008/AC-22: a badge appearing is news, and a badge that has been there a month is not."""
    quiet = do_run(store, sources={"realtor": [prop("a1", price=350_000), prop("a2")]})
    record(store, rules(STALE), quiet.id)

    later = do_run(store, sources={"realtor": [prop("a1", price=350_000), prop("a2")]})
    made = rules({"id": "stale", "when": "price > 300000", "severity": "flag"})
    record(store, made, later.id)

    fired_now = tuple(
        sorted(v.listing_id for v in store.verdicts(later.id) if v.verdict == "fired")
    )

    assert newly_fired(store, quiet.id, None) == {}
    assert newly_fired(store, later.id, quiet.id) == {"stale": fired_now}
    assert newly_fired(store, later.id, later.id) == {}, "nothing is new against itself"


def test_the_values_a_criterion_sees_come_from_this_tools_own_history(store: Store) -> None:
    """feat-008/AC-20: `dom` and the price movements are ours, computed from what we recorded."""
    first = do_run(store, sources={"realtor": [prop("a1", price=400_000)]})
    listing_id = store.listings()[0].id
    do_run(store, sources={"realtor": [prop("a1", price=350_000)]})
    third = do_run(store, sources={"realtor": [prop("a1", price=380_000)]})

    values = values_for(store, listing_id, run_id=third.id)

    assert values["price"] == 380_000, "the snapshot from the run being asked about"
    assert values["price_cut"] is True, "it went down once"
    assert values["price_raised_after_days"] == 0, "and back up, the same day"
    assert values["dom"] >= 0
    assert values["is_new"] is False
    assert values_for(store, listing_id, run_id=first.id)["is_new"] is True


def test_evaluating_the_same_run_twice_produces_the_same_rows_in_the_same_order(
    store: Store,
) -> None:
    """feat-008/AC-21: a recorded fact that varies with dictionary order is not reproducible."""
    run = do_run(store, sources={"realtor": [prop("a1"), prop("a2"), prop("a3")]})
    made = rules(STALE, CHEAP, NO_FIBER)

    once = evaluate_run(store, made, run.id)
    again = evaluate_run(store, made, run.id)

    assert once == again
    assert len(once) == 9


def test_a_search_with_no_criteria_records_nothing_and_costs_nothing(store: Store) -> None:
    """feat-008/AC-22: the spec's edge case. No rules is a state, not a special case."""
    run = do_run(store, sources={"realtor": [prop("a1")]})

    assert record(store, (), run.id) == ()
    assert store.verdicts(run.id) == []


def test_the_run_loop_records_verdicts_for_a_search_that_carries_rules(tmp_path: Path) -> None:
    """feat-008/AC-22: through the real loop, from a real definition file."""
    from cli_fakes import FakeSource, row
    from homescout import api
    from searches_fakes import sourced, workspace, write

    write(
        tmp_path / "searches",
        "criteria",
        text='name: criteria\nareas:\n  - {type: zip, value: "88130"}\nsources: [fake]\n'
        "rules:\n  - {id: cheap, when: 'price < 300000', severity: flag}\n",
    )

    with sourced("fake"), Store.open(tmp_path / "homescout.db") as store:
        source = FakeSource(rows=[row("a", price=250_000), row("b", price=900_000)])
        space = workspace(store, sources={"fake": source})
        outcome = api.run_search(space, "criteria")

        recorded = store.verdicts(outcome.run.id)
        assert {v.verdict for v in recorded} == {"fired", "not-fired"}
        assert {v.rule_id for v in recorded} == {"cheap"}
