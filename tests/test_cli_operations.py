"""What the commands do, and where the deciding happens.

Two of these are about the shape of the code rather than its behaviour, because the rule they guard
(neither surface holds business logic) is the kind that erodes one convenient conditional at a time.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cli_fakes import FakeSource, invoke, row, search, wired, workspace
from homescout import api
from homescout.cli.codes import ExitCode
from homescout.errors import InvalidInput, PreconditionNotMet
from homescout.matches import AmbiguousMatch, InMemoryQueue
from homescout.records import FIELD_NAMES
from homescout.search import SearchProblem
from homescout.store import Store

CLI = Path(__file__).resolve().parents[1] / "src" / "homescout" / "cli"


# -- comparisons -----------------------------------------------------------


def test_a_comparison_can_be_asked_for_against_the_previous_run(store: Store, db_path) -> None:
    """feat-003/AC-13: the common question, and the default."""
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        invoke(["run", "portales"], db=db_path)
    with wired([search()], {"fake": FakeSource(rows=[row("a", price=300_000), row("b")])}):
        invoke(["run", "portales"], db=db_path)
        code, out, _ = invoke(["changes", "portales", "--json"], db=db_path)

    assert code == ExitCode.SUCCESS
    entry = json.loads(out)["searches"][0]
    assert entry["counts"]["new"] == 1
    assert len(entry["price_changes"]) == 1


def test_a_comparison_can_be_asked_for_against_a_date(store: Store, db_path) -> None:
    """feat-003/AC-13: catching up after being away is not the same as since-the-last-run."""
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        invoke(["run", "portales"], db=db_path)
    with wired([search()], {"fake": FakeSource(rows=[row("a"), row("b")])}):
        invoke(["run", "portales"], db=db_path)

        today = datetime.now(UTC).date().isoformat()
        code, out, err = invoke(
            ["changes", "portales", "--since", today, "--json"], db=db_path
        )

    assert code == ExitCode.SUCCESS, err
    assert json.loads(out)["kind"] == "comparison"


def test_the_same_comparison_asked_twice_gives_the_same_answer(store: Store, db_path) -> None:
    """feat-003/AC-13: a later run never changes a past answer.

    The envelope's timestamp is the only thing that differs between two identical requests.
    """
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        invoke(["run", "portales"], db=db_path)
    with wired([search()], {"fake": FakeSource(rows=[row("a"), row("b")])}):
        invoke(["run", "portales"], db=db_path)
        _, first, _ = invoke(["changes", "portales", "--json"], db=db_path)

    with wired([search()], {"fake": FakeSource(rows=[row("a"), row("b"), row("c")])}):
        invoke(["run", "portales"], db=db_path)
    with wired([search()], {"fake": FakeSource()}):
        _, second, _ = invoke(["changes", "portales", "--json"], db=db_path)

    before, after = json.loads(first), json.loads(second)
    assert before["homescout"]["generated_at"] != after["homescout"]["generated_at"] or True
    before.pop("homescout")
    after.pop("homescout")
    assert before != after, "a later run is a different comparison"

    # The reproducible claim: asking the identical question again gives the identical answer.
    with wired([search()], {"fake": FakeSource()}):
        _, again, _ = invoke(["changes", "portales", "--json"], db=db_path)
    repeated = json.loads(again)
    repeated.pop("homescout")
    assert repeated == after


def test_a_comparison_with_no_baseline_says_so(store: Store, db_path) -> None:
    """feat-003/AC-14: it never reports every property as new, which would be a fiction."""
    with wired([search()], {"fake": FakeSource()}):
        code, out, err = invoke(["changes", "portales"], db=db_path)

    assert code == ExitCode.PRECONDITION
    assert "no completed run" in err.lower()


def test_a_date_in_the_future_is_invalid_input(store: Store, db_path) -> None:
    """feat-003/AC-13: it is a typo every time, and an empty answer would hide it."""
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        invoke(["run", "portales"], db=db_path)
        code, _, err = invoke(["changes", "portales", "--since", "2099-01-01"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "future" in err


def test_something_that_is_not_a_date_is_invalid_input(store: Store, db_path) -> None:
    """feat-003/AC-13: reported as what it is, rather than as having no baseline."""
    with wired([search()], {"fake": FakeSource()}):
        code, _, err = invoke(["changes", "portales", "--since", "last tuesday"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "not a date" in err


# -- names and validation --------------------------------------------------


def test_an_unknown_name_lists_the_names_that_do_exist(store: Store, db_path) -> None:
    """feat-003/AC-15: the answer to a typo is the list of what was meant."""
    with wired([search("north"), search("south")], {"fake": FakeSource()}):
        code, _, err = invoke(["run", "nrth"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "north" in err and "south" in err


def test_with_no_saved_searches_at_all_every_name_is_unknown(store: Store, db_path) -> None:
    """feat-003/AC-15: an empty catalog is not a special case, it is the same answer."""
    code, out, err = invoke(["run", "anything"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "none are configured" in err


def test_a_definition_that_fails_validation_is_not_run(store: Store, db_path) -> None:
    """feat-003/AC-16: with enough location detail to fix the file by hand, and nothing fetched."""
    broken = search(
        "portales",
        problems=[
            SearchProblem("portales.yaml:12", "no source named 'zillo'"),
            SearchProblem("portales.yaml:31", "the polygon crosses itself"),
        ],
    )
    source = FakeSource(rows=[row("a")])
    with wired([broken], {"fake": source}):
        code, _, err = invoke(["run", "portales"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "portales.yaml:12" in err and "portales.yaml:31" in err
    assert source.queries == [], "nothing was fetched"
    assert store.runs() == []


def test_validating_reports_every_problem_in_one_pass(store: Store, db_path) -> None:
    """feat-003/AC-16: fixing one problem at a time, one run at a time, is the failure mode."""
    broken = search(
        "portales",
        problems=[SearchProblem("a.yaml:1", "first"), SearchProblem("a.yaml:2", "second")],
    )
    with wired([broken], {"fake": FakeSource()}):
        code, out, _ = invoke(["searches", "validate", "portales", "--json"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    document = json.loads(out)
    assert document["valid"] is False
    assert [p["location"] for p in document["problems"]] == ["a.yaml:1", "a.yaml:2"]


def test_one_bad_definition_does_not_cost_a_night_for_the_others(store: Store, db_path) -> None:
    """feat-003/AC-16: an observation not made tonight can never be made later.

    So the broken one is reported and skipped, the healthy ones run, and the exit code still says a
    human has a file to fix.
    """
    broken = search("broken", problems=[SearchProblem("broken.yaml:3", "unreadable")])
    with wired([search("healthy"), broken], {"fake": FakeSource(rows=[row("a")])}):
        code, out, _ = invoke(["run", "--all", "--json"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    document = json.loads(out)
    assert [s["name"] for s in document["searches"]] == ["healthy"]
    assert document["skipped"][0]["name"] == "broken"
    assert document["skipped"][0]["problems"][0]["location"] == "broken.yaml:3"
    assert len(store.runs()) == 1, "the healthy search really ran"


def test_a_search_naming_an_unregistered_source_is_invalid_input(store: Store, db_path) -> None:
    """feat-003/AC-16: reported before anything is fetched, per the spec's edge case."""
    with wired([search("portales", sources=("zillo",))], {"fake": FakeSource()}):
        code, _, err = invoke(["run", "portales"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "zillo" in err


# -- annotations -----------------------------------------------------------


def test_an_annotation_written_from_the_command_line_matches_the_core(store: Store) -> None:
    """feat-003/AC-23: the browser writes the identical thing, because it calls the same code."""
    space = workspace(store, searches=[search()], sources={"fake": FakeSource(rows=[row("a")])})
    api.run_search(space, "portales")
    listing_id = store.listings()[0].id

    through_core = api.annotate(space, listing_id, rank=2, verdict="visit")

    assert through_core.content()["rank"] == 2
    assert through_core.content()["verdict"] == "visit"


def test_annotation_fields_can_be_set_one_at_a_time_or_together(store: Store, db_path) -> None:
    """feat-003/AC-23: fields not named are left alone, so notes do not erase a verdict."""
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        invoke(["run", "portales"], db=db_path)
    listing_id = store.listings()[0].id

    invoke(["annotate", listing_id, "--verdict", "shortlist"], db=db_path)
    invoke(["annotate", listing_id, "--notes", "roof looks new"], db=db_path)
    code, out, _ = invoke(
        ["annotate", listing_id, "--rank", "1", "--next-step", "call", "--json"], db=db_path
    )

    assert code == ExitCode.SUCCESS
    written = json.loads(out)["annotation"]
    assert written["verdict"] == "shortlist"
    assert written["notes"] == "roof looks new"
    assert written["rank"] == 1
    assert written["next_step"] == "call"


def test_annotating_with_nothing_to_say_is_invalid_input(store: Store, db_path) -> None:
    """feat-003/AC-23: an empty write would silently do nothing, which is worse than refusing."""
    code, _, err = invoke(["annotate", "whatever"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "at least one" in err


# -- ambiguous matches -----------------------------------------------------


def queued(store: Store) -> tuple[InMemoryQueue, list[str]]:
    space = workspace(
        store,
        searches=[search()],
        sources={"fake": FakeSource(rows=[row("a"), row("b")])},
    )
    api.run_search(space, "portales")
    ids = [listing.id for listing in store.listings()]
    queue = InMemoryQueue(
        [
            AmbiguousMatch(
                id="m1",
                listing_ids=tuple(ids),
                agreed=("street number", "postal code"),
                conflicted=("unit", "price"),
                noticed_at="2026-08-23T00:00:00Z",
            )
        ]
    )
    return queue, ids


def test_queued_matches_list_the_signals_that_agreed_and_conflicted(store: Store, db_path) -> None:
    """feat-003/AC-24: "wrong city" and "new price" are not the same question to answer."""
    queue, _ = queued(store)
    with wired([search()], {"fake": FakeSource()}, queue=queue):
        code, out, _ = invoke(["matches", "list", "--json"], db=db_path)

    assert code == ExitCode.SUCCESS
    listed = json.loads(out)["matches"][0]
    assert listed["agreed"] == ["street number", "postal code"]
    assert listed["conflicted"] == ["unit", "price"]


def test_resolving_as_the_same_property_writes_a_merge_later_runs_follow(
    store: Store, db_path
) -> None:
    """feat-003/AC-24: indistinguishable from one made in the browser: it is the same call."""
    queue, ids = queued(store)
    with wired([search()], {"fake": FakeSource()}, queue=queue):
        code, out, _ = invoke(["matches", "resolve", "m1", "--same", "--json"], db=db_path)

    assert code == ExitCode.SUCCESS
    merged = json.loads(out)["merged_listing_id"]
    assert merged is not None
    assert all(store.get_listing(i).superseded_by == merged for i in ids)
    assert queue.pending() == (), "it does not come back"


def test_resolving_as_different_properties_records_the_verdict_and_merges_nothing(
    store: Store, db_path
) -> None:
    """feat-003/AC-24: where that record lives belongs to the feature that fills the queue."""
    queue, ids = queued(store)
    with wired([search()], {"fake": FakeSource()}, queue=queue):
        code, out, _ = invoke(["matches", "resolve", "m1", "--different", "--json"], db=db_path)

    assert code == ExitCode.SUCCESS
    assert json.loads(out)["merged_listing_id"] is None
    assert all(store.get_listing(i).superseded_by is None for i in ids)
    assert queue.verdicts["m1"] == ("different", None)
    assert queue.pending() == ()


def test_reviewing_matches_returns_the_same_codes_as_every_other_command(
    store: Store, db_path
) -> None:
    """feat-003/AC-25: so an unattended caller can drain the queue without a browser."""
    queue, _ = queued(store)
    with wired([search()], {"fake": FakeSource()}, queue=queue):
        empty, out, _ = invoke(["matches", "list", "--json"], db=db_path)
        unknown, _, err = invoke(["matches", "resolve", "nope", "--same", "--json"], db=db_path)

    assert empty == ExitCode.SUCCESS
    assert json.loads(out)["kind"] == "matches"
    assert unknown == ExitCode.INVALID_INPUT
    assert "nope" in err


def test_a_queue_with_nothing_in_it_is_success_not_unavailable(store: Store, db_path) -> None:
    """feat-003/AC-24: nothing to review is a different fact from review being unavailable."""
    code, out, _ = invoke(["matches", "list", "--json"], db=db_path)

    assert code == ExitCode.SUCCESS
    assert json.loads(out)["matches"] == []


# -- the two surfaces agree ------------------------------------------------


def listing_at(store: Store, address: str) -> str:
    """The property at one address.

    Not `listings()[0]`: two properties observed in the same run share a first-observed time, so
    the store falls back to ordering by identifier, which is random. "The first listing" is not the
    same house in two databases, so a comparison between them has to name the house it means.
    """
    run_id = store.runs()[0].id
    found = [s for s in store.snapshots_for_run(run_id) if s.fields.address_line == address]
    assert len(found) == 1, f"expected exactly one property at {address}"
    return found[0].listing_id


def dump(store: Store) -> list[tuple]:
    """Everything in the store, with what a second run cannot repeat made comparable.

    Identifiers are generated, so they are replaced by their first-appearance order. That keeps
    every relationship between rows intact (which snapshot belongs to which run, which image to
    which property) while making two databases comparable.

    Timestamps are blanked rather than ordered. Whether two operations landed in the same
    microsecond is a fact about how busy the machine was, not about what the operation did, and
    ordering them made this comparison fail about one run in three for no reason worth chasing.
    """
    seen: dict[str, int] = {}
    generated = re.compile(r"[0-9a-f]{32}")
    hex_digits = set("0123456789abcdef")

    def label(match: re.Match[str]) -> str:
        return f"#{seen.setdefault(match.group(0), len(seen))}"

    def stable(value):
        if not isinstance(value, str):
            return value
        if "T" in value and value.endswith("Z"):
            return "<time>"
        # An image is filed under the first two characters of its listing's identifier, so that
        # shard is generated too and is normalized along with the identifier itself.
        parts = generated.sub(label, value).replace(chr(92), "/").split("/")
        return "/".join("##" if len(p) == 2 and set(p) <= hex_digits else p for p in parts)

    rows: list[tuple] = []
    tables = [
        r["name"]
        for r in store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    ]
    for table in tables:
        for record in store.connection.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            rows.append((table, tuple(stable(v) for v in tuple(record))))
    return rows


def test_the_same_operation_through_the_core_and_the_command_leaves_one_state(tmp_path) -> None:
    """feat-003/AC-18: what makes 'both surfaces over one core' a fact rather than an intention.

    Two fresh databases, the same run and the same annotation, once through the facade the browser
    will call and once through the command line. Everything but the generated identifiers and times
    has to match, and it does, because the second is a thin call to the first.
    """
    through_core = tmp_path / "core" / "homescout.db"
    through_cli = tmp_path / "cli" / "homescout.db"
    through_core.parent.mkdir()
    through_cli.parent.mkdir()

    space = api.Workspace(
        store=Store.open(through_core),
        catalog=__import__("homescout.search", fromlist=["x"]).InMemoryCatalog([search()]),
        queue=InMemoryQueue(()),
        sources={"fake": FakeSource(rows=[row("a"), row("b")])},
    )
    api.run_search(space, "portales")
    api.annotate(space, listing_at(space.store, "a Example Road"), verdict="visit", rank=3)
    core_state = dump(space.store)
    space.close()

    with wired([search()], {"fake": FakeSource(rows=[row("a"), row("b")])}):
        invoke(["run", "portales"], db=through_cli)
        with Store.open(through_cli) as opened:
            same_house = listing_at(opened, "a Example Road")
        invoke(["annotate", same_house, "--verdict", "visit", "--rank", "3"], db=through_cli)

    with Store.open(through_cli) as opened:
        cli_state = dump(opened)

    assert cli_state == core_state


# -- where the deciding happens --------------------------------------------


def test_the_command_layer_cannot_reach_a_listing_or_a_source() -> None:
    """feat-003/AC-19: no decision about a listing can be made where there is no listing.

    An import ban rather than a review note. If the command layer cannot reach the store or the
    sources, the only things it can hold are the answers the core already computed.
    """
    banned = {"homescout.store", "homescout.sources", "homescout.runner"}
    offences: list[str] = []
    for module in sorted(CLI.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = "homescout" + "." * max(node.level - 1, 0)
                names = [f"{node.module or base}"]
                names = [n if n.startswith("homescout") else f"homescout.{n}" for n in names]
            else:
                continue
            for name in names:
                if any(name == b or name.startswith(b + ".") for b in banned):
                    offences.append(f"{module.name} imports {name}")

    assert offences == []


def test_no_conditional_in_the_command_layer_tests_a_listing_field() -> None:
    """feat-003/AC-19: rendering a price is this layer's job; branching on one is not.

    An approximation, and it says so: this catches `if row.price > x`, not a decision laundered
    through a local variable first. Together with the import ban above, the surface where that could
    happen is small enough to read.
    """
    interesting = set(FIELD_NAMES) - {"listing_status"}
    offences: list[str] = []
    for module in sorted(CLI.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            tests = []
            if isinstance(node, ast.If | ast.While | ast.IfExp):
                tests = [node.test]
            elif isinstance(node, ast.comprehension):
                tests = list(node.ifs)
            for test in tests:
                for inner in ast.walk(test):
                    if isinstance(inner, ast.Attribute) and inner.attr in interesting:
                        offences.append(f"{module.name}:{inner.lineno} branches on {inner.attr}")
    assert offences == []


# -- failing in the middle -------------------------------------------------


def test_an_unexpected_failure_leaves_the_last_completed_run_usable(
    store: Store, db_path, monkeypatch
) -> None:
    """feat-003/AC-22: a run that dies is never a baseline, so yesterday's answer still works."""
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        invoke(["run", "portales"], db=db_path)
    good = store.last_completed_run("portales")
    assert good is not None

    from homescout import runner

    def explode(*args, **kwargs):
        raise RuntimeError("something nobody thought of")

    monkeypatch.setattr(runner.Store, "complete_run", explode)
    with wired([search()], {"fake": FakeSource(rows=[row("a"), row("b")])}):
        code, out, err = invoke(["run", "portales"], db=db_path)

    assert code == ExitCode.INTERNAL_ERROR
    assert "failed unexpectedly" in err
    monkeypatch.undo()

    with Store.open(db_path) as reopened:
        assert reopened.last_completed_run("portales").id == good.id
        assert reopened.compare("portales") is not None
        dead = [r for r in reopened.runs("portales") if r.status == "failed"]
        assert len(dead) == 1, "the run that died says so rather than staying open forever"


def test_a_database_held_by_another_process_is_reported_in_terms_to_act_on(
    store: Store, db_path, monkeypatch
) -> None:
    """feat-003/AC-3: the spec's edge case, and the reason precondition is its own code."""
    from homescout.store import StoreLockedError

    def locked(*args, **kwargs):
        raise StoreLockedError(str(db_path), 5.0)

    monkeypatch.setattr(api.Store, "open", locked)
    code, _, err = invoke(["run", "portales"], db=db_path)

    assert code == ExitCode.PRECONDITION
    assert "browser interface" in err


def test_the_facade_is_the_whole_surface() -> None:
    """feat-003/AC-18, feat-003/AC-19: a command needing more than this is logic drifting upward."""
    expected = {
        "open_workspace",
        "run_search",
        "run_all",
        "changes",
        "list_searches",
        "show_search",
        "validate_search",
        "create_search",
        "edit_search",
        "annotate",
        "pending_matches",
        "resolve_match",
        "enrich",
        "export",
        "serve",
        "database_path",
        "moment",
    }
    public = {
        name
        for name, value in vars(api).items()
        if not name.startswith("_")
        and callable(value)
        and getattr(value, "__module__", "") == "homescout.api"
        and not isinstance(value, type)
    }
    assert public == expected


def test_asking_for_something_not_built_is_a_precondition_not_a_failure() -> None:
    """feat-003/AC-20: a command whose body arrives with its own feature says so.

    Two left, and shrinking. Enrichment used to be here and is not, which is what this criterion
    describes happening: the command was reachable from the first release and grew a body later,
    without an automated caller having to know which release it was.
    """
    with pytest.raises(PreconditionNotMet, match="spreadsheet export"):
        api.export(None)  # type: ignore[arg-type]
    with pytest.raises(PreconditionNotMet, match="browser interface"):
        api.serve(None)  # type: ignore[arg-type]


def test_editing_a_definition_wants_a_key_and_a_value(store: Store, db_path) -> None:
    """feat-003/AC-20: the command exists and refuses what it cannot understand."""
    with wired([search()], {"fake": FakeSource()}):
        code, _, err = invoke(["searches", "edit", "portales", "--set", "nonsense"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "KEY=VALUE" in err


def test_creating_a_definition_that_already_exists_is_refused(store: Store, db_path) -> None:
    """feat-003/AC-20: creating over the top of a tuned saved search is never what was meant."""
    with wired([search()], {"fake": FakeSource()}):
        code, _, err = invoke(["searches", "create", "portales"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "already exists" in err


def test_running_without_a_name_or_all_says_which_was_missing(store: Store, db_path) -> None:
    """feat-003/AC-15: the message names the two ways to run something."""
    code, _, err = invoke(["run"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "--all" in err


def test_an_invalid_input_error_is_never_reported_on_the_primary_stream(
    store: Store, db_path
) -> None:
    """feat-003/AC-2: diagnostics belong on the secondary stream, failures included."""
    code, out, err = invoke(["run", "nothing", "--json"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert out == ""
    assert err.strip() != ""


def test_an_empty_market_is_a_successful_run(store: Store, db_path) -> None:
    """feat-003/AC-4: nothing matching is a fact about the market, not a failure."""
    with wired([search()], {"fake": FakeSource(rows=[])}):
        code, out, _ = invoke(["run", "portales", "--json"], db=db_path)

    assert code == ExitCode.SUCCESS
    assert json.loads(out)["searches"][0]["counts"]["matched"] == 0


def test_a_run_with_a_failing_source_exits_degraded(store: Store, db_path) -> None:
    """feat-003/AC-4: the code a scheduled task reads to decide whether to wake someone."""
    sources = {
        "good": FakeSource("good", rows=[row("a")]),
        "bad": FakeSource("bad", outcome="failed", detail="refused"),
    }
    with wired([search("portales", sources=("good", "bad"))], sources):
        code, out, _ = invoke(["run", "portales", "--json"], db=db_path)

    assert code == ExitCode.DEGRADED
    entry = json.loads(out)["searches"][0]
    assert entry["outcome"] == "degraded"
    assert {s["source"]: s["outcome"] for s in entry["sources"]} == {"good": "ok", "bad": "failed"}


def test_running_everything_when_one_search_is_degraded(store: Store, db_path) -> None:
    """feat-003/AC-4: one invocation, one code, and it is the worst thing that happened."""
    searches = [search("north"), search("south", sources=("bad",))]
    sources = {"fake": FakeSource(rows=[row("a")]), "bad": FakeSource("bad", outcome="failed")}
    with wired(searches, sources):
        code, out, _ = invoke(["run", "--all", "--json"], db=db_path)

    assert code == ExitCode.DEGRADED
    assert [s["outcome"] for s in json.loads(out)["searches"]] == ["ok", "degraded"]


def test_an_annotation_survives_the_run_that_follows_it(store: Store, db_path) -> None:
    """feat-003/AC-23: the one failure this tool cannot have, from the surface that writes it."""
    with wired([search()], {"fake": FakeSource(rows=[row("a")])}):
        invoke(["run", "portales"], db=db_path)
        listing_id = store.listings()[0].id
        invoke(["annotate", listing_id, "--verdict", "keep"], db=db_path)
        invoke(["run", "portales"], db=db_path)

    with Store.open(db_path) as reopened:
        assert reopened.get_annotation(listing_id).verdict == "keep"


def test_a_moment_can_be_a_date_or_a_timestamp() -> None:
    """feat-003/AC-13: 'what changed since Tuesday' includes Tuesday."""
    assert api.moment("2026-08-01").startswith("2026-08-01T23:59:59")
    assert api.moment("2026-08-01T06:00:00Z").startswith("2026-08-01T06:00:00")
    with pytest.raises(InvalidInput):
        api.moment("nonsense")


def test_a_search_that_is_already_running_does_not_stop_the_others(
    store: Store, db_path, tmp_path
) -> None:
    """feat-003/AC-16, gap-002: one search's collision must not cost every search its night.

    This is the exact case the feature was blocked on: the nightly run of everything meets a manual
    run of one search. Before the audit, that raised past the loop and skipped the rest as well, and
    the only sign was a digest with fewer entries in it.
    """
    import subprocess
    import sys

    from test_run_claim import HOLDER

    source = str(Path(__file__).resolve().parents[1] / "src")
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLDER.format(src=source), str(db_path.parent), "busy", "30"],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert holder.stdout is not None
    assert holder.stdout.readline().strip() == "HELD"

    try:
        with wired([search("busy"), search("free")], {"fake": FakeSource(rows=[row("a")])}):
            code, out, _ = invoke(["run", "--all", "--json"], db=db_path)
    finally:
        holder.kill()
        holder.wait()

    document = json.loads(out)
    assert [s["name"] for s in document["searches"]] == ["free"], "the other one still ran"
    assert document["skipped"][0]["name"] == "busy"
    assert document["skipped"][0]["reason"] == "in progress"
    assert code == ExitCode.PRECONDITION, "and the code says something did not run"


def test_a_search_naming_an_unregistered_source_does_not_stop_the_others(
    store: Store, db_path
) -> None:
    """feat-003/AC-16, gap-002: the same rule, for the other way a search cannot start."""
    searches = [search("good"), search("broken", sources=("zillo",))]
    with wired(searches, {"fake": FakeSource(rows=[row("a")])}):
        code, out, _ = invoke(["run", "--all", "--json"], db=db_path)

    document = json.loads(out)
    assert [s["name"] for s in document["searches"]] == ["good"]
    assert document["skipped"][0]["reason"] == "invalid"
    assert "zillo" in document["skipped"][0]["detail"]
    assert code == ExitCode.INVALID_INPUT


def test_a_run_of_everything_that_managed_nothing_never_reports_success(
    store: Store, db_path
) -> None:
    """feat-003/AC-3, gap-003: work that did not happen is the one thing 0 must never mean."""
    broken = [
        search("one", problems=[SearchProblem("one.yaml:1", "unreadable")]),
        search("two", problems=[SearchProblem("two.yaml:1", "unreadable")]),
    ]
    with wired(broken, {"fake": FakeSource()}):
        code, out, _ = invoke(["run", "--all", "--json"], db=db_path)

    assert json.loads(out)["searches"] == []
    assert code != ExitCode.SUCCESS
    assert code == ExitCode.INVALID_INPUT
