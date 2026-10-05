"""Assessment concurrency, read through the existing local environment loader."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..errors import InvalidInput
from ..extract.settings import environment

CONCURRENCY = "HOMESCOUT_ASSESS_CONCURRENCY"
DEFAULT_CONCURRENCY = 8
MAX_CONCURRENCY = 32


class AssessmentMisconfigured(InvalidInput):
    pass


def validated(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_CONCURRENCY:
        raise AssessmentMisconfigured(
            f"{CONCURRENCY} must be an integer from 1 to {MAX_CONCURRENCY}."
        )
    return value


def concurrency(root: Path, environ: Mapping[str, str] | None = None) -> int:
    raw = (environment(root, environ).get(CONCURRENCY) or "").strip()
    if not raw:
        return DEFAULT_CONCURRENCY
    try:
        value = int(raw)
    except ValueError:
        raise AssessmentMisconfigured(
            f"{CONCURRENCY} must be an integer from 1 to {MAX_CONCURRENCY}."
        ) from None
    return validated(value)
