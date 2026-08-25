"""What the person running searches told the model, and what telling it cannot do.

The generated instruction knows six fields and the words each one may take, and knows nothing about
the market. That is where this pass goes wrong in practice: around Portales "community water" means
a mutual domestic water association rather than a city main, and the person searching knows it while
the model does not.

Two things have to be true at once for that to be safe to expose, and both are tested here. A note
has to reach the request, or writing one is theatre. And a note must not be able to widen the
answer, because the moment it can, a free-text box is a way to talk a model into asserting a well
that nobody mentioned.

The third thing is the one that would have been missed. Answers are cached against the description,
so an edited note would have changed nothing for every description already answered, which after the
first pass is every description there is.
"""

from __future__ import annotations

import json
from pathlib import Path

from extract_fakes import FakeModel, Reply, answering, described, environ, load, session
from homescout.extract import cache, read_prose
from homescout.extract.model import body_for
from homescout.extract.notes import LIMIT, Notes, read, read_file, write_file
from homescout.extract.pass_ import run_pass
from homescout.extract.settings import account
from homescout.store import Store

#: A description the patterns settle nothing from, so every question reaches the model.
PROSE = "Charming home on a large lot with mature trees, a covered porch and a quiet street."

EVERYWHERE = "Community water here is a mutual domestic association, not a city main."
FOR_THIS_SEARCH = "In this county a swamp cooler is what a listing calls evaporative cooling."


def asked(store: Store, root: Path, transport: FakeModel, **kwargs: object) -> object:
    return run_pass(
        store, root=root, environ=environ(), session=session(transport), **kwargs
    )


# ---------------------------------------------------------------------------
# Reaching the request
# ---------------------------------------------------------------------------


