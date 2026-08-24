"""The command line.

Every command does the same three things: parse, call :mod:`homescout.api`, format. It holds no
decision about a listing, and it cannot: nothing in this package may import the store or the
sources, so there is no listing here to decide anything about.

Two contracts are kept here and nowhere else. **The primary stream belongs to the structured
document**: with machine output requested, one document reaches it and every progress line,
warning and diagnostic goes to the secondary stream, so an unattended caller never has to
disentangle them. **The exit code is stable**, and it is translated in exactly one place from the
kind of error the core raised.

Both streams are re-wrapped as UTF-8, because Windows is the primary platform, its console encoding
is not UTF-8, and property descriptions carry characters outside ASCII as a matter of course.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from .. import api, digest
from ..errors import HomescoutError, InvalidInput
from ..search import blocking
from . import render
from .codes import ExitCode, code_for, worst_of

VERSION = "0.1.0"

#: Printed at the end of `homescout --help`. The codes are the contract a scheduled task is built
#: on, so they have to be readable without opening the source: someone writing a Task Scheduler
#: entry should not have to go looking for what 1 means.
EXIT_CODES = """exit codes:
  0  success
  1  degraded: it completed, but at least one source or delivery failed
  2  invalid input: usage, an unknown name, or a saved search that does not validate
  3  cannot proceed yet: nothing to compare against, a run already going, the database in use,
     or a command whose feature is not built
  4  internal error

  One invocation that produces several settles on the worst: 4, then 2, then 3, then 1, then 0.
