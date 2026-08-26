"""The email: what it says, how it is put together, and what it never contains.

Every document here comes out of a real run through the real digest builder, and every assertion is
made against the parsed MIME rather than against a string of HTML. A test that greps the source for
`<img` would pass on a message no mail client could render.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cli_fakes import FakeSource, row, search, workspace
from deliver_fakes import PASSWORD, parts
from homescout import api, digest
from homescout.deliver import build, moved, render, subject
from homescout.deliver.message import BODY_PX, MAX_WIDTH_PX, SMALL_PX
from homescout.store import Store


def run(store: Store, *, rows, name="portales", images=True, outcome="ok", detail=None):
    space = workspace(
        store,
        searches=[search(name)],
        sources={"fake": FakeSource(rows=rows, images=images, outcome=outcome, detail=detail)},
    )
    return api.run_search(space, name)


def document(store: Store, *outcomes, kind="run"):
    return digest.build(
        [
            digest.entry(
                store,
                search_name=o.run.search_name,
                comparison=o.comparison,
                outcome=o,
            )
            for o in outcomes
        ],
        kind=kind,
    )


@pytest.fixture
def a_night(store: Store):
    """One night's worth of news: a new property, a price cut, and one that disappeared."""
    run(store, rows=[row("a", price=400_000), row("b", price=250_000)])
    second = run(store, rows=[row("a", price=388_000)])
    return document(store, second), store


def message_of(store: Store, doc, **kwargs):
    return build(
        doc,
        sender="homescout@example.invalid",
        recipients=("me@example.invalid",),
        root=store.path.parent,
        **kwargs,
    )


def test_an_email_lists_each_property_with_its_picture_price_address_and_link(a_night) -> None:
    """feat-012/AC-4: everything needed to decide whether to open anything, in one row each."""
    doc, store = a_night

    found = parts(message_of(store, doc))

    assert "Example Road" in found["html"], "the address"
    assert "$388,000" in found["html"], "the price"
    assert "https://example.invalid/a" in found["html"], "the link"
    assert found["images"], "the picture"
    assert "Example Road" in found["text"], "and the plain-text part says the same things"
    assert "$388,000" in found["text"]


def test_every_picture_in_the_email_is_the_tool_s_own_copy(a_night) -> None:
    """feat-012/AC-6: attached, not referenced, so it renders whatever a source permits.

    It also means opening this email tells nobody anything: there is no outbound reference in it.
    """
    doc, store = a_night

    found = parts(message_of(store, doc))
    referenced = set(re.findall(r'src="cid:([^"]+)"', found["html"]))

    assert referenced, "the message refers to at least one attached picture"
    assert referenced <= set(found["cids"]), "every reference resolves to an attached part"
    for cid in referenced:
        assert found["cids"][cid] == b"fake-image-bytes", "the bytes on disk, not a URL"
    assert "http://example.invalid" not in found["html"].replace("https://", "")
    assert not re.findall(r'<img[^>]+src="https?://', found["html"]), "nothing is hotlinked"


def test_every_picture_carries_the_address_as_its_alternative_text(a_night) -> None:
    """feat-012/AC-5: an email read with images off still says which property each row is."""
    doc, store = a_night

    html = parts(message_of(store, doc))["html"]

    images = re.findall(r"<img[^>]*>", html)
    assert images
    for tag in images:
        alt = re.search(r'alt="([^"]*)"', tag)
        assert alt is not None and alt.group(1).strip(), tag


def test_a_price_change_says_where_it_was_where_it_is_and_which_way(a_night) -> None:
    """feat-012/AC-7: in words, because nothing may be conveyed by colour alone."""
    doc, store = a_night

    found = parts(message_of(store, doc))

    assert "$400,000 to $388,000" in found["html"]
    assert "down" in found["html"]
    assert "$400,000 to $388,000" in found["text"]


