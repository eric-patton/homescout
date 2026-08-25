"""The database schema, version 1.

Two things here are load-bearing and deserve reading before anything is changed.

**History is append-only, and the database enforces it.** Every history table carries triggers that
abort an UPDATE or a DELETE. This is deliberately stronger than a code convention: it holds for code
written years from now by someone who has not read the project's rules, and it holds for a person
poking at the file with a SQLite browser. Corrections are new rows.

**A run writes one complete snapshot row per matching listing.** Not a difference, not a
change-detected subset. Answering "what did this run see" is then one indexed lookup rather than a
reconstruction across two tables that can disagree with each other. That costs storage and buys the
one property this whole product rests on.
"""

from collections.abc import Sequence

from ..records import FIELD_NAMES

SCHEMA_VERSION = 7

# The fields a difference event may name. Declared, never inferred from whatever a source happened
# to return: otherwise every source schema change would look like a market event, and the promise
# that an uncompared field never appears in a change would be unenforceable.
COMPARED_FIELDS: tuple[str, ...] = (
    "price",
    "listing_status",
    "beds",
    "baths",
    "sqft",
    "lot_sqft",
    "year_built",
    "property_type",
    "address_line",
    "unit",
    "city",
    "state",
    "postal_code",
)

# Recorded on every snapshot but never compared: these move for reasons that are not market events
# (coordinate jitter, a rewritten description, a reordered photo list).
INFORMATIONAL_FIELDS: tuple[str, ...] = (
    "county",
    "latitude",
    "longitude",
    "parcel_number",
    "listing_url",
    "description",
    "photo_urls",
    # A source's own idea of how long this has been listed. Retained because the first source
    # adapter will want it for debugging, and pointedly NOT compared: freshness is always
    # computed from our own first observation, never read from a source field.
    "days_on_market_source",
)

SNAPSHOT_FIELDS: tuple[str, ...] = COMPARED_FIELDS + INFORMATIONAL_FIELDS

# Which fields exist is the record's business; which of them are compared is this package's. The
# two must still partition each other exactly. A field added to the record and to neither set here
# would be silently dropped from every snapshot, which is the sort of loss no later run can undo,
# so it fails at import rather than at midnight three months from now.
if set(SNAPSHOT_FIELDS) != set(FIELD_NAMES):
    missing = sorted(set(FIELD_NAMES) - set(SNAPSHOT_FIELDS))
    unknown = sorted(set(SNAPSHOT_FIELDS) - set(FIELD_NAMES))
    raise RuntimeError(
        "the compared and informational sets must together account for every listing field: "
        f"unaccounted for {missing}, not on the record {unknown}"
    )

# Tables where a recorded row is never edited or removed. These are version 1's; a later version
# adds its own and protects them the same way, which is why the trigger generator takes a list
# rather than reading this one. Rewriting what version 1 creates is not allowed: a migration that
# has run on somebody's real database is history too.
APPEND_ONLY_TABLES: tuple[str, ...] = (
    "run_sources",
    "raw_listings",
    "listing_sources",
    "listing_snapshots",
    "listing_events",
)

_LISTING_COLUMNS = """
    price           INTEGER,
    listing_status  TEXT,
    beds            REAL,
    baths           REAL,
    sqft            INTEGER,
    lot_sqft        INTEGER,
    year_built      INTEGER,
    property_type   TEXT,
    address_line    TEXT,
    unit            TEXT,
    city            TEXT,
    state           TEXT,
    postal_code     TEXT,
    county          TEXT,
    latitude        REAL,
    longitude       REAL,
    parcel_number   TEXT,
    listing_url     TEXT,
    description     TEXT,
    photo_urls      TEXT,
    days_on_market_source INTEGER
"""

