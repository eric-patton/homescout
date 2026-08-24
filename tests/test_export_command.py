"""The `export` command, end to end, as a terminal and a scheduled task get it."""

from __future__ import annotations

import json
from pathlib import Path

from cli_fakes import FakeSource, invoke, row, search, wired
from export_fakes import headers, template_file
from homescout.cli.codes import ExitCode
from homescout.store import Store

WELL = "The property has its own private well and a new septic system."


def a_run(db_path: Path, rows=None) -> None:
    with wired([search()], {"fake": FakeSource(rows=rows or [row("a", description=WELL)])}):
        code, _out, err = invoke(["run", "portales"], db=db_path)
    assert code == ExitCode.SUCCESS, err


def test_the_command_writes_a_workbook(store: Store, db_path: Path, tmp_path: Path) -> None:
    a_run(db_path)
    target = tmp_path / "portales.xlsx"

    code, out, err = invoke(
        ["export", "--search", "portales", "--to", str(target)], db=db_path
    )

    assert code == ExitCode.SUCCESS, err
    assert target.exists()
    assert "1 properties written" in out
    assert headers(target)[0] == "Rank"


def test_the_command_answers_a_machine_too(store: Store, db_path: Path, tmp_path: Path) -> None:
    """Product invariant 6: every command takes --json and returns a stable code."""
    a_run(db_path)
    target = tmp_path / "portales.xlsx"

    code, out, err = invoke(
        ["export", "--search", "portales", "--to", str(target), "--json"], db=db_path
    )

    assert code == ExitCode.SUCCESS, err
    document = json.loads(out)
    assert document["kind"] == "export"
    assert document["properties"] == 1
    assert document["template"] == "default"
    assert len(document["columns"]) == 32
    assert "Garage/Outbuildings" in document["empty_columns"]["unfilled"]


def test_the_command_refuses_to_replace_a_file(
    store: Store, db_path: Path, tmp_path: Path
) -> None:
    """feat-011/AC-8: re-exporting is safe because it says no, not because it is careful."""
    a_run(db_path)
    target = tmp_path / "portales.xlsx"
    invoke(["export", "--search", "portales", "--to", str(target)], db=db_path)

    code, _out, err = invoke(
        ["export", "--search", "portales", "--to", str(target)], db=db_path
    )

    assert code == ExitCode.INVALID_INPUT
    assert "--force" in err


def test_the_command_replaces_a_file_when_told_to(
    store: Store, db_path: Path, tmp_path: Path
) -> None:
    a_run(db_path)
    target = tmp_path / "portales.xlsx"
    invoke(["export", "--search", "portales", "--to", str(target)], db=db_path)

    code, _out, err = invoke(
        ["export", "--search", "portales", "--to", str(target), "--force"], db=db_path
    )
    assert code == ExitCode.SUCCESS, err


def test_the_command_writes_plain_text_too(
    store: Store, db_path: Path, tmp_path: Path
) -> None:
    a_run(db_path)
    target = tmp_path / "portales.csv"

    code, out, err = invoke(
        ["export", "--search", "portales", "--to", str(target), "--format", "csv"], db=db_path
    )

    assert code == ExitCode.SUCCESS, err
    assert target.read_text(encoding="utf-8-sig").startswith("Rank,Status,Property")


def test_the_command_uses_a_named_template(
    store: Store, db_path: Path, tmp_path: Path
) -> None:
    """feat-011/AC-7: a sheet for a different purpose, with no code changed."""
    a_run(db_path)
    # Beside the database, which is where the workspace keeps saved searches and `.env` too.
    template_file(db_path.parent, "land", ["Property", "Acres", "Water Source"])
    target = tmp_path / "land.xlsx"

    code, out, err = invoke(
        [
            "export",
            "--search",
            "portales",
            "--to",
            str(target),
            "--template",
            "land",
            "--json",
        ],
        db=db_path,
    )

    assert code == ExitCode.SUCCESS, err
    assert json.loads(out)["columns"] == ["Property", "Acres", "Water Source"]


def test_a_template_that_does_not_exist_is_invalid_input(
    store: Store, db_path: Path, tmp_path: Path
) -> None:
    a_run(db_path)
    code, _out, err = invoke(
        ["export", "--search", "portales", "--to", str(tmp_path / "x.xlsx"),
         "--template", "nope"],
        db=db_path,
    )

    assert code == ExitCode.INVALID_INPUT
    assert "nope" in err


def test_the_command_lists_the_templates_available(
    store: Store, db_path: Path, tmp_path: Path
) -> None:
    code, out, err = invoke(["export", "--templates"], db=db_path)
    assert code == ExitCode.SUCCESS, err
    assert "default" in out


def test_exporting_a_search_that_never_ran_says_so(store: Store, db_path: Path) -> None:
    """Rather than an empty workbook, which reads as a market with nothing in it."""
    with wired([search()], {"fake": FakeSource()}):
        code, _out, err = invoke(["export", "--search", "portales"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "no completed run" in err


def test_with_several_searches_the_command_asks_which(store: Store, db_path: Path) -> None:
    with wired([search("north"), search("south")], {"fake": FakeSource()}):
        code, _out, err = invoke(["export"], db=db_path)

    assert code == ExitCode.INVALID_INPUT
    assert "north" in err and "south" in err