def test_disappearances_and_returns_are_their_own_sections(store: Store) -> None:
    """feat-012/AC-7: reported separately from new properties, because they mean the opposite."""
    run(store, rows=[row("a"), row("b")])
    gone = run(store, rows=[row("a")])
    back = run(store, rows=[row("a"), row("b")])

    away = parts(message_of(store, document(store, gone)))
    again = parts(message_of(store, document(store, back)))

    assert "Gone" in away["html"] and "Gone" in away["text"]
    assert "Back on the market" in again["html"]
    assert "New" not in again["text"].split("Back on the market")[0].split("\n")[-2:][0]


def test_a_degraded_run_names_every_source_that_failed(store: Store) -> None:
    """feat-012/AC-8: in the email as well as the digest, because a short list of results.

    A run with a source down looks exactly like a quiet market unless it says so.
    """
    outcome = run(store, rows=[row("a")], outcome="failed", detail="the service is down")

    found = parts(message_of(store, document(store, outcome)))

    assert "degraded" in found["html"].lower()
    assert "fake" in found["html"] and "failed" in found["html"]
    assert "the service is down" in found["html"]
    assert "fake" in found["text"] and "failed" in found["text"]


def test_a_property_with_no_stored_picture_still_appears(store: Store) -> None:
    """feat-012/AC-4, and the spec's edge case: a failed image fetch hides nothing.

    An image that could not be retrieved is not a reason to leave a price cut out of the email.
    """
    outcome = run(store, rows=[row("a"), row("b")], images=False)

    found = parts(message_of(store, document(store, outcome)))

    assert found["images"] == []
    assert "a Example Road" in found["html"]
    assert "b Example Road" in found["html"]


def test_the_new_list_is_capped_and_says_how_many_more_there_are(store: Store) -> None:
    """feat-012/AC-4, and the first-run edge case: the first ever run is everything at once.

    Capped rather than truncated: the remainder is a count, and the count says where the rest is.
    Nothing is silently dropped, which is what a cap becomes if nobody watches it.
    """
    outcome = run(store, rows=[row(f"p{i:03d}") for i in range(40)])

    found = parts(message_of(store, document(store, outcome), max_new=25))

    assert found["text"].count("Example Road") == 25, "one line per property in the plain part"
    assert len(re.findall(r"<img[^>]*>", found["html"])) == 25
    assert "and 15 more" in found["html"]
    assert "and 15 more" in found["text"]
    assert "digest file" in found["html"], "and where to find them"


def test_a_change_is_never_capped(store: Store) -> None:
    """feat-012/AC-7: a night with thirty price cuts is news, and hiding it would hide the news."""
    run(store, rows=[row(f"p{i:02d}", price=400_000) for i in range(30)])
    second = run(store, rows=[row(f"p{i:02d}", price=380_000) for i in range(30)])

    found = parts(message_of(store, document(store, second), max_new=2))

    assert found["html"].count("$400,000 to $380,000") == 30


def test_the_message_is_one_column_and_fits_a_phone(a_night) -> None:
    """feat-012/AC-5: checked as the four things that decide it, since legibility is a judgment.

    A single column, nothing wider than the cap, no fixed width larger than a narrow phone, and no
    text below fourteen pixels. Whether it is *legible* is a human call nobody has made yet, and
    saying so here is the point of writing the check out.
    """
    doc, store = a_night

    html = parts(message_of(store, doc))["html"]

    assert f"max-width: {MAX_WIDTH_PX}px" in html
    widths = [int(found) for found in re.findall(r"(?<!max-)width: (\d+)px", html)]
    assert all(width <= 320 for width in widths), f"something is wider than a phone: {widths}"
    sizes = [int(found) for found in re.findall(r"font-size: (\d+)px", html)]
    assert sizes and min(sizes) >= SMALL_PX
    assert BODY_PX in sizes, "the body text is the comfortable size, not the small one"
    assert "display: flex" not in html and "<style" not in html, (
        "mail clients are not browsers: flexbox fails and a style block is often stripped"
    )


def test_the_message_carries_a_plain_text_alternative(a_night) -> None:
    """feat-012/AC-5: readable in its own right, not an apology about needing HTML."""
    doc, store = a_night

    message = message_of(store, doc)
    found = parts(message)

    assert message.get_content_type() == "multipart/alternative"
    assert len(found["text"].splitlines()) > 3
    assert "<" not in found["text"], "it is text, not markup with the tags left in"


