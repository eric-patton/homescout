"""Export reads. It never writes to the store, and it never reads a spreadsheet back.

Two halves of one property, and both are checked rather than promised. The first is checked against
every table in the database rather than against a spot check of annotations, because the claim is
about everything. The second is checked against the package's own source, because the way an import
path appears is somebody adding one helpfully.
"""

from __future__ import annotations

import ast
import contextlib
from pathlib import Path

from export_fakes import fingerprint, listing, load, template_file, write
from homescout.rules.definition import Rule
from homescout.rules.parse import parse
from homescout.rules.verdicts import record
from homescout.store import Store

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "homescout" / "export"


def a_store_with_everything_in_it(store: Store):
    """A store carrying one of each thing the export touches, so nothing is untested by absence."""
    loaded = load(
        store,
        [
            listing("a", description="The property has a private well and septic."),
            listing("b", price=90_000),
        ],
    )
    store.set_annotation(loaded["a"], rank=1, verdict="worth a look", notes="old well")
    store.set_area_note("city", "Portales", "Good water.")
    record(
        store,
        [
            Rule(
                id="cheap",
                when="price < 100000",
                severity="flag",
                expression=parse("price < 100000"),
            )
        ],
        loaded.run_id,
    )
    return loaded


def test_exporting_changes_nothing_in_the_database(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-9: every table, before and after, compared."""
    loaded = a_store_with_everything_in_it(store)
    before = fingerprint(store)

    write(store, loaded, tmp_path / "sheet.xlsx", root=tmp_path)

    assert fingerprint(store) == before


def test_exporting_twice_and_in_both_formats_changes_nothing(
    store: Store, tmp_path: Path
) -> None:
    """feat-011/AC-9: including the paths a person actually takes, which is all of them."""
    loaded = a_store_with_everything_in_it(store)
    template_file(tmp_path, "small", ["Property", "Price"])
    before = fingerprint(store)

    write(store, loaded, tmp_path / "a.xlsx", root=tmp_path)
    write(store, loaded, tmp_path / "b.csv", root=tmp_path, format="csv")
    write(store, loaded, tmp_path / "c.xlsx", root=tmp_path, template="small")
    write(store, loaded, tmp_path / "d.xlsx", root=tmp_path, include_dropped=True)
    write(store, loaded, tmp_path / "a.xlsx", root=tmp_path, force=True)

    assert fingerprint(store) == before


def test_a_refused_export_changes_nothing_either(store: Store, tmp_path: Path) -> None:
    """feat-011/AC-9: a failure is not a licence to have half-written something."""
    loaded = a_store_with_everything_in_it(store)
    write(store, loaded, tmp_path / "sheet.xlsx", root=tmp_path)
    before = fingerprint(store)

    for attempt in (
        lambda: write(store, loaded, tmp_path / "sheet.xlsx", root=tmp_path),
        lambda: write(store, loaded, tmp_path / "s.xlsx", root=tmp_path, template="nope"),
        lambda: write(store, loaded, tmp_path / "s.ods", root=tmp_path, format="ods"),
    ):
        # Each of these is meant to fail. What is being asserted is the store, not the failure.
        with contextlib.suppress(Exception):
            attempt()

    assert fingerprint(store) == before


# ---------------------------------------------------------------------------
# No import path
# ---------------------------------------------------------------------------

#: Anything that would read a workbook back. `load_workbook` is the one a helpful person adds.
READERS = {
    "load_workbook",
    "read_excel",
    "reader",
    "DictReader",
}


def test_nothing_in_the_package_reads_a_spreadsheet() -> None:
    """feat-011/AC-11: the spreadsheet is an output, and there is no second source of truth.

    A source scan rather than a behavioural test, for the same reason the source adapters scan
    themselves for credentials: the way this rule breaks is somebody adding a convenient reader, and
    a behavioural test cannot notice a path nothing calls yet.
    """
    for module in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name not in READERS, f"{module.name} imports {alias.name}"
            if name in READERS:
                raise AssertionError(f"{module.name} refers to {name}, which reads a spreadsheet")


def test_the_package_opens_no_file_for_reading() -> None:
    """The other way an import path arrives: `open(path)` and a parser written by hand."""
    for module in sorted(PACKAGE.glob("*.py")):
        text = module.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            builtin = isinstance(called, ast.Name) and called.id == "open"
            method = isinstance(called, ast.Attribute) and called.attr == "open"
            if not (builtin or method):
                continue
            # `open(path, mode)` puts the mode second; `path.open(mode)` puts it first.
            positional = node.args[1:] if builtin else node.args
            modes = [
                arg.value
                for arg in positional
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            ] + [
                kw.value.value
                for kw in node.keywords
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant)
            ]
            assert modes, f"{module.name} opens a file without saying how"
            assert all("w" in mode or "a" in mode for mode in modes), (
                f"{module.name} opens a file for reading, in a package that only writes"
            )