"""


@dataclass
class Answer:
    """One command's result, in both renderings.

    Two renderings of one computation, never two computations. That is the whole reason this type
    exists rather than each command deciding for itself what to print.
    """

    document: dict[str, Any] = field(default_factory=dict)
    text: str = ""
    code: ExitCode = ExitCode.SUCCESS


def _utf8(stream: TextIO) -> TextIO:
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        return stream
    return io.TextIOWrapper(buffer, encoding="utf-8", newline="\n", write_through=True)


def common_options() -> argparse.ArgumentParser:
    """The options every command takes.

    Attached to the top-level parser and to every subcommand, with suppressed defaults so that
    whichever side names one wins and the other does not overwrite it with a default. That is what
    makes both `homescout --json run x` and `homescout run x --json` work.

    No option here or anywhere else accepts a credential. Arguments are visible to other processes
    and Windows Task Scheduler stores them in plain text, so secrets come from the environment.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--db",
        default=argparse.SUPPRESS,
        help="the database file (default: HOMESCOUT_DB, else ./homescout.db)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="emit one structured document on the primary stream and nothing else",
    )
    parser.add_argument(
        "--output",
        default=argparse.SUPPRESS,
        metavar="PATH",
        help="also write the structured document to this file",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=argparse.SUPPRESS,
        metavar="SECONDS",
        help="seconds to wait between requests to one source (default: the shipped value)",
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    common = common_options()
    parser = argparse.ArgumentParser(
        prog="homescout",
        description="A local-first property search monitor.",
        epilog=EXIT_CODES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    parser.add_argument("--version", action="version", version=f"homescout {VERSION}")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", parents=[common], help="run a saved search")
    run.add_argument("name", nargs="?", help="the saved search to run")
    run.add_argument("--all", action="store_true", help="run every saved search")
    run.add_argument(
        "--no-images", action="store_true", help="do not retrieve preview images this run"
    )
    run.add_argument(
        "--deliver",
        action="store_true",
        help="write the digest to the configured path and email it if anything changed",
    )

    changes = commands.add_parser(
        "changes", parents=[common], help="what changed since an earlier point"
    )
    changes.add_argument("name")
    changes.add_argument(
        "--since", metavar="DATE", help="compare against the last run at or before this date"
    )

    searches = commands.add_parser("searches", parents=[common], help="manage saved searches")
    which = searches.add_subparsers(dest="action", required=True)
    which.add_parser("list", parents=[common], help="list saved searches")
    which.add_parser("show", parents=[common], help="show one saved search").add_argument("name")
    which.add_parser("validate", parents=[common], help="check one definition").add_argument("name")
    which.add_parser("create", parents=[common], help="start a new definition").add_argument("name")
    edit = which.add_parser("edit", parents=[common], help="change one definition")
    edit.add_argument("name")
    edit.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE", dest="assignments"
    )

    annotate = commands.add_parser(
        "annotate", parents=[common], help="record your own judgment about a property"
    )
    annotate.add_argument("listing_id")
    for option in ("rank", "verdict", "red-flags", "summary", "next-step", "notes"):
        annotate.add_argument(f"--{option}", default=None)

    matches = commands.add_parser(
        "matches", parents=[common], help="review property matches that need a human"
    )
    review = matches.add_subparsers(dest="action", required=True)
    review.add_parser("list", parents=[common], help="matches waiting for review")
    resolve = review.add_parser("resolve", parents=[common], help="settle one match")
    resolve.add_argument("match_id")
    verdict = resolve.add_mutually_exclusive_group(required=True)
    verdict.add_argument("--same", action="store_true", help="one property, so merge them")
    verdict.add_argument("--different", action="store_true", help="two properties, so keep both")

    enrich = commands.add_parser("enrich", parents=[common], help="attach public data to locations")
    enrich.add_argument("--stale", action="store_true", help="only values past their lifetime")
    enrich.add_argument("--search", metavar="NAME", help="only properties in this saved search")

    extract = commands.add_parser(
        "extract", parents=[common], help="ask the configured model about listing descriptions"
    )
    extract.add_argument("--search", metavar="NAME", help="only properties in this saved search")
    extract.add_argument(
        "--limit", type=int, metavar="N", help="ask about at most this many descriptions"
    )
    extract.add_argument(
        "--listing",
        metavar="ID",
        help="show what was read out of one property, and the words it was read from",
    )

    export = commands.add_parser("export", parents=[common], help="write a spreadsheet")
    export.add_argument("--search", metavar="NAME")
    export.add_argument("--to", metavar="PATH", help="where to write it")
    export.add_argument(
        "--format", choices=("xlsx", "csv"), default="xlsx", help="spreadsheet or plain text"
    )
    export.add_argument("--template", metavar="NAME", help="which column set (default: default)")
    export.add_argument(
        "--force", action="store_true", help="replace the file if it is already there"
    )
    export.add_argument(
        "--include-dropped",
        action="store_true",
        help="include properties a drop rule removed",
    )
    export.add_argument(
        "--templates", action="store_true", help="list the column sets available and stop"
    )

    show = commands.add_parser(
        "show", parents=[common], help="everything known about one property"
    )
    show.add_argument("listing_id")

    areas = commands.add_parser(
        "areas", parents=[common], help="notes about a town or region rather than a property"
    )
    areas.add_argument("--set", metavar="KIND:PLACE", help="write a note about this place")
    areas.add_argument("--notes", metavar="TEXT", help="what to write")

    serve = commands.add_parser("serve", parents=[common], help="start the local browser interface")
    serve.add_argument(
        "--port", type=int, default=None, help="default: HOMESCOUT_PORT, else 8765"
    )
    serve.add_argument("--open", action="store_true", help="open a browser at it")
    # Deliberately no --host. The constitution binds this to localhost, `serve.serve` refuses
    # anything else at runtime, and an option that can only ever hold one value is a knob for
    # something that is not on offer. A test in `test_cli_contract.py` keeps it that way.

    return parser


def _assignments(pairs: Sequence[str]) -> dict[str, object]:
    changes: dict[str, object] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise InvalidInput(f"--set wants KEY=VALUE, got {pair!r}.")
        changes[key.strip()] = value.strip()
    return changes


def _summary_of(search: Any) -> dict[str, Any]:
    return {"name": search.name, "sources": list(search.sources), "areas": len(search.areas)}


def _problems(found: Sequence[Any]) -> list[dict[str, str]]:
    return [
        {"location": p.location, "message": p.message, "severity": p.severity} for p in found
    ]


def _run(workspace: api.Workspace, args: argparse.Namespace, note: Any) -> Answer:
    if args.all:
        result = api.run_all(workspace, progress=note)
        entries = [
            digest.entry(
                workspace.store,
                search_name=outcome.run.search_name,
                comparison=outcome.comparison,
                outcome=outcome,
            )
            for outcome in result.outcomes
        ]
        skipped = [
            {
                "name": s.name,
                "reason": s.reason,
                "detail": s.detail,
                "problems": _problems(s.problems),
            }
            for s in result.skipped
        ]
        document = digest.build(entries, kind="run", skipped=skipped)
        codes = [
            ExitCode.DEGRADED if outcome.degraded else ExitCode.SUCCESS
            for outcome in result.outcomes
        ]
        codes.extend(
            ExitCode.INVALID_INPUT if s.reason == "invalid" else ExitCode.PRECONDITION
            for s in result.skipped
        )
        return Answer(document, render.digest(document), worst_of(codes))

    if not args.name:
        raise InvalidInput("Name a saved search to run, or pass --all to run every one of them.")
    outcome = api.run_search(workspace, args.name, progress=note)
    entry = digest.entry(
        workspace.store,
        search_name=args.name,
        comparison=outcome.comparison,
        outcome=outcome,
    )
    document = digest.build([entry], kind="run")
    code = ExitCode.DEGRADED if outcome.degraded else ExitCode.SUCCESS
    return Answer(document, render.digest(document), code)


def _delivered(workspace: api.Workspace, answer: Answer, settings: Any) -> Answer:
    """What was done with the report, folded into the answer.

    The document handed to delivery is the one built above, without this section in it. A file
    cannot record whether it was written, and a reader of the digest wants what the run found
    rather than an account of how it was told about it. This invocation's own answer is a different
    question, so the section goes there.
    """
    outcome = api.deliver(workspace, answer.document, settings=settings)
    document = {
        **answer.document,
        "delivery": {
            "moved": outcome.moved,
            "channels": [
                {
                    "channel": channel.channel,
                    "outcome": channel.outcome,
                    "target": channel.target,
                    "detail": channel.detail,
                }
                for channel in outcome.channels
            ],
        },
    }
    codes = [answer.code]
    if outcome.digest.failed:
        # Not degraded. A scheduled agent reads the file, and telling it the run was merely
        # degraded when the file it is about to read is not there would be a lie of exactly the
        # wrong shape.
        codes.append(ExitCode.INTERNAL_ERROR)
    if outcome.email.failed:
        codes.append(ExitCode.DEGRADED)
    text = f"{answer.text}\n\ndelivery:\n{render.delivery(outcome)}".lstrip()
    return Answer(document, text, worst_of(codes))


def _changes(workspace: api.Workspace, args: argparse.Namespace) -> Answer:
    comparison = api.changes(workspace, args.name, since=args.since)
    entry = digest.entry(workspace.store, search_name=args.name, comparison=comparison)
    document = digest.build([entry], kind="comparison")
    return Answer(document, render.digest(document))


def _searches(workspace: api.Workspace, args: argparse.Namespace) -> Answer:
    if args.action == "list":
        names = api.list_searches(workspace)
        return Answer(digest.envelope("searches", searches=list(names)), render.searches(names))
    if args.action == "show":
        found = api.show_search(workspace, args.name)
        return Answer(
            digest.envelope("search", search=_summary_of(found)), render.definition(found)
        )
    if args.action == "validate":
        problems = api.validate_search(workspace, args.name)
        stopping = blocking(problems)
        document = digest.envelope(
            "validation",
            name=args.name,
            valid=not stopping,
            problems=_problems(problems),
        )
        code = ExitCode.INVALID_INPUT if stopping else ExitCode.SUCCESS
        return Answer(document, render.problems(args.name, problems), code)
    if args.action == "create":
        made = api.create_search(workspace, args.name)
        return Answer(digest.envelope("search", search=_summary_of(made)), render.definition(made))
    edited = api.edit_search(workspace, args.name, _assignments(args.assignments))
    return Answer(digest.envelope("search", search=_summary_of(edited)), render.definition(edited))


def _enrich(workspace: api.Workspace, args: argparse.Namespace, note: Any) -> Answer:
    outcome = api.enrich(
        workspace, stale_only=args.stale, search=args.search, progress=note
    )
    document = digest.envelope(
        "enrichment",
        properties=outcome.properties,
        without_location=outcome.without_location,
        providers=[
            {
                "provider": found.provider,
                "outcome": found.outcome,
                "looked_up": found.looked_up,
                "cached": found.cached,
                "detail": found.detail,
            }
            for found in outcome.providers
        ],
    )
    # Degraded, not failed: one provider down costs one column, and the values that were obtained
    # are worth the same as they would have been.
    code = ExitCode.DEGRADED if outcome.degraded else ExitCode.SUCCESS
    return Answer(document, render.enrichment(outcome), code)


def _extract(workspace: api.Workspace, args: argparse.Namespace, note: Any) -> Answer:
    if args.listing:
        return _extracted_for(workspace, args.listing)
    outcome = api.extract(
        workspace, search=args.search, limit=args.limit, progress=note
    )
    document = digest.envelope(
        "extraction",
        descriptions=outcome.descriptions,
        cached=outcome.cached,
        asked=outcome.asked,
        recorded=outcome.recorded,
        truncated=outcome.truncated,
        rejected=list(outcome.rejected),
        failures=list(outcome.failures),
        skipped=outcome.skipped,
    )
    # Degraded, not failed, on the same principle as a provider being down: a model this tool could
    # not reach costs the fields it would have filled and nothing else, and the deterministic values
    # never involved it.
    code = ExitCode.DEGRADED if outcome.degraded else ExitCode.SUCCESS
    return Answer(document, render.extraction(outcome), code)


def _extracted_for(workspace: api.Workspace, listing_id: str) -> Answer:
    """What was recovered from one property's description, and where it says so.

    The answer to "why does this column say well", which is a question somebody will ask the first
    time a value surprises them. Both surfaces read the same thing (product invariant 5); this is
    the command line's half.
    """
    found = api.extracted_for(workspace, listing_id)
    payload = [
        {
            "field": name,
            "value": entry.value,
            "provenance": entry.provenance,
            "evidence": list(entry.evidence),
            "conflicted": entry.conflicted,
        }
        for name, entry in found.items()
    ]
    document = digest.envelope("extracted", listing_id=listing_id, fields=payload)
    return Answer(document, render.extracted(listing_id, found))


def _export(workspace: api.Workspace, args: argparse.Namespace) -> Answer:
    if args.templates:
        found = api.export_templates(workspace)
        return Answer(
            digest.envelope("templates", templates=list(found)),
            "\n".join(found),
        )
    written = api.export(
        workspace,
        search=args.search,
        to=args.to,
        template=args.template,
        format=args.format,
        force=args.force,
        include_dropped=args.include_dropped,
    )
    document = digest.envelope(
        "export",
        path=str(written.path),
        format=written.format,
        template=written.template,
        properties=written.properties,
        areas=written.areas,
        columns=list(written.columns),
        empty_columns={origin: list(names) for origin, names in written.empty.items()},
    )
    return Answer(document, render.export(written))


def _show(workspace: api.Workspace, args: argparse.Namespace) -> Answer:
    """One property's full picture, which is the terminal half of the browser's detail surface.

    Product invariant 5: every capability is reachable from both surfaces. This one arrived with the
    browser interface, so it arrived here at the same time.
    """
    found = api.listing(workspace, args.listing_id)
    return Answer(digest.envelope("listing", listing=found), render.listing(found))


def _areas(workspace: api.Workspace, args: argparse.Namespace) -> Answer:
    if args.set:
        kind, _, place = args.set.partition(":")
        if not place:
            raise InvalidInput("--set wants KIND:PLACE, such as city:Portales.")
        api.set_area_note(workspace, kind.strip(), place.strip(), args.notes)
    found = api.area_notes(workspace)
    payload = [
        {
            "area_type": note.area_type,
            "area_value": note.area_value,
            "notes": note.notes,
            "updated_at": note.updated_at,
        }
        for note in found
    ]
    return Answer(digest.envelope("areas", areas=payload), render.areas(found))


def _annotate(workspace: api.Workspace, args: argparse.Namespace) -> Answer:
    values = {
        name: getattr(args, name)
        for name in ("rank", "verdict", "red_flags", "summary", "next_step", "notes")
        if getattr(args, name) is not None
    }
    if not values:
        raise InvalidInput("Give at least one thing to record, such as --verdict or --notes.")
    if "rank" in values:
        try:
            values["rank"] = int(values["rank"])
        except ValueError:
            raise InvalidInput(f"--rank wants a whole number, got {values['rank']!r}.") from None
    written = api.annotate(workspace, args.listing_id, **values)
    payload = {
        "listing_id": written.listing_id,
        "updated_at": written.updated_at,
        **written.content(),
    }
    return Answer(digest.envelope("annotation", annotation=payload), render.annotation(written))


def _matches(workspace: api.Workspace, args: argparse.Namespace) -> Answer:
    if args.action == "list":
        pending = api.pending_matches(workspace)
        payload = [
            {
                "id": m.id,
                "listing_ids": list(m.listing_ids),
                "agreed": list(m.agreed),
                "conflicted": list(m.conflicted),
                "noticed_at": m.noticed_at,
            }
            for m in pending
        ]
        return Answer(digest.envelope("matches", matches=payload), render.matches(pending))
    merged = api.resolve_match(workspace, args.match_id, same=args.same)
    verdict = "same" if args.same else "different"
    document = digest.envelope(
        "resolution", match_id=args.match_id, verdict=verdict, merged_listing_id=merged
    )
    text = (
        f"Merged into {merged}." if merged else "Recorded as different properties."
    )
    return Answer(document, text)


def _dispatch(
    workspace: api.Workspace, args: argparse.Namespace, note: Any, settings: Any = None
) -> Answer:
    if args.command == "run":
        answer = _run(workspace, args, note)
        return _delivered(workspace, answer, settings) if args.deliver else answer
    if args.command == "changes":
        return _changes(workspace, args)
    if args.command == "searches":
        return _searches(workspace, args)
    if args.command == "annotate":
        return _annotate(workspace, args)
    if args.command == "matches":
        return _matches(workspace, args)
    if args.command == "export":
        return _export(workspace, args)
    if args.command == "extract":
        return _extract(workspace, args, note)
    if args.command == "enrich":
        return _enrich(workspace, args, note)
    if args.command == "show":
        return _show(workspace, args)
    if args.command == "areas":
        return _areas(workspace, args)
    if args.command == "serve":
        api.serve(workspace, port=args.port, open_browser=args.open)
        return Answer(digest.envelope("served"), "")
    raise InvalidInput(f"No command named {args.command!r}.")


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    out = stdout if stdout is not None else _utf8(sys.stdout)
    err = stderr if stderr is not None else _utf8(sys.stderr)
    parser = build_parser()

    try:
        with redirect_stdout(out), redirect_stderr(err):
            args = parser.parse_args(argv)
    except SystemExit as stop:  # --help and usage errors both arrive here
        return int(stop.code or 0)

    wants_json = getattr(args, "json", False)
    output = getattr(args, "output", None)

    def note(message: str) -> None:
        print(message, file=err)

    settings: Any = None

    try:
        # Checked before anything is opened or fetched: discovering a missing directory after an
        # hour of throttled requests is the failure this guard exists to prevent.
        if output is not None:
            parent = Path(output).parent
            if not parent.exists():
                raise InvalidInput(
                    f"There is no directory {str(parent)!r} to write {output!r} into. "
                    f"Create it first; nothing has been run."
                )

        # The same guard, for the configured digest path, and for the mail account. Reading the
        # settings here rather than at the end is the whole difference between a scheduled task
        # that reports a missing recipient in its first second and one that fetches all night
        # before finding out it has nobody to tell.
        if getattr(args, "deliver", False):
            settings = api.delivery_settings(api.database_path(getattr(args, "db", None)).parent)
            where = settings.digest_path.parent
            if not where.exists():
                raise InvalidInput(
                    f"There is no directory {str(where)!r} to write the digest into. "
                    f"Create it first; nothing has been run."
                )

        with api.open_workspace(
            getattr(args, "db", None),
            delay=getattr(args, "delay", None),
            images=not getattr(args, "no_images", False),
            # The one command that needs it. A web server hands requests to worker threads and
            # SQLite refuses a connection used from a thread other than the one that opened it; the
            # interface holds a lock around every request, which is what makes lifting that check
            # safe. Every other command is one thread and keeps the check as a real guard.
            shared=args.command == "serve",
        ) as workspace:
            answer = _dispatch(workspace, args, note, settings)
    except HomescoutError as failure:
        print(str(failure), file=err)
        return int(code_for(failure))
    except Exception as failure:  # noqa: BLE001 - the end of the line, and it says so
        print(f"homescout failed unexpectedly: {failure}", file=err)
        return int(ExitCode.INTERNAL_ERROR)

    rendered = json.dumps(answer.document, ensure_ascii=False, indent=2)
    if wants_json:
        print(rendered, file=out)
    else:
        print(answer.text, file=out)

    if output is not None:
        try:
            Path(output).write_text(rendered + "\n", encoding="utf-8")
        except OSError as failure:
            # Reported, and reflected in the code, but the primary stream is left exactly as it
            # would have been: a command asked for readable output does not start emitting a
            # structured document because a file could not be opened.
            print(f"Could not write {output!r}: {failure}", file=err)
            return int(ExitCode.INTERNAL_ERROR)

    return int(answer.code)


def run() -> None:
    """The console entry point, which is what Windows Task Scheduler invokes."""
    sys.exit(main())


if __name__ == "__main__":  # pragma: no cover
    run()
