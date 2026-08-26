"""Turning an answer into text a person can read.

Human output is the default, and it is the same computation as machine output rendered differently,
never a second one. Nothing here decides anything: it receives what the core returned and formats
it.

No colour anywhere. The accessibility requirement says human output must convey nothing by colour
alone, and the way to be sure of that is to use none.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from ..search import blocking

DASH = "-"


def money(value: Any) -> str:
    return f"${value:,}" if isinstance(value, int) else DASH


def _cell(value: Any) -> str:
    if value is None:
        return DASH
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return str(value)


def table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    """A plain aligned table. Two spaces between columns, nothing drawn."""
    body = [[_cell(cell) for cell in row] for row in rows]
    if not body:
        return ""
    widths = [
        max(len(str(headers[i])), *(len(row[i]) for row in body)) for i in range(len(headers))
    ]
    lines = ["  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)).rstrip()]
    lines.append("  ".join(DASH * widths[i] for i in range(len(headers))))
    for row in body:
        lines.append("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))).rstrip())
    return "\n".join(lines)


def address(summary: dict[str, Any]) -> str:
    """One property's address. The composing is the digest's, so both surfaces say it the same."""
    from ..digest import address_of

    return address_of(summary) or "(no address)"


def _properties(title: str, rows: Sequence[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    out = [f"{title} ({len(rows)}):"]
    for row in rows:
        detail = money(row.get("price"))
        change = row.get("price_change")
        if change:
            detail = f"{money(change.get('before'))} to {money(change.get('after'))}"
        status = row.get("status_change")
        if status:
            detail = f"{status.get('before') or DASH} to {status.get('after') or DASH}"
        out.append(f"  {address(row)}  {detail}")
    return out


def digest(document: dict[str, Any]) -> str:
    """The same document machine output carries, said out loud."""
    lines: list[str] = []
    for search in document.get("searches", []):
        counts = search["counts"]
        headline = (
            f"{search['name']}: {counts['matched']} matched, {counts['new']} new, "
            f"{counts['changed']} changed, {counts['gone']} gone, {counts['returned']} returned"
        )
        if search.get("outcome"):
            headline += f" [{search['outcome']}]"
        lines.append(headline)
        waiting = counts.get("waiting_for_review") or 0
        if waiting:
            lines.append(
                f"  {waiting} pair{'s' if waiting != 1 else ''} of records need a decision: "
                f"run `homescout matches list`"
            )
        for source in search.get("sources", []):
            note = f", {source['detail']}" if source.get("detail") else ""
            applied = ", ".join(source["applied_by_source"]) or "nothing"
            locally = ", ".join(source["applied_locally"]) or "nothing"
            lines.append(
                f"  {source['source']}: {source['outcome']}, {source['rows']} listings"
                f"{' (incomplete)' if source['truncated'] else ''}{note}"
            )
            lines.append(f"    filtered by the source: {applied}; filtered here: {locally}")
        lines.extend(f"  {line}" for line in _properties("New", search["new"]))
        lines.extend(f"  {line}" for line in _properties("Price changes", search["price_changes"]))
        lines.extend(
            f"  {line}" for line in _properties("Status changes", search["status_changes"])
        )
        lines.extend(f"  {line}" for line in _properties("Gone", search["gone"]))
        lines.extend(f"  {line}" for line in _properties("Returned", search["returned"]))
        lines.append("")
    for skip in document.get("skipped", []):
        lines.append(f"{skip['name']}: skipped, {skip.get('reason', 'not valid')}")
        for problem in skip["problems"]:
            lines.append(f"  {problem['location']}: {problem['message']}")
        if not skip["problems"] and skip.get("detail"):
            lines.append(f"  {skip['detail']}")
    return "\n".join(lines).rstrip() or "Nothing to report."


def searches(names: Sequence[str]) -> str:
    if not names:
        return "No saved searches are configured."
    return "\n".join(names)


def definition(search: Any) -> str:
    lines = [
        f"name:    {search.name}",
        f"sources: {', '.join(search.sources) or DASH}",
        f"areas:   {len(search.areas)}",
    ]
    written = str(getattr(search, "extract_notes", "") or "")
    if written:
        # Shown because it is sent. Somebody looking at a search should be able to see everything
        # that leaves with it without opening the file.
        lines.append(f"notes:   {written}")
    return "\n".join(lines)


def problems(name: str, found: Sequence[Any]) -> str:
    """What validation found, with the two kinds told apart.

    Only a `problem` stops a search running. A `notice` is worth knowing and changes nothing, and
    counting one as a failure is not a wording slip: somebody told their file is invalid, whose file
    is fine, goes and fixes something that was never broken. The structured document has always
    drawn this line. This is meant to be the same computation said in prose rather than a second
    opinion about it (gap-004).
    """
    if not found:
        return f"{name} is valid."
    stopping = blocking(found)
    aside = len(found) - len(stopping)
    if stopping:
        head = f"{name} is not valid ({_things(len(stopping), 'problem')}"
        head += f", {_things(aside, 'notice')}):" if aside else "):"
    else:
        head = f"{name} is valid ({_things(aside, 'notice')}):"
    lines = [head]
    # Marked by word rather than by colour, which the accessibility requirement rules out, and
    # needed at all because a list holding both kinds otherwise reads as a list of failures.
    lines.extend(
        f"  {'' if p.severity == 'problem' else 'note '}{p.location}: {p.message}" for p in found
    )
    return "\n".join(lines)


def _things(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def enrichment(outcome: Any) -> str:
    """What an enrichment pass did, for somebody watching it rather than parsing it."""
    lines = [f"{outcome.properties} properties"]
    if outcome.without_location:
        lines[0] += f", {outcome.without_location} with no location to look up"
    for found in outcome.providers:
        detail = f" ({found.detail})" if found.detail else ""
        # Said here rather than left to the README: a column that answers for one state and reads as
        # empty everywhere else is a column somebody will otherwise misread as a gap (AC-26).
        where = f" [{found.coverage} only]" if getattr(found, "coverage", None) else ""
        lines.append(
            f"  {found.provider}{where}: {found.outcome}, {found.looked_up} looked up, "
            f"{found.cached} already cached{detail}"
        )
    return "\n".join(lines)


def extraction(outcome: Any) -> str:
    """What the model pass did, for somebody watching it rather than parsing it."""
    if outcome.skipped and not outcome.asked and not outcome.cached:
        return f"Nothing asked: {outcome.skipped}"
    lines = [
        f"{outcome.descriptions} distinct descriptions, "
        f"{outcome.cached} already answered, {outcome.asked} asked about"
    ]
    if outcome.recorded:
        lines.append(f"  {outcome.recorded} values recorded")
    if outcome.truncated:
        lines.append(f"  {outcome.truncated} descriptions were too long and were cut")
    if outcome.rejected:
        lines.append(f"  {len(outcome.rejected)} answers rejected:")
        lines.extend(f"    {reason}" for reason in outcome.rejected[:5])
        if len(outcome.rejected) > 5:
            lines.append(f"    and {len(outcome.rejected) - 5} more")
    for failure in outcome.failures[:5]:
        lines.append(f"  could not be processed: {failure}")
    if len(outcome.failures) > 5:
        lines.append(f"  and {len(outcome.failures) - 5} more could not be processed")
    if outcome.skipped:
        lines.append(f"  {outcome.skipped}")
    return "\n".join(lines)


def export(written: Any) -> str:
    """What was written, and which columns came out empty and why.

    The second half is the point. A person opening a thirty-two column sheet with eleven blank
    columns has three different questions, and telling them which kind of blank each one is saves an
    afternoon spent looking for a bug in this tool.
    """
    lines = [
        f"{written.properties} properties written to {written.path}",
        f"  template {written.template}, {len(written.columns)} columns",
    ]
    if written.format == "xlsx":
        lines.append(f"  a second sheet carries {written.areas} area notes")
    for reason in written.reasons():
        lines.append(f"  empty because {reason}")
    return "\n".join(lines)


def extracted(listing_id: str, found: Any) -> str:
    """One property's six recovered fields, how each was determined, and the words it came from.

    The evidence is the point. A value with no visible reason is a value nobody can argue with, and
    a person who cannot argue with it cannot trust it either.
    """
    lines = [f"{listing_id}"]
    for name, entry in found.items():
        label = name.replace("_", " ")
        if entry.conflicted:
            lines.append(f"  {label}: could not tell, the description says more than one thing")
        elif entry.value is None:
            lines.append(f"  {label}: not stated")
        else:
            lines.append(f"  {label}: {entry.value}  (from the {entry.provenance})")
        for quote in entry.evidence:
            lines.append(f"      {quote}")
    return "\n".join(lines)


def annotation(written: Any) -> str:
    rows = [
        (name.replace("_", " "), getattr(written, name))
        for name in ("rank", "verdict", "red_flags", "summary", "next_step", "notes")
    ]
    return "\n".join(f"{label}: {_cell(value)}" for label, value in rows)


def matches(pending: Sequence[Any]) -> str:
    """The queue, with enough of each property to decide without opening either one.

    A table of identifiers and signals says everything about the *match* and nothing about the two
    houses, and the houses are what somebody is actually ruling on. Two records from two different
    sites at one address is a house seen twice; "Mimbres Rd" against "Mimbres Ct" at a different
    price is two houses. Both readings need the addresses.

    The browser shows the two photographs here, which settles most pairs at a glance. A terminal
    has no pictures, so it shows everything else, from the same core answer.
    """
    if not pending:
        return "No matches are waiting for review."
    lines: list[str] = []
    for found in pending:
        lines.append(f"{found['id']}  ({len(found['listing_ids'])} records)")
        for prop in found.get("properties", ()):
            where = ", ".join(p for p in (prop.get("address_line"), prop.get("city")) if p)
            seen = ", ".join(prop.get("sources") or ()) or "no source recorded"
            named = where or prop["listing_id"][:8]
            lines.append(f"  {named}  {money(prop.get('price'))}  [{seen}]")
        if found.get("agreed"):
            lines.append(f"  agrees:    {', '.join(found['agreed'])}")
        if found.get("conflicted"):
            lines.append(f"  disagrees: {', '.join(found['conflicted'])}")
        lines.append("")
    return "\n".join(lines).rstrip()


def delivery(outcome: Any) -> str:
    """What was done with the report, for somebody watching rather than parsing.

    Both channels always appear, including the one that did nothing. A person who set up an email
    digest and got no email needs to be told which of the three silences this was: nothing to say,
    no account configured, or a server that refused.
    """
    lines = []
    for channel in outcome.channels:
        detail = f" ({channel.detail})" if channel.detail else ""
        where = f" {channel.target}" if channel.target else ""
        lines.append(f"  {channel.channel}: {channel.outcome}{where}{detail}")
    return "\n".join(lines)


def listing(found: Any) -> str:
    """One property's full picture, for a terminal.

    The provenance at the end is the part worth having: a merged record is source rows joined by a
    signal, and the only way to tell a real record from a bad merge is to see both.
    """
    fields = found.get("fields") or {}
    address = ", ".join(
        str(fields[name])
        for name in ("address_line", "unit", "city", "state", "postal_code")
        if fields.get(name)
    )
    lines = [address or found["listing_id"], ""]

    for label, name in (
        ("price", "price"),
        ("status", "listing_status"),
        ("beds", "beds"),
        ("baths", "baths"),
        ("sq ft", "sqft"),
        ("year built", "year_built"),
        ("type", "property_type"),
        ("county", "county"),
    ):
        lines.append(f"  {label:<14} {_cell(fields.get(name))}")
    lines.append(f"  {'days on market':<14} {_cell(found.get('days_on_market'))}")
    lines.append(f"  {'first seen':<14} {_cell(found.get('first_observed_at'))}")
    lines.append(f"  {'presence':<14} {_cell(found.get('presence'))}")

    extracted = {k: v for k, v in (found.get("extracted") or {}).items() if v.get("value")}
    if extracted:
        lines += ["", "read out of the description:"]
        for name, entry in sorted(extracted.items()):
            lines.append(f"  {name.replace('_', ' '):<14} {entry['value']} ({entry['provenance']})")

    enrichment = {k: v for k, v in (found.get("enrichment") or {}).items() if v is not None}
    if enrichment:
        lines += ["", "where it is:"]
        for name, held in sorted(enrichment.items()):
            lines.append(f"  {name.replace('_', ' '):<24} {_cell(held)}")

    sources = found.get("sources") or []
    if sources:
        lines += ["", "assembled from:"]
        for link in sources:
            why = f", joined on {link['join_signal']}" if link.get("join_signal") else ""
            seen = link.get("times_seen") or 1
            times = f", seen in {seen} runs" if seen > 1 else ""
            lines.append(f"  {link['source']} {link.get('source_listing_id') or ''}{why}{times}")
            # One address per site, because a merged property has one page on each and they are
            # not interchangeable to anyone keeping a list on one of them.
            if link.get("listing_url"):
                lines.append(f"    {link['listing_url']}")

    annotation = {k: v for k, v in (found.get("annotation") or {}).items() if v not in (None, "")}
    if annotation:
        lines += ["", "your own judgment:"]
        for name, held in annotation.items():
            lines.append(f"  {name.replace('_', ' '):<14} {_cell(held)}")

    return "\n".join(lines)


def broadband(found: dict[str, Any]) -> str:
    """What internet data is held, and what would get more of it.

    Says the two words that travel with the number everywhere: the figure is the census block's,
    not the property's, and it is advertised rather than measured.
    """
    lines: list[str] = []
    loaded = found.get("loaded")
    if loaded:
        lines.append(
            f"{loaded['state']}: {loaded['blocks']:,} census blocks, as of {loaded['as_of']}"
        )
        lines.append("")

    states = found.get("states") or []
    if not states:
        lines.append("No state's data is held yet.")
    else:
        lines.append("Held:")
        for row in states:
            lines.append(
                f"  {row['state']}  {row['blocks']:,} blocks, published {row['as_of']}"
            )

    if not found.get("configured"):
        lines.append("")
        lines.append(
            "Not configured: " + " and ".join(found.get("variables") or []) + " are both needed."
        )
    lines.append("")
    lines.append(
        "These are the best advertised residential speeds in a property's census block, as filed "
        "with the FCC. Not a measurement, and not the property's own line. Satellite is left out, "
        "because it is available almost everywhere and would tell you nothing."
    )
    return "\n".join(lines)


def model_notes(found: dict[str, Any]) -> str:
    """What this installation tells the model, or the fact that it tells it nothing."""
    written = str(found.get("notes") or "")
    where = found.get("path")
    if not written:
        return (
            "Nothing written. What you put here is sent to the model with every description, to "
            f"say how listings in your market are written.\n  {where}"
        )
    lines = [written, "", f"Sent to the model with every description. Kept in {where}."]
    if found.get("truncated"):
        lines.insert(1, f"Cut to {found.get('limit')} characters before it is sent.")
    return "\n".join(lines)


def areas(notes: Sequence[Any]) -> str:
    """Notes about places rather than about properties."""
    if not notes:
        return "No notes about any area yet."
    return table(
        ["Area", "Place", "Notes"],
        [
            [note.area_type, note.area_value, (note.notes or "").replace("\n", " ")]
            for note in notes
        ],
    )


def overview(found: dict[str, Any]) -> str:
    """What is in here, in the few numbers worth seeing before anything else."""
    searches = found["searches"]
    lines = [
        f"{found['properties']} properties across {searches} "
        f"saved search{'' if searches == 1 else 'es'}",
        f"last run: {found['last_run_at'] or 'never'}",
    ]
    if found.get("running"):
        lines.append(f"running now: {', '.join(found['running'])}")
    if found.get("waiting_to_review"):
        lines.append(f"{found['waiting_to_review']} matches waiting for a decision")
    if found.get("searches_with_problems"):
        lines.append(f"{found['searches_with_problems']} searches will not run until fixed")
    return "\n".join(lines)


def deleted(gone: dict[str, Any]) -> str:
    """What a delete did, and just as importantly what it did not do."""
    lines = [f"{gone['name']} is no longer a saved search."]
    if gone.get("runs_kept"):
        lines.append(
            f"Its {gone['runs_kept']} runs and everything they found are still in the store, "
            "because recorded history is never deleted."
        )
    lines.append(f"The definition is kept at {gone['kept_at']}, so it can be brought back:")
    lines.append(f"  homescout searches restore {gone['name']}")
    return "\n".join(lines)


def passed(rows: Sequence[Any]) -> str:
    """What the person has said no to, which the results view keeps out of their way.

    Said plainly rather than as a table: this is a list somebody reads to check a decision, not one
    they work from.
    """
    if not rows:
        return "You have not passed on anything yet."
    lines = [f"{len(rows)} passed on, and hidden from results:"]
    for row in rows:
        where = ", ".join(part for part in (row.get("address"), row.get("city")) if part)
        cost = money(row.get("price"))
        because = f"  {row['verdict']}" if row.get("verdict") else ""
        lines.append(f"  {where or row['listing_id']}  {cost}{because}")
    lines.append("Un-pass one with: homescout annotate <id> --judgment none")
    return "\n".join(lines)
