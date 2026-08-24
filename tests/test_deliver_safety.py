"""What a listing site writes, arriving in an email as text.

Every value the email shows about a property was written by somebody else, and this is the first
place in the product that renders that text as markup for another program to display. Nothing here
executes on this machine and a mail client is not a browser, so the danger is quieter than it looks:
the one artifact this feature exists to make trustworthy is a message that says what changed, and a
message whose links are not the ones the tool put there is not that.

The ordinary case is the same code path. A house whose address contains an ampersand is a Tuesday.
"""

from __future__ import annotations

import re

from cli_fakes import FakeSource, row, search, workspace
from deliver_fakes import parts
from homescout import api, digest
from homescout.deliver import build
from homescout.deliver.message import attribute, link_target, render, text
from homescout.store import Store

HOSTILE = '<script>alert("x")</script>'


def document_for(store: Store, one_row):
    space = workspace(
        store, searches=[search("portales")], sources={"fake": FakeSource(rows=[one_row])}
    )
    outcome = api.run_search(space, "portales")
    return digest.build(
        [
            digest.entry(
                store,
                search_name="portales",
                comparison=outcome.comparison,
                outcome=outcome,
            )
        ],
        kind="run",
    )


def test_an_address_a_source_wrote_arrives_as_text(store: Store) -> None:
    """feat-012/AC-4: rendered, never obeyed."""
    doc = document_for(store, row("a", address_line=HOSTILE, city='Portales" onload="x'))

    found = parts(
        build(
            doc,
            sender="homescout@example.invalid",
            recipients=("me@example.invalid",),
            root=store.path.parent,
        )
    )

    assert "<script>" not in found["html"]
    assert "&lt;script&gt;" in found["html"], "it is shown, so a person can see what the site sent"
    assert 'onload="x' not in found["html"]
    assert re.search(r'alt="[^"]*&quot;', found["html"]), "and quoting holds inside an attribute"


def test_a_link_is_a_link_only_when_it_is_one(store: Store) -> None:
    """feat-012/AC-4: a `javascript:` URL is text, not something to tap on a phone."""
    doc = document_for(store, row("a", listing_url="javascript:alert(1)"))

    rendered = render(doc, root=store.path.parent)

    assert "javascript:" not in rendered.html.lower().replace("&#", "")
    assert "<a href=" not in rendered.html.split("HomeScout,")[0], "no link at all, rather than one"
    assert "javascript:" not in rendered.text, "and the plain part does not offer it either"


def test_the_schemes_that_are_allowed_and_the_ones_that_are_not() -> None:
    """feat-012/AC-4: parsed rather than pattern-matched.

    A check for a leading `http` passes `httpx://`, and a check for the absence of `javascript:`
    passes a value with a tab in the middle of the word, which some clients still honour.
    """
    for allowed in ("https://example.invalid/a", "http://example.invalid/a"):
        assert link_target(allowed) == allowed
    for refused in (
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "java\tscript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "file:///c:/windows/system32",
        "httpx://example.invalid",
        "https://",
        "",
        None,
        12,
    ):
        assert link_target(refused) is None, refused


def test_there_is_one_way_to_put_a_value_in_the_document() -> None:
    """feat-012/AC-4: which is the property that makes the escaping true rather than mostly true.

    The two names say where a value is going; they escape identically on purpose, so that moving a
    value from element text into an attribute during an ordinary edit cannot make it unsafe.
    """
    assert text("a & b") == "a &amp; b"
    assert text('say "hello"') == attribute('say "hello"') == "say &quot;hello&quot;"
    assert text("<b>") == "&lt;b&gt;"
    assert text(None) == "" and attribute(None) == ""


def test_an_ampersand_in_an_address_is_the_ordinary_case(store: Store) -> None:
    """feat-012/AC-4: the same rule that stops the hostile case stops the common one."""
    doc = document_for(store, row("a", address_line="Smith & Jones Road"))

    rendered = render(doc, root=store.path.parent)

    assert "Smith &amp; Jones Road" in rendered.html
    assert "Smith & Jones Road" in rendered.text, "and the plain part is plain"


def test_a_value_with_a_newline_does_not_forge_a_field_in_the_plain_part(store: Store) -> None:
    """feat-012/AC-4: the plain-text part carries no markup and still has a shape to abuse."""
    doc = document_for(store, row("a", address_line="A Road\n    Price: $1"))

    rendered = render(doc, root=store.path.parent)

    assert "Price: $1" in rendered.text, "it is shown"
    assert "\n    Price: $1" not in rendered.text, "but not on a line of its own"