SCHEMA_V1 = f"""
-- ---------------------------------------------------------------------------
-- Runs
-- ---------------------------------------------------------------------------

-- A run is identified by a generated id rather than by its start time, so two runs starting within
-- the same clock second are not a special case.
--
-- `seq` is what runs are *ordered* by. Identity not depending on timestamp resolution is only half
-- the problem: two runs recorded in the same millisecond would also sort arbitrarily, which would
-- make "the previous completed run" ambiguous and a comparison irreproducible. Insertion order is
-- unambiguous and monotonic, so every ordering and every "at or before" boundary uses it.
CREATE TABLE runs (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    id           TEXT NOT NULL UNIQUE,
    search_name  TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed'))
);

CREATE INDEX idx_runs_search ON runs (search_name, seq);
CREATE INDEX idx_runs_status ON runs (status, seq);

-- A run row is not history: it has a lifecycle. But it may only move forwards, and only its
-- outcome may move. Everything identifying it is fixed at creation.
CREATE TRIGGER runs_forward_only BEFORE UPDATE ON runs
BEGIN
    SELECT CASE WHEN NOT (
        OLD.status = 'running'
        AND NEW.status IN ('completed', 'failed')
        AND NEW.seq = OLD.seq
        AND NEW.id = OLD.id
        AND NEW.search_name = OLD.search_name
        AND NEW.started_at = OLD.started_at
    ) THEN RAISE(ABORT, 'a run may only go from running to completed or failed, once')
    END;
END;

CREATE TRIGGER runs_no_delete BEFORE DELETE ON runs
BEGIN
    SELECT RAISE(ABORT, 'runs are never deleted');
END;

-- What each source contributed to a run, written once when that source finishes. This is what
-- keeps a source outage from reading as a market that emptied out.
CREATE TABLE run_sources (
    run_id     TEXT NOT NULL REFERENCES runs (id),
    source     TEXT NOT NULL,
    outcome    TEXT NOT NULL CHECK (outcome IN ('ok', 'failed', 'unavailable')),
    row_count  INTEGER NOT NULL DEFAULT 0,
    truncated  INTEGER NOT NULL DEFAULT 0,
    detail     TEXT,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (run_id, source)
);

-- ---------------------------------------------------------------------------
-- What sources returned, exactly as they returned it
-- ---------------------------------------------------------------------------

CREATE TABLE raw_listings (
    id                TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES runs (id),
    source            TEXT NOT NULL,
    source_listing_id TEXT,
    fetched_at        TEXT NOT NULL,
    payload           TEXT NOT NULL,
    {_LISTING_COLUMNS}
);

CREATE INDEX idx_raw_run ON raw_listings (run_id);
CREATE INDEX idx_raw_source_key ON raw_listings (source, source_listing_id);

-- ---------------------------------------------------------------------------
-- Canonical listings
-- ---------------------------------------------------------------------------

-- One row per physical property. Built on top of source rows, never instead of them.
--
-- A merge does not rewrite these: it writes a NEW listing and points its constituents at it via
-- superseded_by. An unmerge clears the pointer and retracts the merged row. Nothing is deleted and
-- no annotation ever moves, which is how a user's judgment survives a merge and its undo.
CREATE TABLE listings (
    id                TEXT PRIMARY KEY,
    first_observed_at TEXT NOT NULL,
    created_in_run    TEXT NOT NULL REFERENCES runs (id),
    presence          TEXT NOT NULL CHECK (presence IN ('observed', 'disappeared')),
    superseded_by     TEXT REFERENCES listings (id),
    retracted         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_listings_presence ON listings (presence);
CREATE INDEX idx_listings_superseded ON listings (superseded_by);

-- Presence and merge state move; identity and first observation never do.
CREATE TRIGGER listings_identity_is_fixed BEFORE UPDATE ON listings
BEGIN
    SELECT CASE WHEN NOT (
        NEW.id = OLD.id
        AND NEW.first_observed_at = OLD.first_observed_at
        AND NEW.created_in_run = OLD.created_in_run
    ) THEN RAISE(ABORT, 'a listing identity and its first observation are fixed')
    END;
END;

CREATE TRIGGER listings_no_delete BEFORE DELETE ON listings
BEGIN
    SELECT RAISE(ABORT, 'listings are never deleted; they are superseded or retracted');
END;

-- Which source rows a canonical listing was built from, and what justified each join.
CREATE TABLE listing_sources (
    listing_id     TEXT NOT NULL REFERENCES listings (id),
    raw_listing_id TEXT NOT NULL REFERENCES raw_listings (id),
    join_signal    TEXT NOT NULL,
    decided_by     TEXT NOT NULL CHECK (decided_by IN ('automatic', 'human')),
    linked_at      TEXT NOT NULL,
    PRIMARY KEY (listing_id, raw_listing_id)
);

CREATE INDEX idx_listing_sources_raw ON listing_sources (raw_listing_id);

-- ---------------------------------------------------------------------------
-- The record every difference is computed from
-- ---------------------------------------------------------------------------

-- One complete row per matching listing per run. See this module's docstring for why this is a
-- full copy rather than a change-detected subset.
CREATE TABLE listing_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT NOT NULL REFERENCES runs (id),
    listing_id  TEXT NOT NULL REFERENCES listings (id),
    observed_at TEXT NOT NULL,
    {_LISTING_COLUMNS},
    UNIQUE (run_id, listing_id)
);

CREATE INDEX idx_snapshots_listing ON listing_snapshots (listing_id, id);
CREATE INDEX idx_snapshots_run ON listing_snapshots (run_id);

-- The dated timeline: presence transitions, price and status movements, merges and their undo.
CREATE TABLE listing_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id  TEXT NOT NULL REFERENCES listings (id),
    run_id      TEXT REFERENCES runs (id),
    occurred_at TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN (
                    'first_seen', 'disappeared', 'returned',
                    'price_change', 'status_change',
                    'merged', 'unmerged'
                )),
    detail      TEXT
);

CREATE INDEX idx_events_listing ON listing_events (listing_id, occurred_at, id);
CREATE INDEX idx_events_kind ON listing_events (kind, occurred_at);

-- ---------------------------------------------------------------------------
-- The user's own judgment. Never written by a run.
-- ---------------------------------------------------------------------------

CREATE TABLE annotations (
    listing_id TEXT PRIMARY KEY REFERENCES listings (id),
    rank       INTEGER,
    verdict    TEXT,
    red_flags  TEXT,
    summary    TEXT,
    next_step  TEXT,
    notes      TEXT,
    updated_at TEXT NOT NULL
);

-- Observations about a place rather than about a property. These fill the export's second sheet.
CREATE TABLE area_notes (
    id         TEXT PRIMARY KEY,
    area_type  TEXT NOT NULL,
    area_value TEXT NOT NULL,
    notes      TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE (area_type, area_value)
);

-- ---------------------------------------------------------------------------
-- Stored preview images
-- ---------------------------------------------------------------------------

-- One preview image per listing, on disk beside the database rather than inside it. The path is
-- recorded here; the bytes are not. Full-size addresses live on the snapshot; those images are
-- not retained.
CREATE TABLE listing_images (
    listing_id   TEXT PRIMARY KEY REFERENCES listings (id),
    path         TEXT NOT NULL,
    source_url   TEXT,
    retrieved_at TEXT NOT NULL,
    byte_size    INTEGER
);
"""