def test_nothing_in_the_message_is_a_credential_or_a_local_path(a_night, monkeypatch) -> None:
    """feat-012 security NFR: generated from stored data, and never from this machine's shape.

    Asserted rather than reasoned about, because it is true today by construction and construction
    changes. The failure this catches is somebody adding an error message about a file that could
    not be read.
    """
    doc, store = a_night
    monkeypatch.setenv("HOMESCOUT_SMTP_PASSWORD", PASSWORD)

    message = message_of(store, doc)
    whole = message.as_string()

    assert PASSWORD not in whole
    assert str(store.path) not in whole
    assert str(store.path.parent) not in whole
    assert str(store.images_dir) not in whole


def test_the_subject_says_what_happened_before_it_is_opened(a_night) -> None:
    """feat-012/AC-4: counts, not adjectives.

    The reader is deciding on a phone whether this is worth the next thirty seconds.
    """
    doc, _ = a_night

    assert subject(doc) == "HomeScout portales: 1 change, 1 gone"


def test_a_degraded_run_says_so_in_the_subject(store: Store) -> None:
    """feat-012/AC-8: before it is opened, because it changes how the contents should be read."""
    outcome = run(store, rows=[row("a")], outcome="failed")

    assert subject(document(store, outcome)).endswith("(degraded)")


def test_what_counts_as_something_to_say(store: Store) -> None:
    """feat-012/AC-3: the number silence is computed from."""
    first = run(store, rows=[row("a")])
    again = run(store, rows=[row("a")])

    assert moved(document(store, first)) == 1
    assert moved(document(store, again)) == 0
    assert moved({"searches": []}) == 0


def test_a_run_over_a_county_makes_an_email_a_person_can_open(store: Store) -> None:
    """feat-012/AC-5: the size of the message is a function of what moved, not of what matched."""
    rows = [row(f"p{i:04d}") for i in range(1_500)]
    run(store, rows=rows)
    second = run(store, rows=rows)

    message = message_of(store, document(store, second))

    assert len(message.as_bytes()) < 20_000, "a quiet night is a small message"


def test_the_root_is_optional_so_a_document_can_be_rendered_without_a_store(a_night) -> None:
    """feat-012/AC-4: the renderer is about a document, not about a database."""
    doc, _ = a_night

    rendered = render(doc, root=None)

    assert rendered.pictures == []
    assert "Example Road" in rendered.html


def test_a_missing_image_file_costs_the_picture_and_nothing_else(a_night) -> None:
    """feat-012/AC-6: an image the store knows about but disk does not is not an error."""
    doc, store = a_night
    for path in Path(store.images_dir).rglob("*"):
        if path.is_file():
            path.unlink()

    found = parts(message_of(store, doc))

    assert found["images"] == []
    assert "Example Road" in found["html"]


def test_a_new_property_carries_its_criteria_on_its_own_row(store: Store) -> None:
    """feat-012/AC-4: notable flags belong where somebody first sees the property.

    The digest keeps newly flagged properties in a list of their own, which is right for a document
    an agent parses. In an email it is not enough: a new property that is also in a flood zone
    should say so on its own row, not only further down under a second heading.
    """
    outcome = run(store, rows=[row("a")])
    doc = document(store, outcome)
    entry = doc["searches"][0]
    listing_id = entry["new"][0]["listing_id"]
    entry["flagged"] = [{**entry["new"][0], "rules": ["in-the-floodplain"]}]
    entry["counts"]["flagged"] = 1

    found = parts(message_of(store, doc))

    assert listing_id
    assert "in-the-floodplain" in found["html"], "the criterion is named"
    assert "in-the-floodplain" in found["text"]
    # Once, on the row where the property is first seen. Reaching the bottom of a short email and
    # finding the same house again under a second heading reads as a bug.
    assert found["text"].count("Example Road") == 1
    assert "Newly flagged" not in found["text"]
    assert found["text"].index("in-the-floodplain") > found["text"].index("New:")


