"""One digest, turned into an email worth opening on a phone.

Three things about this module look dated and are deliberate.

**The layout is tables.** Mail clients are not browsers. Flexbox and grid still fail in Outlook's
rendering engine, and several clients strip a `<style>` block entirely, so every rule here is
inline on the element it applies to and every column is a table cell. A single-column table capped
at 600 pixels renders correctly from a phone's default client to a webmail preview pane, which is
what the spec means by legible without horizontal scrolling.

**The pictures are attached, not linked.** Each one is this tool's own stored copy, carried in the
message as a related part and referenced by content id. That is why the picture appears whether or
not the listing site permits its images to be loaded from elsewhere, why it still appears for a
property that has since disappeared and taken its images with it, and why opening this email tells
nobody anything: there is no outbound reference in it at all.

**Every value from a listing site is escaped, and a link is only a link if it is one.** An address,
a city, a property type and a URL are all text somebody else wrote, and this is the first place in
the product that renders that text as markup. A house whose address contains an ampersand is a
Tuesday; a `listing_url` with a scheme other than http or https is not, and neither one gets to
decide what this message says.
"""

from __future__ import annotations

import html
import mimetypes
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

#: The widest the message ever gets. Wider than this and a phone client either scales the whole
#: message down until the text is unreadable or gives it a horizontal scrollbar.
MAX_WIDTH_PX = 600

#: The thumbnail's column. Small enough that the text beside it still has room on a 320 pixel
#: screen, which is the narrowest phone anybody still reads mail on.
IMAGE_WIDTH_PX = 120

#: Nothing in the message is smaller than this. A phone at its default text size renders 16px
#: comfortably and 14px legibly; below that people zoom, and zooming is horizontal scrolling.
BODY_PX = 16
SMALL_PX = 14

INK = "#1a1a1a"
QUIET = "#5a5a5a"
RULE = "#dddddd"
PAPER = "#ffffff"

#: Content ids are generated against a domain that does not exist, rather than against this
#: machine's. `make_msgid` defaults to the local hostname, and the machine's name is nobody's
#: business but its own.
CID_DOMAIN = "homescout.invalid"

#: The schemes a link may have. Everything else (`javascript:`, `data:`, `file:`) renders as text.
SAFE_SCHEMES = frozenset({"http", "https"})


def text(value: Any) -> str:
    """A value on its way into the document, escaped.

    Every interpolation in this module goes through this function or through `attribute`, and the
    two do exactly the same thing. That is deliberate. Quotes only need escaping inside an
    attribute, so the strictly correct version of this function would leave them alone in element
    text, and then a value moved from one position to the other during an ordinary edit would
    silently stop being safe. One behavior under two names costs nothing and cannot be got wrong.
    """
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def attribute(value: Any) -> str:
    """The same escaping, named for where it is going. See `text`."""
    return text(value)


def link_target(url: Any) -> str | None:
    """The URL if it is safe to make into a link, otherwise nothing.

    Parsed rather than pattern-matched: a check for a leading `http` passes
    `httpx://`, and a check for the absence of `javascript:` passes
    `java\tscript:`, which some clients still honour.
    """
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    if parsed.scheme.lower() not in SAFE_SCHEMES or not parsed.netloc:
        return None
    return url.strip()


def money(value: Any) -> str:
    if not isinstance(value, int | float):
        return ""
    return f"${int(value):,}"


