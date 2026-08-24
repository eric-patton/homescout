"""The tool with no model configured at all, which is how it ships and how most people will run it.

Product invariant 9 says an unconfigured optional component leaves the tool fully functional, and
the spec says the same thing twice: the model pass is off by default, and with it off nothing
contacts a model, reads a credential, or is required to exist.

Proved hostilely rather than by inspection. The environment is stripped of every variable this
feature knows about, `requests` is replaced with something that fails loudly if anything touches it,
and the whole tool is run end to end.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from cli_fakes import invoke, row, search, workspace
from extract_fakes import described, load
from homescout import api
from homescout.extract import settings, values_for
from homescout.extract.pass_ import run_pass
from homescout.store import Store

WELL = "This home sits on 5 acres with its own private well and a new septic system."


@pytest.fixture(autouse=True)
def no_model_anywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every variable this feature reads, removed, including the shared OpenAI one."""
    for name in settings.VARIABLES:
        monkeypatch.delenv(name, raising=False)


class Tripwire:
    """A transport that fails the test rather than the request.

    Substituted for the real one so that "no request was made" is proved by nothing being able to
    make one, rather than by counting calls to something that was allowed to happen.
    """

    def __call__(self, request: object) -> None:
        raise AssertionError(f"something reached the network with no model configured: {request}")


def test_the_deterministic_values_need_no_configuration(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-1: no key, no address, no network, and the six fields still fill."""
    loaded = load(store, [described("p1", WELL)])
    snapshot = store.snapshot_at(loaded["p1"], loaded.run_id)
    assert snapshot is not None

    found = values_for(snapshot.fields)
    assert found["water_source"].value == "well"
    assert found["sewer"].value == "septic"
    assert found["water_source"].provenance == "pattern"


def test_nothing_is_contacted_and_no_credential_is_read(store: Store, tmp_path: Path) -> None:
    """feat-009/AC-7: the pass reports itself unconfigured instead of trying."""
    load(store, [described("p1", "A quiet home on a corner lot with mature trees.")])

    outcome = run_pass(store, root=tmp_path, session=Tripwire())

    assert outcome.asked == 0
    assert outcome.skipped and "HOMESCOUT_EXTRACT_MODEL" in outcome.skipped
    assert not outcome.degraded, "not configured is not a failure"


def test_reading_values_for_a_criterion_reads_no_credential(store: Store, tmp_path: Path) -> None:
    """The common path, run on every property of every run: it must cost nothing at all."""
    from homescout.extract.pass_ import model_values

    loaded = load(store, [described("p1", WELL)])
    snapshot = store.snapshot_at(loaded["p1"], loaded.run_id)
    assert snapshot is not None
    assert model_values(store, [snapshot], root=tmp_path) == {}


def test_a_saved_search_says_nothing_about_extraction_by_default() -> None:
    """feat-009/AC-6: off unless a file turns it on, and the template does not mention it."""
    from homescout.search.definition import TEMPLATE

    assert "extract" not in TEMPLATE
    assert search().model_extraction is False if hasattr(search(), "model_extraction") else True


def test_the_whole_tool_runs_end_to_end_with_no_model(store: Store) -> None:
    """feat-009/AC-7: a run, its criteria and its digest, with nothing configured."""
    from cli_fakes import FakeSource

    source = FakeSource(rows=[row("a", description=WELL)])
    held = workspace(store, searches=[search()], sources={"fake": source})
    outcome = api.run_search(held, "portales")

    assert outcome.run.status == "completed"
    assert not outcome.degraded
    assert outcome.extraction is None, "the search did not ask for a model, so there was no pass"
    assert outcome.comparison.counts["new"] == 1

    listing_id = outcome.comparison.events[0].listing_id
    snapshot = store.snapshot_at(listing_id, outcome.run.id)
    assert snapshot is not None
    assert values_for(snapshot.fields)["water_source"].value == "well"


def test_the_command_line_runs_with_no_model_configured(db_path: Path) -> None:
    """feat-009/AC-7, from the outside: the surface a scheduled task drives."""
    code, out, err = invoke(["searches", "list"], db=db_path)
    assert code == 0, err

    code, out, err = invoke(["extract", "--json"], db=db_path)
    # Nothing to do and nothing configured, which is a clean exit rather than a failure: the tool
    # is complete without this.
    assert code == 0, err
    assert "HOMESCOUT_EXTRACT_MODEL" in out or "description" in out


def test_the_extraction_variables_are_named_in_one_place() -> None:
    """So the example file, the documentation and this test cannot drift apart from the code."""
    assert settings.VARIABLES == (
        "HOMESCOUT_EXTRACT_BASE_URL",
        "HOMESCOUT_EXTRACT_MODEL",
        "HOMESCOUT_EXTRACT_API_KEY",
        "OPENAI_API_KEY",
    )
    assert all(name not in os.environ for name in settings.VARIABLES)


def test_asking_what_was_read_out_of_one_property(store: Store, db_path: Path) -> None:
    """The user story that had no surface: knowing how each value was determined.

    A value with no visible reason is a value nobody can argue with, and a person who cannot argue
    with it cannot trust it either. So both sentences come back for a field that could not be
    settled, which is the case that most needs explaining.
    """
    both = "The property includes a well, two septic systems, and access to city water."
    loaded = load(store, [described("p1", both)])
    store.close()

    code, out, err = invoke(["extract", "--listing", loaded["p1"]], db=db_path)

    assert code == 0, err
    assert "water source: could not tell" in out
    assert "sewer: septic  (from the pattern)" in out
    assert both in out, "and the sentence it was decided from"
    assert "heating: not stated" in out


def test_asking_about_a_property_that_is_not_there(store: Store, db_path: Path) -> None:
    """Invalid input, named, rather than an empty answer that looks like a silent listing."""
    store.close()
    code, _out, err = invoke(["extract", "--listing", "nope"], db=db_path)
    assert code != 0
    assert "nope" in err
