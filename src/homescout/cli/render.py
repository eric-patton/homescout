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
    return "\n".join(
        [
            f"name:    {search.name}",
            f"sources: {', '.join(search.sources) or DASH}",
            f"areas:   {len(search.areas)}",
        ]
    )


def problems(name: str, found: Sequence[Any]) -> str:
    if not found:
        return f"{name} is valid."
    lines = [f"{name} is not valid ({len(found)} problems):"]
    lines.extend(f"  {p.location}: {p.message}" for p in found)
    return "\n".join(lines)


def enrichment(outcome: Any) -> str:
    """What an enrichment pass did, for somebody watching it rather than parsing it."""
    lines = [f"{outcome.properties} properties"]
    if outcome.without_location:
        lines[0] += f", {outcome.without_location} with no location to look up"
    for found in outcome.providers:
        detail = f" ({found.detail})" if found.detail else ""
        lines.append(
            f"  {found.provider}: {found.outcome}, {found.looked_up} looked up, "
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
    if not pending:
        return "No matches are waiting for review."
    return table(
        ("id", "properties", "agreed", "conflicted"),
        [
            (m.id, len(m.listing_ids), ", ".join(m.agreed) or DASH, ", ".join(m.conflicted) or DASH)
            for m in pending
        ],
    )


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