#: Version 2, added by the rule engine (feat-008).
#:
#: A run's verdicts are recorded rather than recomputed. Re-evaluating today's criteria against an
#: old snapshot would silently rewrite what that run decided the moment somebody edited a rule,
#: which is the one thing this database is built not to allow. So verdicts are history, and they are
#: append-only like every other kind.
SCHEMA_V2 = """
CREATE TABLE rule_verdicts (
    run_id     TEXT NOT NULL REFERENCES runs (id),
    listing_id TEXT NOT NULL REFERENCES listings (id),
    rule_id    TEXT NOT NULL,
    severity   TEXT NOT NULL,
    verdict    TEXT NOT NULL,
    -- The names that were unknown, sorted, when the verdict is undetermined. Sorted because a
    -- recorded fact that varies with dictionary order is not reproducible.
    missing    TEXT,
    PRIMARY KEY (run_id, listing_id, rule_id)
);

CREATE INDEX rule_verdicts_by_rule ON rule_verdicts (run_id, rule_id, verdict);
"""

VERDICT_TABLES: tuple[str, ...] = ("rule_verdicts",)

#: Version 3, added by location enrichment (feat-007).
#:
#: The one table here that is deliberately not append-only, and the exception is worth stating
#: rather than noticing. Every other table records what this tool observed, and an observation is
#: never rewritten: the constitution's first non-negotiable is about what a run saw of a listing,
#: and product invariant 1 names snapshot and raw-listing history. This table is neither. It holds
#: a copy of somebody else's fact about a place, and refreshing a copy is what a cache is for.
#:
#: The narrower rule that does apply is the feature's own: a provider failing never removes a cached
#: value. A refresh replaces it; a failure leaves it exactly where it was, and it reads as stale.
SCHEMA_V3 = """
CREATE TABLE enrichment_values (
    provider   TEXT NOT NULL,
    -- The location, rounded to this provider's own precision, or a place name for the boundary
    -- provider. Two properties on one street share a key, and therefore share one lookup.
    cache_key  TEXT NOT NULL,
    -- The value's name in the rule engine's namespace, so a criterion and a cache row agree.
    name       TEXT NOT NULL,
    -- JSON, so a number stays a number, false stays false, and a known-absent value stays null
    -- rather than becoming an empty string.
    value      TEXT,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (provider, cache_key, name)
);
"""


