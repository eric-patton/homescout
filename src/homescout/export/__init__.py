"""Producing the sheet, which is the half of this tool that feeds the spreadsheet rather than
replacing it.

Months of somebody's judgment and the expectations of whoever else reads that document both live in
a particular column layout, so the default template reproduces it exactly and the output is
recognizable as the same file rather than as a new one.

Two rules the whole package is built around:

**It reads.** Nothing here writes to the store, and there is no path that reads a spreadsheet back.
The app is where edits are made; this is an output. Both halves are enforced by tests rather than
promised here.

**Empty means empty.** A value nobody determined is an empty cell with no placeholder, no default
and no zero. What the export does instead is say, afterwards, *which kind* of empty each blank
column was, because "run the enrichment pass", "write some notes" and "no free national source
supplies this" are three different answers to the same question.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..errors import InvalidInput
from ..store import Store
from . import columns as cols
from . import delimited, templates, workbook
from .rows import Row, rows_for
from .workbook import ExportFailed

__all__ = [
    "ExportFailed",
    "Written",
    "export_run",
    "cols",
    "templates",
]

FORMATS = ("xlsx", "csv")


@dataclass(frozen=True, slots=True)
class Written:
    """What an export produced, and what it could not fill."""

    path: Path
    format: str
    template: str
    properties: int
    columns: tuple[str, ...] = ()
    areas: int = 0
    #: Columns that came out entirely empty, grouped by why. See this package's own explanation.
    empty: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def reasons(self) -> list[str]:
        """The empty columns as sentences, most actionable first."""
        order = ("enriched", "annotation", "extracted", "unfilled")
        said: list[str] = []
        for origin in order:
            names = self.empty.get(origin)
            if not names:
                continue
            said.append(f"{cols.WHY_EMPTY[origin]}: {', '.join(names)}")
        return said


def _target(path: Path, *, format: str, force: bool) -> Path:
    """The file to write, or a refusal to replace one.

    AC-8's second branch, taken explicitly. The other reading, writing `sheet-2.xlsx` beside it,
    quietly accumulates files nobody asked for and leaves a person unsure which one is current.
    """
    if path.exists() and not force:
        raise InvalidInput(
            f"{path} already exists. Pass --force to replace it, or --to to write somewhere else. "
            "Nothing was written, and nothing in the database was touched."
        )
    return path


def export_run(
    store: Store,
    run_id: str,
    path: Path,
    *,
    root: Path | None = None,
    template: str | None = None,
    format: str = "xlsx",
    force: bool = False,
    include_dropped: bool = False,
) -> Written:
    """One run's results, as a file.

    Everything that could go wrong with the request goes wrong before anything is read: an unknown
    format, an unknown template, a template naming a column that does not exist, a file that already
    exists. Assembling five thousand rows and then refusing is not a kindness.
    """
    if format not in FORMATS:
        raise InvalidInput(
            f"{format!r} is not a format this writes. Available: {', '.join(FORMATS)}."
        )
    where = root if root is not None else path.parent
    chosen = templates.load(where, template)
    destination = _target(path, format=format, force=force)

    rows = rows_for(store, run_id, include_dropped=include_dropped, root=root)
    notes = store.area_notes()

    if format == "xlsx":
        workbook.save(workbook.build(chosen.columns, rows, area_notes=notes), destination)
    else:
        delimited.write(chosen.columns, rows, destination)

    return Written(
        path=destination,
        format=format,
        template=chosen.name,
        properties=len(rows),
        columns=chosen.headers,
        areas=len(notes),
        empty=workbook.empty_columns(chosen.columns, rows),
    )


def latest_run(store: Store, search: str) -> str:
    """The run a sheet is made from when nobody says which one."""
    runs = store.runs(search, only_completed=True)
    if not runs:
        raise InvalidInput(
            f"The saved search {search!r} has no completed run to export. Run it first."
        )
    return runs[-1].id


def default_path(root: Path, search: str, format: str) -> Path:
    """Where a sheet goes when nobody says.

    Its own directory, which is already kept out of version control, because an export is collected
    listing data and the constitution says that never goes in git.
    """
    return root / "exports" / f"{search}.{format}"


def rows_of(store: Store, run_id: str, **kwargs: Any) -> Sequence[Row]:
    """The rows a sheet would hold, for a caller that wants them without a file."""
    return rows_for(store, run_id, **kwargs)
