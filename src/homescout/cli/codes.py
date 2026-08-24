"""The five exit codes, and nothing else.

These are a contract. A scheduled task decides whether to wake a human from the number alone, so
the meanings are fixed here, in one place, and no command body ever chooses one.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import IntEnum

from ..errors import InvalidInput, PreconditionNotMet


class ExitCode(IntEnum):
    SUCCESS = 0
    #: Completed, with at least one source failed or unavailable.
    DEGRADED = 1
    #: Usage, an unknown name, or a saved search that fails validation. Two because that is what
    #: `argparse` already exits with on a usage error, so a bad flag and a bad name are one class.
    INVALID_INPUT = 2
    #: Valid, but cannot proceed yet.
    PRECONDITION = 3
    INTERNAL_ERROR = 4


#: Worst first. One invocation can produce several (running every saved search does), and this is
#: the order they settle in. Invalid input beats degraded deliberately: a source that failed is
#: weather, a definition that does not parse is a file a human has to edit. Precondition beats
#: degraded for the same reason at one remove: a search that did not run at all is worse news than
#: one that ran with a source down.
PRECEDENCE: tuple[ExitCode, ...] = (
    ExitCode.INTERNAL_ERROR,
    ExitCode.INVALID_INPUT,
    ExitCode.PRECONDITION,
    ExitCode.DEGRADED,
    ExitCode.SUCCESS,
)

# Every code has a place in the order. Without this, a code left out of the list falls through
# `worst_of` to success, which is how a run of every saved search that managed none of them once
# reported that everything was fine.
assert set(PRECEDENCE) == set(ExitCode), "every exit code needs a place in the precedence order"


def code_for(error: BaseException) -> ExitCode:
    """The code for an error the core raised on purpose.

    Only the two deliberate kinds are named here. The store's own errors are translated by the
    facade before they reach this layer, which is what lets this module import nothing but the
    error definitions.
    """
    if isinstance(error, InvalidInput):
        return ExitCode.INVALID_INPUT
    if isinstance(error, PreconditionNotMet):
        return ExitCode.PRECONDITION
    return ExitCode.INTERNAL_ERROR


def worst_of(codes: Iterable[ExitCode]) -> ExitCode:
    codes = list(codes)
    if not codes:
        return ExitCode.SUCCESS
    for candidate in PRECEDENCE:
        if candidate in codes:
            return candidate
    return ExitCode.SUCCESS