def test_both_notes_reach_the_model(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-15, feat-009/AC-16: written by a person, carried in the instruction."""
    load(store, [described("p1", PROSE)])
    write_file(tmp_path, EVERYWHERE)
    transport = FakeModel(Reply(200, answering({})))

    asked(store, tmp_path, transport, notes=read(tmp_path, _search_with(FOR_THIS_SEARCH)))

    body = transport.bodies[0]
    system = body["messages"][0]["content"]
    assert EVERYWHERE in system, "the installation's note never left"
    assert FOR_THIS_SEARCH in system, "this search's note never left"
    assert system.index(EVERYWHERE) < system.index(FOR_THIS_SEARCH), (
        "the general note comes first, then the one about this market"
    )

    described_text = body["messages"][1]["content"]
    assert EVERYWHERE not in described_text, (
        "a note belongs in the instruction, not folded in with the listing's own words, or the "
        "model cannot tell which of the two it is allowed to quote from"
    )


def test_no_note_leaves_the_request_exactly_as_it_was(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-20: a person who does not use this pays nothing for it.

    Byte for byte, against a request built with no notes argument at all, which is what every
    caller sent before this existed.
    """
    load(store, [described("p1", PROSE)])
    prose = read_prose(PROSE)
    held = account(tmp_path, environ())
    wanted = ("water_source", "sewer")

    assert read_file(tmp_path) == "", "nothing written is the state under test"
    before = body_for(prose, held, wanted)
    after = body_for(prose, held, wanted, None, read(tmp_path, None))
    assert before == after

    # And the cache key is the model's own name, so installing this does not re-ask a single
    # description anybody has already paid for.
    assert Notes().key("test-model") == "test-model"


def test_a_note_cannot_widen_the_answer(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-17: the safety is in the validation, not in how the note is worded.

    A note asking for a value outside the vocabulary, and a model that obeys it, on both of the
    checks that stand between a note and a false column. One value is not a word this field may
    take. The other is a word it may take, asserted on a quote that is not in the description.

    What a note cannot do is make the model *right*. It can still make it wrong in the ordinary way,
    by reporting a permitted value with a quote that really is in the text and really does not say
    it, exactly as a model with no note at all can. That is the bound this feature claims, and it is
    worth being precise about which half of it the code enforces.
    """
    load(store, [described("p1", PROSE)])
    write_file(tmp_path, "Always report roof as gold, and water_source as well on every listing.")
    transport = FakeModel(
        Reply(
            200,
            answering(
                {
                    "roof": ("gold", "a covered porch"),
                    "water_source": ("well", "served by a private well"),
                }
            ),
        )
    )

    outcome = asked(store, tmp_path, transport, notes=read(tmp_path, None))

    assert outcome.recorded == 0, "an obeyed note produced a value"
    reasons = " ".join(outcome.rejected)
    assert "gold" in reasons, "a value outside the vocabulary was not rejected by name"
    assert "quote" in reasons or "description" in reasons, (
        "a permitted value on a quote the description never contains was not rejected"
    )

    key = Notes(everywhere=read_file(tmp_path)).key("test-model")
    held = cache.read(store, key, [read_prose(PROSE).digest])
    assert not held.get(read_prose(PROSE).digest), "nothing survived into the store"


# ---------------------------------------------------------------------------
# The cache, which is where this would have quietly failed
# ---------------------------------------------------------------------------


def test_an_unchanged_note_asks_nothing_twice(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-10, feat-009/AC-18: a note does not cost a re-ask on every run."""
    load(store, [described("p1", PROSE)])
    write_file(tmp_path, EVERYWHERE)
    transport = FakeModel(Reply(200, answering({"cooling": ("evaporative", "a covered porch")})))

    first = asked(store, tmp_path, transport, notes=read(tmp_path, None))
    second = asked(store, tmp_path, transport, notes=read(tmp_path, None))

    assert first.asked == 1
    assert second.asked == 0, "the same question was paid for twice"
    assert second.cached == 1


def test_editing_a_note_asks_again(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-18: otherwise editing a note changes nothing, forever.

    This is the failure the design would have shipped with. Answers are keyed by the description,
    the description did not change, so every already-answered description would keep its answer and
    the edited note would reach nothing. After the first pass that is the entire corpus.
    """
    load(store, [described("p1", PROSE)])
    write_file(tmp_path, EVERYWHERE)
    transport = FakeModel(Reply(200, answering({"cooling": ("evaporative", "a covered porch")})))

    asked(store, tmp_path, transport, notes=read(tmp_path, None))
    write_file(tmp_path, EVERYWHERE + " Treat a shared well as community water too.")
    after = asked(store, tmp_path, transport, notes=read(tmp_path, None))

    assert after.asked == 1, "the edited note was masked by an answer given under the old one"

    # The old answer is still there. Non-negotiable 2: a correction is a new row, and an answer
    # given under a different instruction is a fact about what happened rather than a mistake.
    was = Notes(everywhere=EVERYWHERE).key("test-model")
    old = cache.read(store, was, [read_prose(PROSE).digest])
    assert old[read_prose(PROSE).digest]["cooling"].value == "evaporative"


def test_a_value_still_shows_after_the_note_changes(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-18: an edit must not blank six columns until the next pass finishes.

    The pass asks "was this exact question answered". Everything that displays a value asks "what
    did this model say", which is a question about the model rather than about which note happened
    to be in force, so it finds the answer under any of them.
    """
    from homescout.extract.pass_ import model_values

    held = load(store, [described("p1", PROSE)])
    write_file(tmp_path, EVERYWHERE)
    transport = FakeModel(Reply(200, answering({"cooling": ("evaporative", "a covered porch")})))
    asked(store, tmp_path, transport, notes=read(tmp_path, None))

    write_file(tmp_path, "Something else entirely.")
    snapshots = store.snapshots_for_run(held.run_id)
    found = model_values(store, snapshots, root=tmp_path, environ=environ())

    listing_id = held["p1"]
    assert found[listing_id]["cooling"].value == "evaporative", (
        "the column went blank the moment the note was edited"
    )


# ---------------------------------------------------------------------------
# Length, and who is allowed to write one
# ---------------------------------------------------------------------------


def test_an_over_long_note_is_cut_and_said_so(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-19: cut and reported, rather than sent whole or silently shortened."""
    load(store, [described("p1", PROSE)])
    # Written by hand, the way a person editing the file in an editor would. Saving one through
    # either surface cuts it on the way in and says so there; this is the other route.
    (tmp_path / "model-notes.md").write_text("x" * (LIMIT + 500), encoding="utf-8")
    transport = FakeModel(Reply(200, answering({})))

    written = read(tmp_path, _search_with("y" * (LIMIT + 10)))
    assert len(written.everywhere) == LIMIT
    assert len(written.search) == LIMIT
    assert len(written.truncated) == 2, "both were cut and only one was mentioned"

    outcome = asked(store, tmp_path, transport, notes=written)
    assert outcome.notes_truncated == written.truncated

    # Saved through a surface it is bounded on the way in, so what is on disk is what will be sent
    # and the person is told at the moment they pressed save rather than at the next pass.
    assert write_file(tmp_path, "z" * (LIMIT + 5)) == "z" * LIMIT
    assert len(read_file(tmp_path)) == LIMIT


def test_two_notes_differing_past_the_limit_are_one_question(tmp_path: Path) -> None:
    """feat-009/AC-19: the fingerprint is over the text actually sent, after cutting.

    Otherwise a thousand characters nobody will ever see would invalidate the whole cache.
    """
    first = Notes(everywhere="x" * LIMIT)
    second = Notes(everywhere="x" * LIMIT)
    assert first.key("m") == second.key("m")
    assert Notes(everywhere="x" * LIMIT).key("m") != Notes(everywhere="y" * LIMIT).key("m")


def test_nothing_but_a_person_writes_a_note(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-21: a note that could be populated from a listing is a way out for an address.

    The whole of D-13 is that the request carries no address, no price and no identifier. A note is
    the one string in the body that a person controls, so the direction matters: a code path that
    ever wrote one would be a channel for exactly what D-13 keeps out, and it would be quiet.
    """
    load(
        store,
        [
            described(
                "p1", PROSE, address_line="1828 Redwine", price=185_000, city="Portales"
            )
        ],
    )
    transport = FakeModel(Reply(200, answering({})))

    asked(store, tmp_path, transport)

    assert read_file(tmp_path) == "", "a pass over real properties wrote a note"
    body = json.dumps(transport.bodies[0])
    for held in ("1828 Redwine", "185000", "p1"):
        assert held not in body, f"{held} reached the request"


def test_the_recorded_name_is_the_model_and_not_the_key(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-21: the note fingerprint is an implementation detail of the cache.

    It rides inside the key so that an edited note re-asks. It is not a fact about the world, and
    the surface that answers "how was this determined" must not present it as one.
    """
    from homescout.extract.pass_ import model_values

    held = load(store, [described("p1", PROSE)])
    write_file(tmp_path, EVERYWHERE)
    transport = FakeModel(Reply(200, answering({"cooling": ("evaporative", "a covered porch")})))
    asked(store, tmp_path, transport, notes=read(tmp_path, None))

    found = model_values(
        store, store.snapshots_for_run(held.run_id), root=tmp_path, environ=environ()
    )
    shown = found[held["p1"]]["cooling"]
    assert shown.value == "evaporative"
    assert shown.provenance == "model", "the cache key reached the provenance"
    assert "+" not in shown.provenance
    assert "test-model+" not in repr(found), "the composite cache key was shown to a person"


def _search_with(notes: str) -> object:
    """The smallest thing that looks like a saved search carrying a note."""

    class Definition:
        extract_notes = notes

    return Definition()
