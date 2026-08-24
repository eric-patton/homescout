"""Getting everything out of a source that refuses to hand over everything.

Every listing site caps one query: Realtor.com at ten thousand, Zillow at roughly five hundred per
box, Redfin at three hundred and fifty. The cap is a fact to work around, not to ignore, because a
query that silently returns the first ten thousand of forty thousand looks exactly like a query that
returned everything.

The procedure is the same for all of them and lives here, once: ask for the first page, read the
count the source reports, and if it is over the cap, cut the query in half along whatever dimension
that source can be cut along and do the same to each half. Adding a source means supplying a
different way to cut, not a second copy of this.

Two things reach the truncation flag, and both return the rows already in hand: a piece that stays
over the cap when it can no longer be cut, and a source that starts refusing partway through.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..records import SourceRow
from .base import SearchQuery, Truncation
from .errors import SourceFailed

#: How many times a query may be halved. A century of listing dates cut twenty times is a span of
#: hours, so this is far past useful.
MAX_SPLIT_DEPTH = 20

#: The bound that actually matters. Depth alone does not limit anything, because the number of
#: branches doubles at every level: a depth of twenty permits a million requests. A source that
#: reports the same oversized count for every piece it is handed, which is exactly what a broken or
#: hostile source looks like, would descend until it had asked tens of thousands of times.
#:
#: So the walk carries a budget for the whole query. Two thousand requests at the three-second floor
#: is over an hour and a half, well past any legitimate run (a state-wide query of a hundred
#: thousand listings needs roughly eight hundred), which means this only ever trips on behavior that
#: is already wrong. Reaching it is an honest truncation, not a crash.
MAX_REQUESTS_PER_QUERY = 2_000


@dataclass(frozen=True, slots=True)
class Page:
    """One response: the rows in it, and how many the source says match overall."""

    rows: tuple[SourceRow, ...]
    total: int


#: Fetch one page of a query. The walk calls this and nothing else, so every request it causes goes
#: through whatever pacing the caller wrapped around it.
FetchPage = Callable[[SearchQuery, int], Page]

#: Cut a query in two. Returns None when the query can no longer be usefully divided, which is what
#: turns "too big" into an honest truncation instead of an infinite descent.
SplitQuery = Callable[[SearchQuery], tuple[SearchQuery, SearchQuery] | None]


@dataclass(frozen=True, slots=True)
class Harvest:
    rows: tuple[SourceRow, ...]
    truncation: Truncation | None
    request_count: int


def collect(
    query: SearchQuery,
    *,
    fetch_page: FetchPage,
    split: SplitQuery,
    ceiling: int | None,
    page_size: int,
    budget: int = MAX_REQUESTS_PER_QUERY,
) -> Harvest:
    """Everything the source will give for this query, split as far as needed.

    Returns what was retrieved even when it could not be made complete, with the reason attached.
    Never returns a partial result dressed as a whole one.
    """
    state = _Walk(
        fetch_page=fetch_page,
        split=split,
        ceiling=ceiling,
        page_size=page_size,
        budget=budget,
    )
    rows = state.walk(query, depth=0)
    if not rows and state.failure is not None:
        #: Nothing was retrieved at all, so this is not a partial answer, it is no answer. Reporting
        #: it as an empty-but-truncated success would let a total outage read as a market that has
        #: nothing in it, which is exactly the confusion the outcome vocabulary exists to prevent.
        raise state.failure
    return Harvest(
        rows=tuple(rows),
        truncation=state.truncation,
        request_count=state.requests,
    )


class _Walk:
    def __init__(
        self,
        *,
        fetch_page: FetchPage,
        split: SplitQuery,
        ceiling: int | None,
        page_size: int,
        budget: int,
    ) -> None:
        self._fetch_page = fetch_page
        self._split = split
        self._ceiling = ceiling
        self._page_size = max(1, page_size)
        self._budget = budget
        self._seen: set[str] = set()
        self.requests = 0
        self.truncation: Truncation | None = None
        self.failure: SourceFailed | None = None

    def walk(self, query: SearchQuery, *, depth: int) -> list[SourceRow]:
        if self.truncation is not None and self.truncation.ceiling is None:
            #: Already refused partway through, or out of budget. Pressing on would be asking a
            #: source that just said no to say no again.
            return []
        if self.requests >= self._budget:
            self._note_budget()
            return []

        try:
            first = self._page(query, 0)
        except SourceFailed as exc:
            return self._stop_here(exc)

        if self._over_ceiling(first.total):
            halves = self._split(query) if depth < MAX_SPLIT_DEPTH else None
            if halves is None:
                self._note_ceiling(first.total)
            else:
                collected: list[SourceRow] = []
                for half in halves:
                    collected.extend(self.walk(half, depth=depth + 1))
                return collected

        rows = self._fresh(first)
        wanted = min(first.total, self._ceiling) if self._over_ceiling(first.total) else first.total
        offset = self._page_size
        while offset < wanted and first.rows:
            if self.requests >= self._budget:
                self._note_budget()
                break
            try:
                page = self._page(query, offset)
            except SourceFailed as exc:
                self._stop_here(exc)
                break
            if not page.rows:
                break
            rows.extend(self._fresh(page))
            offset += self._page_size
        return rows

    def _page(self, query: SearchQuery, offset: int) -> Page:
        self.requests += 1
        return self._fetch_page(query, offset)

    def _fresh(self, page: Page) -> list[SourceRow]:
        """This page's rows, minus the ones an earlier page already gave us.

        The boundary is the page, and that is the whole point. A repeat *across* pages is our own
        doing: overlapping query pieces asking twice for the same property. A repeat *within* one
        page is the source contradicting itself, and both halves of a contradiction are evidence the
        store is required to keep. Collapsing the second kind would destroy a source row, which is
        exactly the bug the listing store's audit found last time, one layer down.
        """
        kept = [
            row
            for row in page.rows
            if row.source_listing_id is None or row.source_listing_id not in self._seen
        ]
        self._seen.update(
            row.source_listing_id for row in page.rows if row.source_listing_id is not None
        )
        return kept

    def _over_ceiling(self, total: int) -> bool:
        return self._ceiling is not None and total > self._ceiling

    def _note_budget(self) -> None:
        """Out of budget. Recorded with no ceiling, which is what stops the rest of the walk."""
        if self.truncation is None or self.truncation.ceiling is not None:
            self.truncation = Truncation(
                reason=(
                    f"the query needed more than {self._budget} requests to divide, which means "
                    "the source is not narrowing as its counts claim. What was retrieved is kept."
                )
            )

    def _note_ceiling(self, total: int) -> None:
        if self.truncation is None:
            self.truncation = Truncation(
                reason=(
                    f"{total} properties match, past the source's limit of {self._ceiling}, "
                    "and the query cannot be divided any further"
                ),
                ceiling=self._ceiling,
            )

    def _stop_here(self, exc: SourceFailed) -> list[SourceRow]:
        """A refusal mid-walk keeps what was already retrieved and stops asking."""
        self.failure = self.failure or exc
        self.truncation = Truncation(
            reason=(
                f"the source stopped answering partway through: {exc.reason}. "
                "What had already been retrieved is kept; the rest of the query was abandoned."
            )
        )
        return []
