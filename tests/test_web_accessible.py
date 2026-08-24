"""Keyboard operation and nothing conveyed by colour alone.

Two requirements, and neither is satisfied by good intentions. The first is checked in a browser
where it matters most (in `test_web_browser.py`, the inline edit driven by keys alone) and here in
the source, because an element that is a `div` with a click handler is unreachable by keyboard no
matter how careful the rest is. The second is checked by reading the stylesheet and the scripts: any
state that has a colour must also have a word.
"""

from __future__ import annotations

import re

from web_fakes import STATIC

SCRIPTS = sorted(STATIC.glob("*.js"))
PAGES = sorted(STATIC.glob("*.html"))
CSS = (STATIC / "app.css").read_text(encoding="utf-8")


def source(script) -> str:
    return script.read_text(encoding="utf-8")


def test_nothing_clickable_is_an_element_a_keyboard_cannot_reach() -> None:
    """A div with a click handler is unreachable by keyboard however careful everything else is."""
    for script in SCRIPTS:
        text = source(script)
        for match in re.finditer(r'el\("(\w+)",\s*\{([^}]*onclick[^}]*)\}', text, re.S):
            tag, attributes = match.group(1), match.group(2)
            reachable = tag in ("button", "a", "input", "select", "textarea", "th", "td")
            has_tabindex = "tabindex" in attributes
            assert reachable or has_tabindex, (
                f"{script.name} puts a click handler on a <{tag}> that nothing can tab to"
            )


def test_every_page_has_a_skip_link_and_a_focusable_main() -> None:
    for page in PAGES:
        text = page.read_text(encoding="utf-8")
        assert 'id="main"' in text, page.name
        assert 'tabindex="-1"' in text, f"{page.name}: main cannot be focused after a skip"
    assert "skipLink()" in source(STATIC / "common.js")
    assert ".skip" in CSS and ".skip:focus" in CSS


def test_the_focus_style_is_not_a_colour_change_alone() -> None:
    """Because a colour change is invisible to the person the requirement is about."""
    focus = re.search(r":focus-visible\s*\{([^}]*)\}", CSS)
    assert focus is not None, "there is no focus style at all"
    assert "outline" in focus.group(1)


def test_the_table_is_a_grid_a_keyboard_can_walk() -> None:
    """AC-17's hard case: roving focus, with the windowed rendering keeping the cell present."""
    results = source(STATIC / "results.js")
    for key in ("ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End",
                "PageDown", "PageUp", "Enter", "Escape"):
        assert key in results, f"the table does not answer {key}"
    assert 'role: "grid"' in results
    assert 'role: "gridcell"' in results
    assert '"aria-selected"' in results
    assert "focusCell" in results


def test_a_sortable_header_can_be_sorted_from_the_keyboard() -> None:
    results = source(STATIC / "results.js")
    header = results[results.index("function headerRow"):results.index("function sortBy")]
    assert "onkeydown" in header, "a header can be clicked and not pressed"
    assert '"aria-sort"' in header


def test_every_state_with_a_colour_also_has_a_word() -> None:
    """AC-18. The colour is a second signal, never the signal."""
    common = source(STATIC / "common.js")
    # The three value states each render text.
    assert '"not known"' in common
    assert '"none"' in common
    assert '"yes"' in common and '"no"' in common
    # A badge is built from its text, so there is no way to have one without.
    badge = common[common.index("function badge"):]
    assert "badge-" in badge and "text" in badge


def test_a_row_that_failed_to_save_says_so_in_words() -> None:
    """AC-6 and AC-18 together: the row is not merely a different colour."""
    results = source(STATIC / "results.js")
    assert "unsaved" in results
    assert "not saved" in results
    assert "rowstate problem" in results
    # And the colour is there as well, as the second signal rather than the only one.
    assert "td.unsaved" in CSS


def test_a_property_that_disappeared_is_marked_in_text() -> None:
    """AC-18 and AC-20: a row nobody can see the colour of still reads as gone."""
    assert 'content: "gone · "' in CSS
    assert "disappeared" in source(STATIC / "results.js")


def attributes_after(text: str, at: int) -> str:
    """The `{...}` starting at `at`, counting braces.

    Not `[^}]*`: an accessible name is often built from a template literal, `${label}, minimum`,
    and a non-counting match stops inside it and reports the label it just read as missing.
    """
    depth = 0
    for index in range(at, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[at : index + 1]
    return text[at:]


def test_every_input_carries_a_label_or_an_accessible_name() -> None:
    for script in SCRIPTS:
        text = source(script)
        for match in re.finditer(r'el\("(input|select|textarea)",\s*(\{)', text, re.S):
            attributes = attributes_after(text, match.start(2))
            named = (
                "aria-label" in attributes
                or ("id:" in attributes and f'for: "{_id_of(attributes)}"' in text)
                or 'type: "checkbox"' in attributes
            )
            assert named, f"{script.name} has an unlabelled {match.group(1)}"


def _id_of(attributes: str) -> str:
    found = re.search(r'id:\s*"([^"]+)"', attributes)
    return found.group(1) if found else ""


def test_the_merge_decisions_are_buttons_with_real_words() -> None:
    """AC-17: not icons, and in the tab order because they are buttons."""
    matches = source(STATIC / "matches.js")
    assert 'el("button"' in matches
    assert "One property: merge them" in matches
    assert "Two properties: keep both" in matches


def test_a_run_in_progress_is_announced_rather_than_only_shown() -> None:
    searches = source(STATIC / "searches.js")
    assert 'role: "log"' in searches
    assert '"aria-live": "polite"' in searches
    assert 'role: "status"' in source(STATIC / "common.js")