def test_a_unit_already_written_into_the_address_is_not_repeated(store: Store) -> None:
    """feat-012/AC-4: found by reading the output of the first real run over three sources.

    Both Realtor.com and Zillow write the unit into the address line *and* into their own unit
    field, faithfully recorded by both adapters. Appending it unconditionally produced
    `1828 Redwine Unit B Unit B` and `1839 S Roosevelt Rd S #7 # 7` in a real digest.
    """
    from homescout.digest import address_of

    assert address_of({"address_line": "1828 Redwine Unit B", "unit": "Unit B"}) == (
        "1828 Redwine Unit B"
    )
    assert address_of({"address_line": "1839 S Roosevelt Rd S #7", "unit": "# 7"}) == (
        "1839 S Roosevelt Rd S #7"
    )
    assert address_of({"address_line": "Bigler Addition Block 2 Lot 3", "unit": "Lot 3"}) == (
        "Bigler Addition Block 2 Lot 3"
    )
    # And a unit that genuinely is not there is still added. The digit 2 lives inside 425, which is
    # why this comparison looks at the end of the line rather than anywhere in it.
    assert address_of({"address_line": "425 Monticello Pkwy", "unit": "2"}) == (
        "425 Monticello Pkwy 2"
    )


def test_both_surfaces_write_an_address_the_same_way(store: Store) -> None:
    """feat-012/AC-4: one implementation, because two is how the doubling got in.

    The terminal and the email are thin wrappers over one core (non-negotiable 8), and an address
    is exactly the sort of small rendering decision that quietly forks between them.
    """
    from homescout.cli import render
    from homescout.deliver.message import address_of as in_email
    from homescout.digest import address_of

    summary = {
        "address_line": "1828 Redwine Unit B",
        "unit": "Unit B",
        "city": "Portales",
        "state": "NM",
    }

    assert render.address(summary) == in_email(summary) == address_of(summary)
    assert render.address({}) == "(no address)", "each still has its own word for nothing"
    assert in_email({}) == "an address this listing did not give"


def test_a_busy_night_still_sends_and_still_says_everything(store: Store) -> None:
    """feat-012/AC-3: the email is sent when something moved, including when a lot moved.

    Found the first time delivery was tried against a real statewide search. The new list is
    capped and everything else deliberately is not, because a night with thirty price cuts is the
    news. But a picture was attached per row, so a night with hundreds of moved properties built a
    message with 501 attachments and Google refused the whole thing at 500. The entire email was
    lost, on exactly the night with the most to say, and the only warning was a line in a log.

    So the pictures are capped and the news is not. Everything still appears; the rows past the
    budget appear without a thumbnail, which is a state the message already renders for a property
    whose stored image cannot be read.
    """
    from homescout.deliver.message import MAX_PICTURES

    # A fixed number, deliberately not derived from the cap: a fixture sized by the constant grows
    # when the constant does, and then the assertions below hold no matter how high it goes.
    many = [row(str(n), price=300_000 + n) for n in range(100)]
    run(store, rows=many)
    second = run(store, rows=[replace_price(r) for r in many])

    found = parts(message_of(store, document(store, second)))

    assert len(found["cids"]) <= MAX_PICTURES, "the declared bound"
    assert len(found["cids"]) < len(many), (
        "and actually bounded: without a cap this is one attachment per property, which is how a "
        "real night reached 501 and Google refused the message whole"
    )
    assert len(found["cids"]) < 500, "under the limit of the provider that refused it"
    assert found["cids"], "but not thrown away entirely"

    # Every property is still in the email. The cap costs thumbnails, never news.
    for r in many:
        assert r.fields.address_line in found["html"], r.fields.address_line
        assert r.fields.address_line in found["text"], r.fields.address_line


def replace_price(source_row):
    """The same property, cheaper, so that every one of them counts as a price change."""
    from dataclasses import replace

    return replace(source_row, fields=replace(source_row.fields, price=source_row.fields.price - 5))
