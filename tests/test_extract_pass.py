"""The model pass: what it asks about, what it never asks about twice, and what a failure costs.

The three claims worth proving are all about restraint. It asks about descriptions rather than
properties, it asks about fields the patterns could not settle rather than all six, and it asks once
ever rather than once a night. Get any of those wrong and the feature is a bill.
"""

from __future__ import annotations

from pathlib import Path

from extract_fakes import FakeModel, Reply, answering, described, environ, load, session
from homescout.extract import values_for
from homescout.extract.pass_ import for_run, model_values, run_pass
from homescout.store import Store

WELL = "The property has its own private well."
QUIET = "A charming home close to schools, with a large fenced yard and mature trees."
ALSO_QUIET = "A comfortable two bedroom on a corner lot, freshly painted throughout."

#: A well-formed answer this fake model gives about anything it is asked.
SEPTIC = Reply(200, answering({"sewer": ("septic", "close to schools")}))


class Prop:
    def __init__(self, description: str | None) -> None:
        self.description = description


def go(store: Store, root: Path, transport: FakeModel, **kwargs):
    return run_pass(
        store, root=root, environ=environ(), session=session(transport), **kwargs
    )


# ---------------------------------------------------------------------------
# What it asks about
# ---------------------------------------------------------------------------


def test_it_asks_about_descriptions_rather_than_properties(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-10: three properties sharing one description are one question."""
    load(store, [described(f"p{n}", QUIET) for n in range(1, 4)])
    transport = FakeModel(SEPTIC)

    outcome = go(store, tmp_path, transport)

    assert outcome.descriptions == 1, "three properties, one distinct description"
    assert outcome.asked == 1
    assert len(transport.requests) == 1


def test_it_never_asks_about_the_same_description_twice(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-10: regardless of how many properties or runs contain it."""
    load(store, [described("p1", QUIET)])
    transport = FakeModel(SEPTIC)

    first = go(store, tmp_path, transport)
    second = go(store, tmp_path, transport)

    assert first.asked == 1
    assert second.asked == 0 and second.cached == 1
    assert len(transport.requests) == 1, "the second pass made no request at all"


def test_a_cached_answer_survives_the_process(store: Store, tmp_path: Path, db_path: Path) -> None:
    """feat-009/AC-10: cached in the database, not in an object that dies with the run."""
    load(store, [described("p1", QUIET)])
    go(store, tmp_path, FakeModel(SEPTIC))
    store.close()

    with Store.open(db_path) as reopened:
        again = go(reopened, tmp_path, FakeModel(SEPTIC))
        assert again.asked == 0 and again.cached == 1


def test_it_asks_only_about_what_the_patterns_could_not_settle(
    store: Store, tmp_path: Path
) -> None:
    """The baseline runs first and is free, so a market that states its plumbing costs nothing."""
    load(store, [described("p1", WELL)])
    transport = FakeModel(Reply(200, answering({})))

    go(store, tmp_path, transport)

    said = transport.prompt_text()
    assert "water_source:" not in said, "the patterns already answered this one"
    assert "sewer:" in said and "roof:" in said


def test_a_description_the_patterns_fully_settle_is_never_asked_about(
    store: Store, tmp_path: Path
) -> None:
    """Nothing left open means nothing to ask, which must not become an empty request."""
    complete = (
        "The property has its own private well and a new septic system, central heat and air, "
        "natural gas, and a durable metal roof."
    )
    load(store, [described("p1", complete)])
    transport = FakeModel(SEPTIC)

    outcome = go(store, tmp_path, transport)

    assert transport.requests == []
    assert outcome.cached == 1


def test_a_property_with_no_description_is_not_a_question(store: Store, tmp_path: Path) -> None:
    """The spec's own edge case: extraction produces nothing and reports nothing unusual."""
    load(store, [described("p1", None), described("p2", "   ")])
    transport = FakeModel(SEPTIC)

    outcome = go(store, tmp_path, transport)

    assert transport.requests == []
    assert outcome.skipped and "description" in outcome.skipped


# ---------------------------------------------------------------------------
# What a failure costs
# ---------------------------------------------------------------------------


def test_one_descriptions_failure_does_not_end_the_pass(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-11: reported, and the pass carries on to everything after it.

    The failing one fails every time rather than once, because the paced session retries and a
    transport that fails once would simply be retried into succeeding, which is the session doing
    its job and not this pass doing its own.
    """
    load(store, [described("p1", QUIET), described("p2", ALSO_QUIET)])

    def sometimes(request):
        if QUIET in request.body.decode("utf-8"):
            raise TimeoutError("the model timed out")
        return SEPTIC

    transport = FakeModel(sometimes)
    outcome = go(store, tmp_path, transport)

    assert len(outcome.failures) == 1
    assert outcome.asked == 1, "the second description was still processed"
    assert outcome.degraded


def test_a_failure_leaves_the_deterministic_values_alone(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-11: they never involved a network, so nothing about one can take them away."""
    loaded = load(store, [described("p1", WELL)])
    go(store, tmp_path, FakeModel(RuntimeError("the model is down")))

    snapshot = store.snapshot_at(loaded["p1"], loaded.run_id)
    assert snapshot is not None
    assert values_for(snapshot.fields)["water_source"].value == "well"


def test_a_failure_leaves_the_affected_fields_empty(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-11: empty rather than filled by a fallback, which is the whole product rule."""
    loaded = load(store, [described("p1", QUIET)])
    go(store, tmp_path, FakeModel(RuntimeError("the model is down")))

    snapshot = store.snapshot_at(loaded["p1"], loaded.run_id)
    assert snapshot is not None
    held = model_values(store, [snapshot], root=tmp_path, environ=environ())
    assert held.get(loaded["p1"], {}) == {}
    assert all(entry.value is None for entry in values_for(snapshot.fields).values())


def test_a_failure_is_not_cached_as_an_answer(store: Store, tmp_path: Path) -> None:
    """Because a model that was down for an hour must be asked again, unlike one that said no."""
    load(store, [described("p1", QUIET)])
    go(store, tmp_path, FakeModel(RuntimeError("the model is down")))

    transport = FakeModel(SEPTIC)
    again = go(store, tmp_path, transport)
    assert again.asked == 1


def test_an_answered_nothing_is_cached(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-10: the nothings matter as much as the values, or they are paid for nightly."""
    load(store, [described("p1", QUIET)])
    transport = FakeModel(Reply(200, answering({})))

    go(store, tmp_path, transport)
    again = go(store, tmp_path, transport)

    assert again.asked == 0
    assert len(transport.requests) == 1


def test_a_rejected_answer_is_counted_and_named(store: Store, tmp_path: Path) -> None:
    """A model being rejected nine times in ten is worth knowing about."""
    load(store, [described("p1", QUIET)])
    unattributable = Reply(
        200, answering({"sewer": ("septic", "a sentence that is not in the description")})
    )

    outcome = go(store, tmp_path, FakeModel(unattributable))

    assert outcome.recorded == 0
    assert len(outcome.rejected) == 1
    assert "quote is not in the description" in outcome.rejected[0]


# ---------------------------------------------------------------------------
# Configuration and reach
# ---------------------------------------------------------------------------


def test_no_model_configured_is_reported_rather_than_attempted(
    store: Store, tmp_path: Path
) -> None:
    """feat-009/AC-11, the spec's own edge case: at validation time, not per property."""
    load(store, [described("p1", QUIET)])
    transport = FakeModel(SEPTIC)

    outcome = run_pass(store, root=tmp_path, environ={}, session=session(transport))

    assert transport.requests == []
    assert outcome.skipped and "HOMESCOUT_EXTRACT_MODEL" in outcome.skipped
    assert not outcome.degraded, "unconfigured is not a failure"


def test_the_pass_can_be_narrowed_to_one_saved_search(store: Store, tmp_path: Path) -> None:
    load(store, [described("p1", QUIET)], search="north")
    load(store, [described("p2", ALSO_QUIET)], search="south")
    transport = FakeModel(SEPTIC)

    outcome = go(store, tmp_path, transport, search="north")

    assert outcome.asked == 1
    assert QUIET in transport.prompt_text()


def test_a_bounded_pass_says_what_it_left(store: Store, tmp_path: Path) -> None:
    """No silent caps: a truncation nobody reports reads as a market with nothing in it."""
    load(store, [described(f"p{n}", f"{QUIET} Number {n}.") for n in range(1, 6)])
    transport = FakeModel(Reply(200, answering({})))

    outcome = go(store, tmp_path, transport, limit=2)

    assert outcome.asked == 2
    assert outcome.skipped == "3 descriptions left for a later pass"


def test_a_search_that_did_not_ask_for_a_model_gets_no_pass(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-6: off by default, and off means nothing in this feature runs."""

    class Definition:
        name = "north"
        model_extraction = False

    load(store, [described("p1", QUIET)])
    assert for_run(store, Definition(), root=tmp_path, environ=environ()) is None


def test_a_search_that_asked_for_a_model_gets_one(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-6: enabled per saved search, and that is the only switch."""

    class Definition:
        name = "town"
        model_extraction = True

    load(store, [described("p1", QUIET)], search="town")
    transport = FakeModel(SEPTIC)

    outcome = for_run(
        store, Definition(), root=tmp_path, environ=environ(), session=session(transport)
    )

    assert outcome is not None and outcome.asked == 1


def test_a_model_value_reaches_a_criterion(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-3: the point of the whole pass, from a request to a rule's field namespace."""
    loaded = load(store, [described("p1", QUIET)])
    go(store, tmp_path, FakeModel(SEPTIC))

    snapshot = store.snapshot_at(loaded["p1"], loaded.run_id)
    assert snapshot is not None
    held = model_values(store, [snapshot], root=tmp_path, environ=environ())
    found = values_for(snapshot.fields, model=held[loaded["p1"]])
    assert found["sewer"].value == "septic"
    assert found["sewer"].provenance == "model"
    assert found["sewer"].evidence == ("close to schools",)