#: Version 4, added by scheduling and digests (feat-012).
#:
#: What was reported about a run, as distinct from the run. Append-only like every other history
#: table here, because "the digest went out on the fourteenth" is an observation and this database
#: does not rewrite observations.
#:
#: It exists as a table rather than as a log line because it answers a question a person actually
#: asks the morning after: did last night's run mail me and I missed it, or did it decide there was
#: nothing worth saying? Those are different rows with different outcomes, and a third outcome says
#: there is no mail account at all.
#:
#: `target` is a path or a list of recipients. It is never a credential, and nothing that writes
#: here has one to write.
SCHEMA_V4 = """
CREATE TABLE deliveries (
    id           TEXT PRIMARY KEY,
    attempted_at TEXT NOT NULL,
    -- 'digest' for the file, 'email' for the message.
    channel      TEXT NOT NULL,
    target       TEXT,
    -- 'written' | 'sent' | 'suppressed' | 'skipped' | 'failed'
    outcome      TEXT NOT NULL,
    detail       TEXT,
    -- The runs this delivery reported on, comma separated, so a delivery can be traced back to
    -- what it was about even after the digest file has been overwritten by the next night.
    run_ids      TEXT
);

CREATE INDEX deliveries_by_time ON deliveries (attempted_at);
"""

DELIVERY_TABLES: tuple[str, ...] = ("deliveries",)


#: Version 5, added by address matching and merge review (feat-006).
#:
#: What a person decided about two records, which outranks every automatic signal for as long as the
#: database exists. Non-negotiable 6 says an ambiguous merge is flagged for a human and never
#: guessed; this is where the human's answer lives, and non-negotiable 7 is why it is append-only:
#: losing a user's judgment is the one failure this tool cannot have, because it is what the tool
#: replaces.
#:
#: A person changing their mind is a new row, not an edit. The latest row for a pair is the one that
#: counts, and "they said different in March and the same in June" stays readable, which matters
#: when somebody is working out why a record looks wrong.
#:
#: The pair key is the two listing ids sorted, so the same decision is found whichever order a later
#: run happens to compare them in.
SCHEMA_V5 = """
CREATE TABLE merge_decisions (
    id          TEXT PRIMARY KEY,
    pair_key    TEXT NOT NULL,
    listing_ids TEXT NOT NULL,
    -- 'same' | 'different'
    verdict     TEXT NOT NULL,
    decided_at  TEXT NOT NULL,
    decided_by  TEXT NOT NULL DEFAULT 'human',
    -- The record the merge produced, when the verdict was 'same'.
    merged_id   TEXT,
    note        TEXT
);

CREATE INDEX merge_decisions_by_pair ON merge_decisions (pair_key, decided_at);

-- A pair somebody decided about, later observed disagreeing with itself. Recorded and shown; acted
-- on by nobody. A person's decision is not overruled by evidence, it is questioned by it.
CREATE TABLE merge_contradictions (
    id         TEXT PRIMARY KEY,
    pair_key   TEXT NOT NULL,
    noticed_at TEXT NOT NULL,
    run_id     TEXT,
    detail     TEXT NOT NULL
);

CREATE INDEX merge_contradictions_by_pair ON merge_contradictions (pair_key, noticed_at);
"""

DECISION_TABLES: tuple[str, ...] = ("merge_decisions", "merge_contradictions")


