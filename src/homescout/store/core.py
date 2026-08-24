"""The store's public surface.

Everything the rest of HomeScout does to recorded history goes through this class. The rules it
keeps are not conveniences:

* A recorded observation is never edited. Corrections are new rows.
* A listing is only marked gone on positive evidence. Absence while a source failed means nothing.
* Freshness is computed from this tool's own first observation, never from a source's own field.
* A run never touches an annotation.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from ..records import ListingFields, SourceRow
from . import diff as _diff
from .db import (
    DEFAULT_TIMEOUT_SECONDS,
    connect,
    schema_version,
    transaction,
    translating_errors,
    utc_now,
)
from .errors import NoBaselineError, RunNotCompletedError, UnknownListingError
from .migrations import migrate
from .models import (
    Annotation,
    AreaNote,
    CachedValue,
    Comparison,
    ListingEvent,
    ListingHistory,
    ListingRecord,
    PriceHistoryEntry,
    RuleVerdict,
    RunRecord,
    Snapshot,
    SourceLink,
    SourceOutcome,
    StoredImage,
)
from .schema import SNAPSHOT_FIELDS

_SNAPSHOT_COLUMNS = ", ".join(SNAPSHOT_FIELDS)
_SNAPSHOT_PLACEHOLDERS = ", ".join(f":{name}" for name in SNAPSHOT_FIELDS)


def _new_id() -> str:
    return uuid.uuid4().hex


class Store:
    """A HomeScout database.

    Open it with :meth:`open`, which creates the file if it is absent and brings an older one
    forward. A file written by a newer build is refused by name rather than opened hopefully.
    """

    def __init__(self, conn: sqlite3.Connection, path: Path, timeout: float) -> None:
        self._conn = conn
        self._path = path
        self._timeout = timeout

    # -- lifecycle ---------------------------------------------------------

    @classmethod
    def open(
        cls, path: str | Path, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
    ) -> Store:
        path = Path(path)
        with translating_errors(path, timeout):
            conn = connect(path, timeout=timeout)
            migrate(conn)
        return cls(conn, path, timeout)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def schema_version(self) -> int:
        return schema_version(self._conn)

    @property
    def images_dir(self) -> Path:
        """Where preview images live: beside the database, never inside it."""
        return self._path.parent / "photos"

    @property
    def connection(self) -> sqlite3.Connection:
        """The underlying connection.

        Exposed so that tests can prove the append-only guarantees hold even for a caller who
        bypasses this class entirely, which is the only way to prove they are real.
        """
        return self._conn

    # -- runs --------------------------------------------------------------

    def start_run(self, search_name: str) -> RunRecord:
        run_id = _new_id()
        started_at = utc_now()
        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            cursor = conn.execute(
                "INSERT INTO runs (id, search_name, started_at, finished_at, status) "
                "VALUES (?, ?, ?, NULL, 'running')",
                (run_id, search_name, started_at),
            )
            seq = int(cursor.lastrowid)
        return RunRecord(
            seq=seq,
            id=run_id,
            search_name=search_name,
            started_at=started_at,
            finished_at=None,
            status="running",
        )

    def record_source_outcome(self, run_id: str, outcome: SourceOutcome) -> None:
        """Record what one source contributed. Written once, when that source finishes."""
        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            conn.execute(
                "INSERT INTO run_sources "
                "(run_id, source, outcome, row_count, truncated, detail, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    outcome.source,
                    outcome.outcome,
                    outcome.row_count,
                    int(outcome.truncated),
                    outcome.detail,
                    utc_now(),
                ),
            )

    def record_observations(
        self, run_id: str, source: str, rows: Sequence[SourceRow]
    ) -> list[str]:
        """Write what one source returned, and snapshot the listings it covered.

        Written incrementally, as each source returns, rather than held until the run ends. A long
        run that dies part-way has then not thrown away the network work it already did, which
        matters when every request is deliberately slow. The run only becomes a comparison baseline
        when it is completed.

        Every row a source returned is recorded, including a repeat of an identifier the same
        response already carried. Two rows under one identifier is a source contradicting itself,
        and both halves of that contradiction are evidence: discarding either would be destroying a
        source row. What collapses is the property, not the row, so the repeat joins the same
        canonical listing and the run still holds one snapshot of it.

        Returns one canonical listing id per input row, in input order, so a caller can pair a row
        it still holds with the property that row became. Two rows that collapsed onto one property
        therefore yield that property's id twice, and the distinct set is `dict.fromkeys` away.
        Returning the collapsed list instead would leave a caller with no sound way to do the
        pairing short of reimplementing the identity rule above, which is the one rule this project
        cannot afford to have two of.
        """
        observed_at = utc_now()
        listing_ids: list[str] = []

        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            for row in rows:
                raw_id = _new_id()
                values = row.fields.as_row()
                conn.execute(
                    f"INSERT INTO raw_listings "
                    f"(id, run_id, source, source_listing_id, fetched_at, payload, "
                    f"{_SNAPSHOT_COLUMNS}) "
                    f"VALUES (:id, :run_id, :source, :source_listing_id, :fetched_at, :payload, "
                    f"{_SNAPSHOT_PLACEHOLDERS})",
                    {
                        "id": raw_id,
                        "run_id": run_id,
                        "source": source,
                        "source_listing_id": row.source_listing_id,
                        "fetched_at": row.fetched_at or observed_at,
                        "payload": row.payload_text(),
                        **values,
                    },
                )

                listing_id, is_new = self._resolve_listing(conn, source, row, run_id, observed_at)
                listing_ids.append(listing_id)

                conn.execute(
                    "INSERT OR IGNORE INTO listing_sources "
                    "(listing_id, raw_listing_id, join_signal, decided_by, linked_at) "
                    "VALUES (?, ?, ?, 'automatic', ?)",
                    (listing_id, raw_id, "single-source", observed_at),
                )

                # One snapshot per listing per run. If two source rows resolved to the same
                # listing in this run, the first one recorded stands and both raw rows are kept.
                conn.execute(
                    f"INSERT OR IGNORE INTO listing_snapshots "
                    f"(run_id, listing_id, observed_at, {_SNAPSHOT_COLUMNS}) "
                    f"VALUES (:run_id, :listing_id, :observed_at, {_SNAPSHOT_PLACEHOLDERS})",
                    {
                        "run_id": run_id,
                        "listing_id": listing_id,
                        "observed_at": observed_at,
                        **values,
                    },
                )

                if is_new:
                    self._add_event(conn, listing_id, run_id, observed_at, "first_seen", None)

        return listing_ids

    def complete_run(self, run_id: str) -> RunRecord:
        """Close a run and settle what it means.

        This is where presence moves: a listing this run did not see becomes `disappeared`, but
        only if every configured source succeeded. If any source failed, absence is not evidence
        and nothing changes.
        """
        run = self.get_run(run_id)
        finished_at = utc_now()
        all_ok = run.all_sources_succeeded

        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            observed_here = {
                r["listing_id"]
                for r in conn.execute(
                    "SELECT listing_id FROM listing_snapshots WHERE run_id = ?", (run_id,)
                )
            }
            # Everything this search has seen before, addressed by whichever listing currently
            # represents it. A listing that was merged into another is followed to the merged one,
            # so a property does not read as two half-observed records after a merge.
            known: dict[str, str] = {}
            for r in conn.execute(
                "SELECT DISTINCT sn.listing_id FROM listing_snapshots sn "
                "JOIN runs r ON r.id = sn.run_id "
                "WHERE r.search_name = ? AND r.status = 'completed'",
                (run.search_name,),
            ):
                live = self._live_listing_id(conn, r["listing_id"])
                if live in known:
                    continue
                record = conn.execute(
                    "SELECT presence, retracted FROM listings WHERE id = ?", (live,)
                ).fetchone()
                if record is not None and not record["retracted"]:
                    known[live] = record["presence"]

            for listing_id in observed_here:
                if known.get(listing_id) == "disappeared":
                    conn.execute(
                        "UPDATE listings SET presence = 'observed' WHERE id = ?", (listing_id,)
                    )
                    self._add_event(conn, listing_id, run_id, finished_at, "returned", None)

            if all_ok:
                for listing_id, presence in known.items():
                    if listing_id in observed_here or presence != "observed":
                        continue
                    conn.execute(
                        "UPDATE listings SET presence = 'disappeared' WHERE id = ?", (listing_id,)
                    )
                    self._add_event(conn, listing_id, run_id, finished_at, "disappeared", None)

            self._record_movements(conn, run, observed_here, finished_at)

            conn.execute(
                "UPDATE runs SET status = 'completed', finished_at = ? WHERE id = ?",
                (finished_at, run_id),
            )

        return self.get_run(run_id)

    def fail_run(self, run_id: str) -> RunRecord:
        """Mark a run as failed. It is never used as a comparison baseline."""
        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            conn.execute(
                "UPDATE runs SET status = 'failed', finished_at = ? WHERE id = ?",
                (utc_now(), run_id),
            )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> RunRecord:
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"No run with id {run_id!r}")
        return self._run_from(row)

    def runs(
        self, search_name: str | None = None, *, only_completed: bool = False
    ) -> list[RunRecord]:
        sql = "SELECT * FROM runs"
        clauses, params = [], []
        if search_name is not None:
            clauses.append("search_name = ?")
            params.append(search_name)
        if only_completed:
            clauses.append("status = 'completed'")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY seq"
        return [self._run_from(r) for r in self._conn.execute(sql, params)]

    def last_completed_run(
        self, search_name: str, *, before_seq: int | None = None, since: str | None = None
    ) -> RunRecord | None:
        """The most recent completed run, optionally bounded.

        `before_seq` bounds by insertion order, which is what "the run before this one" means.
        `since` bounds by wall-clock time, which is what a user asking "what changed since Tuesday"
        means. They answer different questions and both are needed.
        """
        sql = "SELECT * FROM runs WHERE search_name = ? AND status = 'completed'"
        params: list[Any] = [search_name]
        if before_seq is not None:
            sql += " AND seq < ?"
            params.append(before_seq)
        if since is not None:
            sql += " AND started_at <= ?"
            params.append(since)
        sql += " ORDER BY seq DESC LIMIT 1"
        row = self._conn.execute(sql, params).fetchone()
        return self._run_from(row) if row else None

    # -- comparison --------------------------------------------------------

    def compare(
        self,
        search_name: str,
        *,
        target_run_id: str | None = None,
        baseline_run_id: str | None = None,
        since: str | None = None,
    ) -> Comparison:
        """What changed between two points in time.

        With neither a baseline nor a `since`, the comparison is against the previous completed run
        of the same search. With no previous run at all, everything observed is new, which is what
        a first-ever run means. An explicit `since` that names a moment with no completed run before
        it is an error rather than an implicit "everything is new".
        """
        target = (
            self.get_run(target_run_id)
            if target_run_id
            else self.last_completed_run(search_name)
        )
        if target is None:
            raise NoBaselineError(search_name)
        if target.status != "completed":
            raise RunNotCompletedError(
                f"Run {target.id} is {target.status}, so it cannot be compared. "
                f"An unfinished run is never used as either side of a comparison."
            )

        if baseline_run_id is not None:
            baseline = self.get_run(baseline_run_id)
            if baseline.status != "completed":
                raise RunNotCompletedError(
                    f"Run {baseline.id} is {baseline.status}, so it cannot be a baseline."
                )
        elif since is not None:
            baseline = self.last_completed_run(
                search_name, before_seq=target.seq, since=since
            )
            if baseline is None:
                raise NoBaselineError(search_name, before=since)
        else:
            baseline = self.last_completed_run(search_name, before_seq=target.seq)

        return _diff.compare_runs(
            self._conn, search_name=search_name, target=target, baseline=baseline
        )

    # -- listings ----------------------------------------------------------

    def get_listing(self, listing_id: str) -> ListingRecord:
        row = self._conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if row is None:
            raise UnknownListingError(f"No listing with id {listing_id!r}")
        return self._listing_from(row)

    def listings(self, *, include_disappeared: bool = True) -> list[ListingRecord]:
        """Every live canonical listing.

        Disappeared listings are included by default. They are not deleted and not hidden here: a
        listing that vanishes and comes back is signal, and the caller decides whether to show it.
        """
        sql = "SELECT * FROM listings WHERE retracted = 0 AND superseded_by IS NULL"
        if not include_disappeared:
            sql += " AND presence = 'observed'"
        sql += " ORDER BY first_observed_at, id"
        return [self._listing_from(r) for r in self._conn.execute(sql)]

    def source_links(self, listing_id: str) -> list[SourceLink]:
        """The source rows underneath a canonical listing, and what justified each join."""
        rows = self._conn.execute(
            "SELECT ls.raw_listing_id, ls.join_signal, ls.decided_by, ls.linked_at, "
            "       rl.source, rl.source_listing_id, rl.fetched_at "
            "FROM listing_sources ls "
            "JOIN raw_listings rl ON rl.id = ls.raw_listing_id "
            "WHERE ls.listing_id = ? ORDER BY rl.fetched_at, ls.raw_listing_id",
            (listing_id,),
        ).fetchall()
        return [
            SourceLink(
                raw_listing_id=r["raw_listing_id"],
                source=r["source"],
                source_listing_id=r["source_listing_id"],
                fetched_at=r["fetched_at"],
                join_signal=r["join_signal"],
                decided_by=r["decided_by"],
                linked_at=r["linked_at"],
            )
            for r in rows
        ]

    def snapshot_at(self, listing_id: str, run_id: str) -> Snapshot | None:
        row = self._conn.execute(
            f"SELECT run_id, listing_id, observed_at, {_SNAPSHOT_COLUMNS} "
            f"FROM listing_snapshots WHERE listing_id = ? AND run_id = ?",
            (listing_id, run_id),
        ).fetchone()
        return self._snapshot_from(row) if row else None

    def snapshots_for_run(self, run_id: str) -> list[Snapshot]:
        rows = self._conn.execute(
            f"SELECT run_id, listing_id, observed_at, {_SNAPSHOT_COLUMNS} "
            f"FROM listing_snapshots WHERE run_id = ? ORDER BY listing_id",
            (run_id,),
        ).fetchall()
        return [self._snapshot_from(r) for r in rows]

    # -- cached public data about places -------------------------------------

    def cache_values(self, provider: str, cache_key: str, values: Mapping[str, Any]) -> None:
        """Remember what one provider said about one place.

        The one table in this database that is written twice. A cached copy of a federal map is not
        an observation this tool made, so the append-only rule does not reach it; the rule that does
        is that a failure never gets here at all, so a failure cannot overwrite a good answer with
        nothing.
        """
        if not values:
            return
        now = utc_now()
        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            conn.executemany(
                "INSERT INTO enrichment_values (provider, cache_key, name, value, fetched_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (provider, cache_key, name) DO UPDATE SET "
                "value = excluded.value, fetched_at = excluded.fetched_at",
                [
                    (provider, cache_key, name, json.dumps(value), now)
                    for name, value in values.items()
                ],
            )

    def cached_values(
        self, provider: str, cache_keys: Sequence[str]
    ) -> dict[str, dict[str, CachedValue]]:
        """Everything cached for these places, in one query.

        In bulk because the alternative is a round trip per property per provider, and a pass over
        five thousand fully cached properties has a five-second budget for the whole thing.
        """
        if not cache_keys:
            return {}
        found: dict[str, dict[str, CachedValue]] = {}
        keys = list(dict.fromkeys(cache_keys))
        for start in range(0, len(keys), 500):
            batch = keys[start : start + 500]
            placeholders = ", ".join("?" * len(batch))
            rows = self._conn.execute(
                "SELECT cache_key, name, value, fetched_at FROM enrichment_values "
                f"WHERE provider = ? AND cache_key IN ({placeholders})",
                (provider, *batch),
            )
            for row in rows:
                found.setdefault(row["cache_key"], {})[row["name"]] = CachedValue(
                    value=json.loads(row["value"]) if row["value"] is not None else None,
                    fetched_at=row["fetched_at"],
                )
        return found

    # -- rule verdicts ------------------------------------------------------

    def record_verdicts(self, run_id: str, verdicts: Sequence[RuleVerdict]) -> None:
        """What every criterion decided about every property this run saw.

        Written once, after the run has completed, in one transaction. Nothing here can be written
        twice for the same run, property and rule: the table's own key says so, and a second attempt
        is a bug rather than a correction.
        """
        if not verdicts:
            return
        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            conn.executemany(
                "INSERT INTO rule_verdicts "
                "(run_id, listing_id, rule_id, severity, verdict, missing) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        run_id,
                        v.listing_id,
                        v.rule_id,
                        v.severity,
                        v.verdict,
                        ",".join(v.missing) or None,
                    )
                    for v in verdicts
                ],
            )

    def verdicts(self, run_id: str, *, listing_id: str | None = None) -> list[RuleVerdict]:
        """Every verdict a run recorded, in a stable order."""
        sql = "SELECT * FROM rule_verdicts WHERE run_id = ?"
        params: list[object] = [run_id]
        if listing_id is not None:
            sql += " AND listing_id = ?"
            params.append(listing_id)
        sql += " ORDER BY listing_id, rule_id"
        return [
            RuleVerdict(
                run_id=r["run_id"],
                listing_id=r["listing_id"],
                rule_id=r["rule_id"],
                severity=r["severity"],
                verdict=r["verdict"],
                missing=tuple(r["missing"].split(",")) if r["missing"] else (),
            )
            for r in self._conn.execute(sql, params)
        ]

    def fired(
        self, run_id: str, rule_id: str | None = None, *, severities: Sequence[str] | None = None
    ) -> dict[str, set[str]]:
        """Which properties fired which rules in one run, as rule to listing identifiers."""
        sql = "SELECT rule_id, listing_id FROM rule_verdicts WHERE run_id = ? AND verdict = 'fired'"
        params: list[object] = [run_id]
        if rule_id is not None:
            sql += " AND rule_id = ?"
            params.append(rule_id)
        if severities is not None:
            sql += f" AND severity IN ({', '.join('?' * len(severities))})"
            params.extend(severities)
        found: dict[str, set[str]] = {}
        for row in self._conn.execute(sql, params):
            found.setdefault(row["rule_id"], set()).add(row["listing_id"])
        return found

    def events(self, listing_id: str) -> list[ListingEvent]:
        rows = self._conn.execute(
            "SELECT * FROM listing_events WHERE listing_id = ? ORDER BY occurred_at, id",
            (listing_id,),
        ).fetchall()
        return [
            ListingEvent(
                id=r["id"],
                listing_id=r["listing_id"],
                run_id=r["run_id"],
                occurred_at=r["occurred_at"],
                kind=r["kind"],
                detail=json.loads(r["detail"]) if r["detail"] else None,
            )
            for r in rows
        ]

    def history(self, listing_id: str, *, as_of: str | None = None) -> ListingHistory:
        """How this listing has moved, according to us.

        Days on market counts from our own first observation. A source reporting four hundred days
        about a listing we first saw last month is telling us about its records, not ours, and its
        value never substitutes for this one.
        """
        listing = self.get_listing(listing_id)
        prices = [
            PriceHistoryEntry(
                observed_at=r["observed_at"], run_id=r["run_id"], price=r["price"]
            )
            for r in self._conn.execute(
                "SELECT observed_at, run_id, price FROM listing_snapshots "
                "WHERE listing_id = ? ORDER BY observed_at, id",
                (listing_id,),
            )
        ]
        reference = datetime.now(UTC) if as_of is None else _parse_utc(as_of)
        first_seen = _parse_utc(listing.first_observed_at)
        return ListingHistory(
            listing_id=listing_id,
            first_observed_at=listing.first_observed_at,
            days_on_market=max(0, (reference - first_seen).days),
            presence=listing.presence,
            prices=tuple(prices),
            events=tuple(self.events(listing_id)),
        )

    # -- merge mechanics (used by the address matching feature) ------------

    def supersede(
        self,
        listing_ids: Sequence[str],
        *,
        join_signal: str,
        decided_by: Literal["automatic", "human"] = "human",
    ) -> str:
        """Merge listings by writing a new one, never by rewriting the old ones.

        The constituents stay exactly as they were and point at the new listing. Nothing is
        deleted, and crucially no annotation moves: this is why a user's judgment survives a merge
        and its undo, by construction rather than by careful bookkeeping.
        """
        if len(listing_ids) < 2:
            raise ValueError("A merge needs at least two listings.")
        constituents = [self.get_listing(i) for i in listing_ids]
        merged_id = _new_id()
        at = utc_now()
        earliest = min(constituents, key=lambda listing: listing.first_observed_at)
        presence = (
            "observed" if any(c.presence == "observed" for c in constituents) else "disappeared"
        )

        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            conn.execute(
                "INSERT INTO listings "
                "(id, first_observed_at, created_in_run, presence, superseded_by, retracted) "
                "VALUES (?, ?, ?, ?, NULL, 0)",
                (merged_id, earliest.first_observed_at, earliest.created_in_run, presence),
            )
            for constituent in constituents:
                conn.execute(
                    "INSERT OR IGNORE INTO listing_sources "
                    "(listing_id, raw_listing_id, join_signal, decided_by, linked_at) "
                    "SELECT ?, raw_listing_id, ?, ?, ? FROM listing_sources WHERE listing_id = ?",
                    (merged_id, join_signal, decided_by, at, constituent.id),
                )
                conn.execute(
                    "UPDATE listings SET superseded_by = ? WHERE id = ?",
                    (merged_id, constituent.id),
                )
                self._add_event(
                    conn, constituent.id, None, at, "merged", {"into": merged_id}
                )
            self._add_event(
                conn, merged_id, None, at, "merged", {"from": [c.id for c in constituents]}
            )
        return merged_id

    def undo_merge(self, merged_listing_id: str) -> list[str]:
        """Put back what a merge joined. Nothing was destroyed, so nothing has to be recovered."""
        at = utc_now()
        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            constituents = [
                r["id"]
                for r in conn.execute(
                    "SELECT id FROM listings WHERE superseded_by = ? "
                    "ORDER BY first_observed_at, id",
                    (merged_listing_id,),
                )
            ]
            if not constituents:
                raise UnknownListingError(
                    f"Listing {merged_listing_id!r} is not a merge of anything."
                )
            for listing_id in constituents:
                conn.execute(
                    "UPDATE listings SET superseded_by = NULL WHERE id = ?", (listing_id,)
                )
                self._add_event(
                    conn, listing_id, None, at, "unmerged", {"from": merged_listing_id}
                )
            conn.execute("UPDATE listings SET retracted = 1 WHERE id = ?", (merged_listing_id,))
            self._add_event(
                conn, merged_listing_id, None, at, "unmerged", {"into": constituents}
            )
        return constituents

    # -- the user's own data -----------------------------------------------

    def get_annotation(self, listing_id: str) -> Annotation | None:
        row = self._conn.execute(
            "SELECT * FROM annotations WHERE listing_id = ?", (listing_id,)
        ).fetchone()
        if row is None:
            return None
        return Annotation(
            listing_id=row["listing_id"],
            rank=row["rank"],
            verdict=row["verdict"],
            red_flags=row["red_flags"],
            summary=row["summary"],
            next_step=row["next_step"],
            notes=row["notes"],
            updated_at=row["updated_at"],
        )

    def set_annotation(self, listing_id: str, **values: Any) -> Annotation:
        """Write the user's judgment. Only an explicit action like this one ever changes it.

        Last write wins, with a timestamp. Fields not named are left alone.
        """
        unknown = set(values) - set(Annotation.ANNOTATION_FIELDS)
        if unknown:
            raise ValueError(
                f"Not annotation fields: {sorted(unknown)}. "
                f"Known fields: {list(Annotation.ANNOTATION_FIELDS)}."
            )
        self.get_listing(listing_id)  # raises if it does not exist
        existing = self.get_annotation(listing_id)
        merged = existing.content() if existing else dict.fromkeys(Annotation.ANNOTATION_FIELDS)
        merged.update(values)
        now = utc_now()
        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            conn.execute(
                "INSERT INTO annotations "
                "(listing_id, rank, verdict, red_flags, summary, next_step, notes, updated_at) "
                "VALUES (:listing_id, :rank, :verdict, :red_flags, :summary, :next_step, "
                ":notes, :updated_at) "
                "ON CONFLICT (listing_id) DO UPDATE SET "
                "rank = excluded.rank, verdict = excluded.verdict, "
                "red_flags = excluded.red_flags, summary = excluded.summary, "
                "next_step = excluded.next_step, notes = excluded.notes, "
                "updated_at = excluded.updated_at",
                {"listing_id": listing_id, "updated_at": now, **merged},
            )
        annotation = self.get_annotation(listing_id)
        assert annotation is not None
        return annotation

    def annotations_for(self, listing_id: str) -> list[Annotation]:
        """Every annotation attached to this listing or to anything merged into it.

        A merged listing presents its constituents' annotations rather than absorbing them, because
        absorbing would mean moving them, and moving is how they get lost.
        """
        ids = [listing_id] + [
            r["id"]
            for r in self._conn.execute(
                "SELECT id FROM listings WHERE superseded_by = ?", (listing_id,)
            )
        ]
        found = [self.get_annotation(i) for i in ids]
        return [a for a in found if a is not None]

    def set_area_note(self, area_type: str, area_value: str, notes: str | None) -> AreaNote:
        """An observation about a place rather than about a property. Never touched by a run."""
        now = utc_now()
        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            conn.execute(
                "INSERT INTO area_notes (id, area_type, area_value, notes, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (area_type, area_value) DO UPDATE SET "
                "notes = excluded.notes, updated_at = excluded.updated_at",
                (_new_id(), area_type, area_value, notes, now),
            )
        note = self.get_area_note(area_type, area_value)
        assert note is not None
        return note

    def get_area_note(self, area_type: str, area_value: str) -> AreaNote | None:
        row = self._conn.execute(
            "SELECT * FROM area_notes WHERE area_type = ? AND area_value = ?",
            (area_type, area_value),
        ).fetchone()
        return self._area_note_from(row) if row else None

    def area_notes(self) -> list[AreaNote]:
        rows = self._conn.execute(
            "SELECT * FROM area_notes ORDER BY area_type, area_value"
        ).fetchall()
        return [self._area_note_from(r) for r in rows]

    # -- stored preview images ---------------------------------------------

    def store_preview_image(
        self,
        listing_id: str,
        data: bytes,
        *,
        extension: str = "jpg",
        source_url: str | None = None,
    ) -> StoredImage:
        """Keep one preview image per listing, on disk beside the database.

        Only ever called with bytes actually retrieved, so a later failed retrieval cannot replace
        a good image with nothing. That matters because a listing that disappears usually takes its
        images with it, and a disappearance is exactly what a user wants to look back at.
        """
        self.get_listing(listing_id)
        extension = extension.lstrip(".").lower() or "jpg"
        target = self.images_dir / listing_id[:2] / f"{listing_id}.{extension}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        now = utc_now()
        relative = str(target.relative_to(self._path.parent))
        with translating_errors(self._path, self._timeout), transaction(self._conn) as conn:
            conn.execute(
                "INSERT INTO listing_images "
                "(listing_id, path, source_url, retrieved_at, byte_size) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (listing_id) DO UPDATE SET "
                "path = excluded.path, source_url = excluded.source_url, "
                "retrieved_at = excluded.retrieved_at, byte_size = excluded.byte_size",
                (listing_id, relative, source_url, now, len(data)),
            )
        return StoredImage(
            listing_id=listing_id,
            path=relative,
            retrieved_at=now,
            source_url=source_url,
            byte_size=len(data),
        )

    def get_preview_image(self, listing_id: str) -> StoredImage | None:
        row = self._conn.execute(
            "SELECT * FROM listing_images WHERE listing_id = ?", (listing_id,)
        ).fetchone()
        if row is None:
            return None
        return StoredImage(
            listing_id=row["listing_id"],
            path=row["path"],
            retrieved_at=row["retrieved_at"],
            source_url=row["source_url"],
            byte_size=row["byte_size"],
        )

    def preview_image_path(self, listing_id: str) -> Path | None:
        stored = self.get_preview_image(listing_id)
        return self._path.parent / stored.path if stored else None

    # -- internals ---------------------------------------------------------

    def _resolve_listing(
        self,
        conn: sqlite3.Connection,
        source: str,
        row: SourceRow,
        run_id: str,
        observed_at: str,
    ) -> tuple[str, bool]:
        """Find the canonical listing this source row belongs to, or start one.

        Matching here is deliberately narrow: the same source's own identifier for the same
        property, or failing that the same source's own address text. Deciding that two
        *different* sources describe one house is the address matching feature's job, and
        guessing at it here would be exactly the silent bad merge this project is organized
        against.
        """
        if row.source_listing_id is not None:
            found = conn.execute(
                "SELECT ls.listing_id FROM listing_sources ls "
                "JOIN raw_listings rl ON rl.id = ls.raw_listing_id "
                "JOIN listings l ON l.id = ls.listing_id "
                "WHERE rl.source = ? AND rl.source_listing_id = ? AND l.retracted = 0 "
                "ORDER BY rl.fetched_at DESC LIMIT 1",
                (source, row.source_listing_id),
            ).fetchone()
        else:
            fields = row.fields
            found = conn.execute(
                "SELECT ls.listing_id FROM listing_sources ls "
                "JOIN raw_listings rl ON rl.id = ls.raw_listing_id "
                "JOIN listings l ON l.id = ls.listing_id "
                "WHERE rl.source = ? AND rl.source_listing_id IS NULL "
                "AND IFNULL(rl.address_line, '') = ? AND IFNULL(rl.unit, '') = ? "
                "AND IFNULL(rl.postal_code, '') = ? AND l.retracted = 0 "
                "ORDER BY rl.fetched_at DESC LIMIT 1",
                (
                    source,
                    fields.address_line or "",
                    fields.unit or "",
                    fields.postal_code or "",
                ),
            ).fetchone()

        if found is not None:
            return self._live_listing_id(conn, found["listing_id"]), False

        listing_id = _new_id()
        conn.execute(
            "INSERT INTO listings "
            "(id, first_observed_at, created_in_run, presence, superseded_by, retracted) "
            "VALUES (?, ?, ?, 'observed', NULL, 0)",
            (listing_id, observed_at, run_id),
        )
        return listing_id, True

    @staticmethod
    def _live_listing_id(conn: sqlite3.Connection, listing_id: str) -> str:
        """Follow a merge chain to whichever listing currently represents this property."""
        seen: set[str] = set()
        current = listing_id
        while current not in seen:
            seen.add(current)
            row = conn.execute(
                "SELECT superseded_by FROM listings WHERE id = ?", (current,)
            ).fetchone()
            if row is None or row["superseded_by"] is None:
                return current
            current = row["superseded_by"]
        return current

    def _record_movements(
        self,
        conn: sqlite3.Connection,
        run: RunRecord,
        observed_here: Iterable[str],
        at: str,
    ) -> None:
        """Note price and status transitions on the timeline as they happen."""
        previous = self.last_completed_run(run.search_name, before_seq=run.seq)
        if previous is None:
            return
        for listing_id in observed_here:
            before = self.snapshot_at(listing_id, previous.id)
            after = self.snapshot_at(listing_id, run.id)
            if before is None or after is None:
                continue
            if before.fields.price != after.fields.price:
                self._add_event(
                    conn,
                    listing_id,
                    run.id,
                    at,
                    "price_change",
                    {"from": before.fields.price, "to": after.fields.price},
                )
            if before.fields.listing_status != after.fields.listing_status:
                self._add_event(
                    conn,
                    listing_id,
                    run.id,
                    at,
                    "status_change",
                    {"from": before.fields.listing_status, "to": after.fields.listing_status},
                )

    @staticmethod
    def _add_event(
        conn: sqlite3.Connection,
        listing_id: str,
        run_id: str | None,
        at: str,
        kind: str,
        detail: dict[str, Any] | None,
    ) -> None:
        conn.execute(
            "INSERT INTO listing_events (listing_id, run_id, occurred_at, kind, detail) "
            "VALUES (?, ?, ?, ?, ?)",
            (listing_id, run_id, at, kind, json.dumps(detail) if detail is not None else None),
        )

    def _run_from(self, row: sqlite3.Row) -> RunRecord:
        sources = tuple(
            SourceOutcome(
                source=s["source"],
                outcome=s["outcome"],
                row_count=s["row_count"],
                truncated=bool(s["truncated"]),
                detail=s["detail"],
            )
            for s in self._conn.execute(
                "SELECT * FROM run_sources WHERE run_id = ? ORDER BY source", (row["id"],)
            )
        )
        return RunRecord(
            seq=row["seq"],
            id=row["id"],
            search_name=row["search_name"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            status=row["status"],
            sources=sources,
        )

    @staticmethod
    def _listing_from(row: sqlite3.Row) -> ListingRecord:
        return ListingRecord(
            id=row["id"],
            first_observed_at=row["first_observed_at"],
            created_in_run=row["created_in_run"],
            presence=row["presence"],
            superseded_by=row["superseded_by"],
            retracted=bool(row["retracted"]),
        )

    @staticmethod
    def _snapshot_from(row: sqlite3.Row) -> Snapshot:
        return Snapshot(
            run_id=row["run_id"],
            listing_id=row["listing_id"],
            observed_at=row["observed_at"],
            fields=ListingFields.from_row({name: row[name] for name in SNAPSHOT_FIELDS}),
        )

    @staticmethod
    def _area_note_from(row: sqlite3.Row) -> AreaNote:
        return AreaNote(
            id=row["id"],
            area_type=row["area_type"],
            area_value=row["area_value"],
            notes=row["notes"],
            updated_at=row["updated_at"],
        )


def _parse_utc(text: str) -> datetime:
    cleaned = text.replace("Z", "+00:00")
    moment = datetime.fromisoformat(cleaned)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)