def one_line(value: Any) -> str:
    """For the plain-text part, where a newline in a value would look like a new field."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def address_of(summary: Mapping[str, Any]) -> str:
    """A postal address from the parts a summary carries.

    Composed by the digest, so the email and the terminal say it the same way. That matters more
    than it sounds: two implementations of this is how `1828 Redwine Unit B Unit B` reaches an
    inbox, which is what the first real run over three sources printed.
    """
    from ..digest import address_of as compose

    return compose(summary) or "an address this listing did not give"


def facts(summary: Mapping[str, Any]) -> str:
    """Beds, baths, size and how long we have been watching, as one readable line."""
    parts: list[str] = []
    for key, unit in (("beds", "bd"), ("baths", "ba")):
        value = summary.get(key)
        if isinstance(value, int | float):
            shown = int(value) if float(value).is_integer() else value
            parts.append(f"{shown} {unit}")
    sqft = summary.get("sqft")
    if isinstance(sqft, int | float):
        parts.append(f"{int(sqft):,} sqft")
    days = summary.get("days_on_market")
    if isinstance(days, int):
        parts.append("listed today" if days == 0 else f"{days} days on market")
    return " · ".join(parts)


@dataclass(frozen=True, slots=True)
class Picture:
    """One stored preview, on its way into the message as a related part."""

    cid: str
    data: bytes
    subtype: str


@dataclass
class Rendered:
    """Both renderings of one digest, and the pictures the HTML one refers to."""

    subject: str
    html: str
    text: str
    pictures: list[Picture] = field(default_factory=list)


class _Pictures:
    """Loads a stored preview once per property and hands back a content id.

    A property with no stored image, or one whose file has gone, gets no content id and renders
    without a picture rather than being left out of the email. The spec's edge case says the entry
    still appears, and it is the right call: an image fetch that failed is not a reason to hide a
    price cut.
    """

    def __init__(self, root: Path | None) -> None:
        self._root = root
        self._by_listing: dict[str, str] = {}
        self.found: list[Picture] = []

    def cid_for(self, summary: Mapping[str, Any]) -> str | None:
        listing_id = str(summary.get("listing_id") or "")
        if listing_id in self._by_listing:
            return self._by_listing[listing_id]
        relative = summary.get("image")
        if self._root is None or not relative:
            return None
        path = self._root / str(relative)
        try:
            data = path.read_bytes()
        except OSError:
            return None
        if not data:
            return None
        guessed, _ = mimetypes.guess_type(path.name)
        subtype = guessed.split("/", 1)[1] if guessed and guessed.startswith("image/") else "jpeg"
        cid = make_msgid(domain=CID_DOMAIN)
        self.found.append(Picture(cid=cid, data=data, subtype=subtype))
        self._by_listing[listing_id] = cid
        return cid


def _direction(change: Mapping[str, Any]) -> str:
    """A price move in words.

    Words rather than a colour or an arrow alone, because the accessibility requirement says
    nothing is conveyed by colour alone and because a red triangle means nothing when images are
    off.
    """
    before, after = change.get("before"), change.get("after")
    amount = change.get("amount")
    way = change.get("direction") or ""
    shown = money(abs(amount)) if isinstance(amount, int | float) else ""
    move = f"{way} {shown}".strip() if shown else way
    both = f"{money(before)} to {money(after)}".strip()
    return f"{both} ({move})" if move else both


def _notes(summary: Mapping[str, Any]) -> list[str]:
    """The lines under an address that say why this property is in this email."""
    lines: list[str] = []
    change = summary.get("price_change")
    if isinstance(change, Mapping):
        lines.append(f"Price {_direction(change)}")
    status = summary.get("status_change")
    if isinstance(status, Mapping):
        lines.append(f"Status {status.get('before') or 'unknown'} to {status.get('after')}")
    for other in summary.get("fields") or ():
        if isinstance(other, Mapping):
            lines.append(
                f"{other.get('field')} {other.get('before')} to {other.get('after')}"
            )
    rules = summary.get("rules")
    if rules:
        lines.append("Matched " + ", ".join(str(rule) for rule in rules))
    return lines


# -- the HTML ---------------------------------------------------------------


def _card(summary: Mapping[str, Any], pictures: _Pictures) -> str:
    """One property: a picture if there is one, an address, a price, and why it is here."""
    where = address_of(summary)
    cid = pictures.cid_for(summary)
    target = link_target(summary.get("listing_url"))

    if cid is None:
        image = ""
    else:
        image = (
            f'<td width="{IMAGE_WIDTH_PX}" valign="top" '
            f'style="padding: 0 12px 0 0;">'
            f'<img src="cid:{attribute(cid.strip("<>"))}" width="{IMAGE_WIDTH_PX}" '
            f'alt="{attribute(where)}" '
            f'style="display: block; width: {IMAGE_WIDTH_PX}px; max-width: 100%; '
            f'height: auto; border-radius: 4px;"></td>'
        )

    heading = text(where)
    if target is not None:
        heading = (
            f'<a href="{attribute(target)}" '
            f'style="color: {INK}; text-decoration: underline;">{text(where)}</a>'
        )

    price = money(summary.get("price"))
    detail = facts(summary)
    notes = "".join(
        f'<div style="font-size: {SMALL_PX}px; color: {QUIET}; padding-top: 2px;">'
        f"{text(note)}</div>"
        for note in _notes(summary)
    )

    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="width: 100%; border-collapse: collapse; border-top: 1px solid {RULE};">'
        f'<tr><td style="padding: 12px 0;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="width: 100%; border-collapse: collapse;"><tr>'
        f"{image}"
        f'<td valign="top" style="font-size: {BODY_PX}px; color: {INK}; line-height: 1.4;">'
        f'<div style="font-weight: bold;">{heading}</div>'
        f'<div style="padding-top: 2px;">{text(price)}</div>'
        f'<div style="font-size: {SMALL_PX}px; color: {QUIET}; padding-top: 2px;">'
        f"{text(detail)}</div>"
        f"{notes}"
        f"</td></tr></table></td></tr></table>"
    )


def _section(
    title: str, rows: Sequence[Mapping[str, Any]], pictures: _Pictures, *, more: int = 0
) -> str:
    if not rows and not more:
        return ""
    cards = "".join(_card(row, pictures) for row in rows)
    tail = ""
    if more:
        tail = (
            f'<div style="font-size: {SMALL_PX}px; color: {QUIET}; padding: 8px 0 0 0;">'
            f"and {more} more, in the digest file and the results table.</div>"
        )
    return (
        f'<h2 style="font-size: {BODY_PX}px; color: {INK}; margin: 20px 0 0 0;">'
        f"{text(title)}</h2>{cards}{tail}"
    )


def _trouble(entry: Mapping[str, Any]) -> str:
    """The sources that did not answer, named, with what happened to each."""
    bad = [
        source
        for source in entry.get("sources") or ()
        if isinstance(source, Mapping) and source.get("outcome") not in (None, "ok")
    ]
    if not bad:
        return ""
    lines = "".join(
        f"<li>{text(source.get('source'))}: {text(source.get('outcome'))}"
        + (f" ({text(source.get('detail'))})" if source.get("detail") else "")
        + "</li>"
        for source in bad
    )
    return (
        f'<div style="font-size: {SMALL_PX}px; color: {INK}; background: #f4f4f4; '
        f'padding: 10px 12px; margin: 12px 0; border-left: 3px solid {QUIET};">'
        f"<strong>This run was degraded.</strong> Some properties may be missing from it."
        f'<ul style="margin: 6px 0 0 0; padding-left: 18px;">{lines}</ul></div>'
    )


def _counts_line(entry: Mapping[str, Any]) -> str:
    counts = entry.get("counts") or {}
    parts = [f"{counts.get('matched', 0)} matched"]
    for key, word in (
        ("new", "new"),
        ("changed", "changed"),
        ("gone", "gone"),
        ("returned", "returned"),
        ("flagged", "newly flagged"),
    ):
        value = counts.get(key) or 0
        if value:
            parts.append(f"{value} {word}")
    return ", ".join(parts)


def badges(entry: Mapping[str, Any]) -> dict[str, list[str]]:
    """Which criteria fired on which property, so any row can carry its own.

    The digest keeps newly flagged properties in their own list, which is right for a document. In
    an email it is not enough on its own: a new property that is also in a flood zone should say so
    on the row where somebody first sees it, rather than only further down under its own heading.
    """
    found: dict[str, list[str]] = {}
    for row in entry.get("flagged") or ():
        if isinstance(row, Mapping) and row.get("listing_id") and row.get("rules"):
            found[str(row["listing_id"])] = [str(rule) for rule in row["rules"]]
    return found


def _badged(
    rows: Sequence[Mapping[str, Any]], marks: Mapping[str, list[str]]
) -> list[Mapping[str, Any]]:
    return [
        row if row.get("rules") or str(row.get("listing_id")) not in marks
        else {**row, "rules": marks[str(row["listing_id"])]}
        for row in rows
    ]


def _sections_of(entry: Mapping[str, Any], max_new: int) -> tuple[list[tuple[str, list]], int]:
    """The email's sections in order, with each property appearing exactly once.

    Two rules, and the second one is why this is a function rather than a list literal.

    The new list is capped and the rest become a count. Everything else is never capped: a night
    with thirty price cuts is the news, and hiding it would hide the news.

    A property that is both new and newly flagged is shown once, on the row where it is first seen,
    carrying its criteria there. Reaching the bottom of a short email and finding the same house
    again under a second heading reads as a bug, and the criteria are already on the first row.
    """
    marks = badges(entry)
    new = _badged(list(entry.get("new") or ()), marks)
    shown, more = new[:max_new], max(0, len(new) - max_new)

    ordered: list[tuple[str, list]] = [("New", list(shown))]
    for title, key in (
        ("Price changes", "price_changes"),
        ("Status changes", "status_changes"),
        ("Other changes", "other_changes"),
        ("Gone", "gone"),
        ("Back on the market", "returned"),
        ("Newly flagged", "flagged"),
    ):
        ordered.append((title, _badged(list(entry.get(key) or ()), marks)))

    already: set[str] = set()
    deduplicated: list[tuple[str, list]] = []
    for title, rows in ordered:
        keep = [row for row in rows if str(row.get("listing_id") or id(row)) not in already]
        already.update(str(row.get("listing_id")) for row in keep if row.get("listing_id"))
        deduplicated.append((title, keep))
    return deduplicated, more


def _entry_html(entry: Mapping[str, Any], pictures: _Pictures, max_new: int) -> str:
    ordered, more = _sections_of(entry, max_new)
    sections = [
        _section(title, rows, pictures, more=more if title == "New" else 0)
        for title, rows in ordered
    ]
    return (
        f'<h1 style="font-size: 20px; color: {INK}; margin: 24px 0 4px 0;">'
        f"{text(entry.get('name'))}</h1>"
        f'<div style="font-size: {SMALL_PX}px; color: {QUIET};">{text(_counts_line(entry))}</div>'
        f"{_trouble(entry)}"
        f"{''.join(sections)}"
    )


def _skipped_html(skipped: Sequence[Mapping[str, Any]]) -> str:
    if not skipped:
        return ""
    lines = "".join(
        f"<li>{text(one.get('name'))}: {text(one.get('reason'))}"
        + (f" ({text(one.get('detail'))})" if one.get("detail") else "")
        + "</li>"
        for one in skipped
    )
    return (
        f'<div style="font-size: {SMALL_PX}px; color: {INK}; background: #f4f4f4; '
        f'padding: 10px 12px; margin: 16px 0; border-left: 3px solid {QUIET};">'
        f"<strong>Not run.</strong>"
        f'<ul style="margin: 6px 0 0 0; padding-left: 18px;">{lines}</ul></div>'
    )


# -- the plain text ---------------------------------------------------------


def _text_card(summary: Mapping[str, Any]) -> list[str]:
    lines = [f"  {one_line(address_of(summary))}"]
    detail = " · ".join(part for part in (money(summary.get("price")), facts(summary)) if part)
    if detail:
        lines.append(f"    {one_line(detail)}")
    lines.extend(f"    {one_line(note)}" for note in _notes(summary))
    target = link_target(summary.get("listing_url"))
    if target:
        lines.append(f"    {one_line(target)}")
    return lines


def _entry_text(entry: Mapping[str, Any], max_new: int) -> list[str]:
    ordered, more = _sections_of(entry, max_new)
    lines = [str(entry.get("name") or ""), _counts_line(entry), ""]

    bad = [
        source
        for source in entry.get("sources") or ()
        if isinstance(source, Mapping) and source.get("outcome") not in (None, "ok")
    ]
    if bad:
        lines.append("This run was degraded. Some properties may be missing from it.")
        lines.extend(
            f"  {one_line(source.get('source'))}: {one_line(source.get('outcome'))}"
            for source in bad
        )
        lines.append("")

    for title, rows in ordered:
        if not rows:
            continue
        lines.append(f"{title}:")
        for row in rows:
            lines.extend(_text_card(row))
        if title == "New" and more:
            lines.append(f"  and {more} more, in the digest file and the results table.")
        lines.append("")
    return lines


# -- counting, and the subject ----------------------------------------------

#: What a digest can have something to say about. Newly flagged is in here because the spec puts it
#: there, and it is the interesting one: a property that has not changed at all can still become
#: worth looking at because a criterion started matching it, which is what happens the night after
#: enrichment fills in a flood zone.
MOVED_KEYS: tuple[str, ...] = (
    "new",
    "price_changes",
    "status_changes",
    "other_changes",
    "gone",
    "returned",
    "flagged",
)


def moved(document: Mapping[str, Any]) -> int:
    """How many properties this digest has something to say about.

    Zero is what silence is computed from. Deliberately not counted here: a source that failed. A
    degraded run with nothing to report sends no email, because the spec's own edge case says so
    and because the degradation is in the digest and the exit code, where the scheduled agent that
    cares about it is already looking. Nobody needs waking because a source timed out.
    """
    total = 0
    for entry in document.get("searches") or ():
        if isinstance(entry, Mapping):
            total += sum(len(entry.get(key) or ()) for key in MOVED_KEYS)
    return total


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def subject(document: Mapping[str, Any]) -> str:
    """What the email says before it is opened.

    Counts, not adjectives. The reader is deciding on a phone whether this is worth the next thirty
    seconds, and "3 new, 1 price change" answers that where "HomeScout digest" does not.
    """
    entries = [e for e in (document.get("searches") or ()) if isinstance(e, Mapping)]
    tally: dict[str, int] = dict.fromkeys(MOVED_KEYS, 0)
    for entry in entries:
        for key in MOVED_KEYS:
            tally[key] += len(entry.get(key) or ())

    changed = tally["price_changes"] + tally["status_changes"] + tally["other_changes"]
    parts: list[str] = []
    if tally["new"]:
        parts.append(_plural(tally["new"], "new"))
    if changed:
        parts.append(_plural(changed, "change"))
    if tally["gone"]:
        parts.append(f"{tally['gone']} gone")
    if tally["returned"]:
        parts.append(f"{tally['returned']} back")
    if tally["flagged"]:
        parts.append(f"{tally['flagged']} flagged")

    where = entries[0].get("name") if len(entries) == 1 else f"{len(entries)} searches"
    headline = ", ".join(parts) if parts else "nothing new"
    degraded = any(
        source.get("outcome") not in (None, "ok")
        for entry in entries
        for source in entry.get("sources") or ()
        if isinstance(source, Mapping)
    ) or bool(document.get("skipped"))
    tail = " (degraded)" if degraded else ""
    return f"HomeScout {where}: {headline}{tail}"


# -- putting it together ----------------------------------------------------


def render(
    document: Mapping[str, Any], *, root: Path | None = None, max_new: int = 25
) -> Rendered:
    """One digest as a subject, an HTML body, a plain-text body, and its pictures."""
    pictures = _Pictures(root)
    entries = [e for e in (document.get("searches") or ()) if isinstance(e, Mapping)]
    skipped = [s for s in (document.get("skipped") or ()) if isinstance(s, Mapping)]

    body = "".join(_entry_html(entry, pictures, max_new) for entry in entries)
    when = ((document.get("homescout") or {}).get("generated_at")) if document else None
    document_html = (
        f'<div style="margin: 0; padding: 0; background: {PAPER};">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="width: 100%; border-collapse: collapse; background: {PAPER};"><tr>'
        f'<td align="left" style="padding: 16px;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'style="max-width: {MAX_WIDTH_PX}px; width: 100%; border-collapse: collapse; '
        f'font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;">'
        f'<tr><td style="font-size: {BODY_PX}px; color: {INK};">'
        f"{_skipped_html(skipped)}{body}"
        f'<div style="font-size: {SMALL_PX}px; color: {QUIET}; padding-top: 24px; '
        f'border-top: 1px solid {RULE}; margin-top: 24px;">'
        f"HomeScout, {text(when)}. This message was sent because a run found something to say."
        f"</div>"
        f"</td></tr></table></td></tr></table></div>"
    )

    lines: list[str] = []
    if skipped:
        lines.append("Not run:")
        lines.extend(
            f"  {one_line(one.get('name'))}: {one_line(one.get('reason'))}" for one in skipped
        )
        lines.append("")
    for entry in entries:
        lines.extend(_entry_text(entry, max_new))
    lines.append(f"HomeScout, {one_line(when)}.")

    return Rendered(
        subject=subject(document),
        html=document_html,
        text="\n".join(lines),
        pictures=pictures.found,
    )


def build(
    document: Mapping[str, Any],
    *,
    sender: str,
    recipients: Iterable[str],
    root: Path | None = None,
    max_new: int = 25,
) -> EmailMessage:
    """The message, ready to hand to a server.

    `multipart/alternative` holding the plain text and an HTML part, with the pictures related to
    the HTML one. A client that shows plain text gets a summary that reads properly on its own,
    rather than the usual apology about needing an HTML client.
    """
    rendered = render(document, root=root, max_new=max_new)

    message = EmailMessage()
    message["Subject"] = rendered.subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(rendered.text)
    message.add_alternative(rendered.html, subtype="html")

    part = message.get_payload()[-1]
    for picture in rendered.pictures:
        part.add_related(
            picture.data, maintype="image", subtype=picture.subtype, cid=picture.cid
        )
    return message