#: Version 6, added by description field extraction (feat-009).
#:
#: What a model said about a piece of prose. A cache, like `enrichment_values`, and the second
#: deliberate exception to this file's append-only rule for the same reason: it holds a copy of
#: somebody else's answer rather than an observation of ours, so re-asking and overwriting loses
#: nothing that happened.
#:
#: Nothing the deterministic patterns produce is stored. They are regular expressions over at most
#: four thousand characters and running them costs less than the query that would fetch the answer,
#: and a cached pattern result would be stale the moment the pattern that wrote it is corrected.
#:
#: The key is the digest of the *description* rather than the listing, which is what makes "a
#: description is processed at most once" true regardless of how many properties or runs carry the
#: same text. The model is in the key too: a person who tries a small local model, dislikes the
#: answers and points the setting at a better one must be able to ask again, and a cache nobody can
#: invalidate is a trap rather than a saving.
#:
#: A row with a null `value` means the model was asked and determined nothing. That is a real
#: answer, it is what stops the same question being paid for every night, and it is why absence of
#: a row and a row with no value are different things here.
SCHEMA_V6 = """
CREATE TABLE extracted_values (
    digest       TEXT NOT NULL,
    model        TEXT NOT NULL,
    -- The field, as the rule engine's namespace calls it, so a criterion and a cached row agree.
    name         TEXT NOT NULL,
    value        TEXT,
    -- The quote from the description the value was attributed to. Never model prose: an answer
    -- that could not be attributed to the text was rejected before it reached here.
    evidence     TEXT,
    extracted_at TEXT NOT NULL,
    PRIMARY KEY (digest, model, name)
);
"""


#: Version 7, added by location enrichment (feat-007), change `broadband-from-the-fcc-files`.
#:
#: What fixed internet the FCC records as available in one census block. A cache, like
#: `enrichment_values` and `extracted_values`, and the third deliberate exception to this file's
#: append-only rule for the same reason: it is a copy of somebody else's published dataset, it is
#: refreshed a whole state at a time, and replacing a stale quarter with the current one loses
#: nothing that happened here.
#:
#: There is no per-property service to ask. The FCC's public API hands over per-state files and
#: nothing finer; the map's own point endpoint is closed and the coordinates that would let anybody
#: build one are licensed. So a point becomes a census block through a keyless FCC service, and the
#: block is answered from here (feat-007 M-7, D-12).
#:
#: `state` is on every row so that a refresh can replace one state without touching another, and so
#: that "we have no data for New Mexico" is answerable without a scan.
#:
#: Speeds exclude satellite, which is available almost everywhere and would otherwise report every
#: remote property as served while saying nothing about what it can get (D-13). They are the best
#: *advertised residential* figures a provider filed for the block, which is a weaker claim than a
#: measurement and is why every surface says both words.
SCHEMA_V7 = """
CREATE TABLE broadband_blocks (
    -- The 15-digit census block the FCC files key on.
    block_geoid    TEXT PRIMARY KEY,
    -- Two-letter state, so one state refreshes without touching another.
    state          TEXT NOT NULL,
    download_mbps  INTEGER,
    upload_mbps    INTEGER,
    -- Comma separated, in the order they read best. Brand names as filed.
    providers      TEXT,
    -- The quarter the FCC published, so an aging index can say how old it is.
    as_of          TEXT NOT NULL,
    loaded_at      TEXT NOT NULL
);

CREATE INDEX broadband_blocks_state ON broadband_blocks (state);
"""


def append_only_triggers(tables: Sequence[str] = APPEND_ONLY_TABLES) -> str:
    """Triggers that make a recorded row physically unrewritable.

    Generated rather than written out so that a table added to the list cannot be accidentally left
    unprotected. The list is a parameter because each schema version protects the tables it creates,
    and a version cannot create a trigger for a table that does not exist yet.
    """
    statements = []
    for table in tables:
        statements.append(
            f"CREATE TRIGGER {table}_no_update BEFORE UPDATE ON {table}\n"
            f"BEGIN\n"
            f"    SELECT RAISE(ABORT, '{table} is append-only: corrections are new rows');\n"
            f"END;"
        )
        statements.append(
            f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table}\n"
            f"BEGIN\n"
            f"    SELECT RAISE(ABORT, '{table} is append-only: "
            f"recorded history is never removed');\n"
            f"END;"
        )
    return "\n\n".join(statements)
