"""The same rows, as plain text.

The properties sheet and nothing else: no link formatting, no second sheet, no column widths. What
it does carry that a naive writer would not is a byte-order mark, because a spreadsheet application
on Windows reads a comma-separated file as the system code page unless one is there, and every
accent, em dash and degree sign in a listing description comes out wrong.

The other difference from the workbook is the one recorded in `text.for_delimited`: a text file has
no cell types, so a value that a spreadsheet would evaluate is written with a leading apostrophe
instead. That is the only place the two formats hold different bytes.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Sequence
from pathlib import Path

from .columns import Column
from .rows import Row
from .text import for_delimited
from .workbook import ExportFailed, _discard

#: UTF-8 with a byte-order mark. Without it, Excel on Windows reads the file as cp1252 and every
#: non-ASCII character in a description is wrong, which is AC-13 failing quietly on the format where
#: it is easiest to miss.
ENCODING = "utf-8-sig"


def write(columns: Sequence[Column], rows: Sequence[Row], path: Path) -> None:
    """The properties sheet, comma separated, written atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging = path.with_name(path.name + ".partial")
    try:
        # `newline=""` because the csv module writes its own line endings, and letting Python
        # translate them as well produces a blank line between every row on Windows.
        with staging.open("w", encoding=ENCODING, newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([column.name for column in columns])
            for row in rows:
                writer.writerow([for_delimited(column.value(row)) for column in columns])
        os.replace(staging, path)
    except PermissionError:
        _discard(staging)
        raise ExportFailed(
            f"{path} could not be written because something else has it open. "
            "Close it and run this again."
        ) from None
    except OSError as exc:
        _discard(staging)
        raise ExportFailed(f"{path} could not be written: {exc}") from None
