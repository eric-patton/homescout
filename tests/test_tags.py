"""Words the household makes up, and what has to be true of them.

Keeping and passing are the tool's own three states, about one question: is this house still in.
Everything else somebody wants to say about a house is their own vocabulary, and this is where it
lives. The rules worth pinning are not the storing, which is a table with two columns; they are the
four places a tag store quietly stops being useful: a second spelling of the same word, a rename
that loses the properties, a merged property showing half its tags, and a tag with a comma in it
that reads as two everywhere it is printed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli_fakes import invoke
from homescout import api
from homescout.errors import InvalidInput
from homescout.store import Store
from web_fakes import client, held_workspace, listing, load, ours, reading, shared_store


def test_a_tag_typed_a_second_way_is_the_same_tag(store: Store) -> None:
    """feat-001/AC-28: two spellings of one word is two piles of houses that should be one.

    Nobody keeps a tag list in their head with its capitalisation. Somebody types "barn" on
    Tuesday and "Barn" on Friday and means the same thing both times, and a store that disagrees
    hands them two half-answers and no way to see that is what happened.

    The casing they typed first is what is kept, because it is the one they chose.
    """
    made = load(store, [listing("a"), listing("b")])

    store.create_tag("Barn")
    store.set_tags(made["a"], ["barn"])
    store.set_tags(made["b"], ["BARN"])

    assert [tag.name for tag in store.tags()] == ["Barn"], "one word became several"
    assert store.tags()[0].used == 2
    assert store.tags_for(made["a"]) == ("Barn",), "the first spelling is not what was kept"
    assert store.tags_for(made["b"]) == ("Barn",)


def test_a_tag_with_a_comma_is_refused_rather_than_escaped(store: Store) -> None:
    """feat-001/AC-28: a tag is printed comma separated everywhere, so one with a comma is two.

    The sheet joins them with commas, the table does, the terminal does. Escaping in three places
    is three places to get it wrong; refusing in the one place a tag is created is once. The
    refusal says what to do instead, because "invalid" with no suggestion is a dead end.
    """
    load(store, [listing("a")])
    with pytest.raises(ValueError, match="comma"):
        store.create_tag("well, unknown")

    with pytest.raises(ValueError, match="A tag needs a name"):
        store.create_tag("   ")

    with pytest.raises(ValueError, match="40"):
        store.create_tag("x" * 41)


def test_renaming_a_tag_keeps_every_property_that_had_it(store: Store) -> None:
    """feat-001/AC-29: the whole reason a tag is a row and not text on a property.

    A vocabulary somebody is building gets a word wrong, and the fix has to be one action. If a
    rename meant re-tagging every property, nobody would rename anything and the wrong word would
    stay, which is how a tag list turns into a list of near-synonyms nobody trusts.
    """
    made = load(store, [listing("a"), listing("b"), listing("c")])
    store.set_tags(made["a"], ["drive by"])
    store.set_tags(made["b"], ["drive by"])

    renamed = store.rename_tag("drive by", "go and look")

    assert renamed.name == "go and look"
    assert renamed.used == 2, "the rename dropped the properties carrying it"
    assert store.tags_for(made["a"]) == ("go and look",)
    assert store.tags_for(made["b"]) == ("go and look",)
    assert store.tags_for(made["c"]) == ()


def test_renaming_onto_a_name_that_exists_merges_the_two(store: Store) -> None:
    """feat-001/AC-29: the only sane reading of the request, and the one that is wanted.

    Somebody who has ended up with "septic?" and "septic unknown" and renames the first to the
    second is saying they are the same word. A refusal would leave both, which is the state they
    were trying to leave, and a property carrying both must not end up carrying it twice.
    """
    made = load(store, [listing("a"), listing("b"), listing("c")])
    store.set_tags(made["a"], ["septic?"])
    store.set_tags(made["b"], ["septic?", "septic unknown"])
    store.set_tags(made["c"], ["septic unknown"])

    merged = store.rename_tag("septic?", "septic unknown")

    assert [tag.name for tag in store.tags()] == ["septic unknown"]
    assert merged.used == 3, f"a property was lost or counted twice: {merged.used}"
    assert store.tags_for(made["b"]) == ("septic unknown",), "the merged tag is on twice"


def test_deleting_a_tag_takes_it_off_every_property_and_says_how_many(store: Store) -> None:
    """feat-001/AC-29: the number is the point of answering at all.

    Deleting a word is the one tag action that cannot be seen afterwards. "Off 14 properties" is
    the difference between somebody knowing what they just did and finding out weeks later.
    """
    made = load(store, [listing("a"), listing("b")])
    store.set_tags(made["a"], ["barn", "keep an eye"])
    store.set_tags(made["b"], ["barn"])

    assert store.delete_tag("barn") == 2
    assert [tag.name for tag in store.tags()] == ["keep an eye"]
    assert store.tags_for(made["a"]) == ("keep an eye",)

    with pytest.raises(KeyError):
        store.delete_tag("barn")


def test_a_merged_property_shows_the_tags_of_both_halves(store: Store) -> None:
    """feat-001/AC-30, constitution 7: a merge must never be how somebody's own words go missing.

    Two sites had the same house and this tool worked that out later. Anything written on either
    record was written about the house, so the record that stands for the house now carries all of
    it. Gathered rather than moved, exactly as annotations are, because moving is how data gets
    lost when the merge is undone.
    """
    made = load(store, [listing("a"), listing("b")])
    store.set_tags(made["a"], ["barn"])
    store.set_tags(made["b"], ["her favourite"])

    merged = store.supersede([made["a"], made["b"]], join_signal="same address")

    assert set(store.tags_for(merged)) == {"barn", "her favourite"}


def test_a_tag_taken_off_a_merged_property_comes_off_the_half_it_was_on(store: Store) -> None:
    """feat-001/AC-30: a tag you can see and cannot remove reads as the tool ignoring the click.

    The gathering above is what makes this necessary. A tag that arrived on one half is shown on
    the record that stands for the house, so unticking it has to reach where it actually lives.
    Whatever is kept is left exactly where it is: nothing a person wrote moves between records,
    which is what carries their work back out of a merge as well as into one.
    """
    made = load(store, [listing("a"), listing("b")])
    store.set_tags(made["a"], ["barn"])
    store.set_tags(made["b"], ["her favourite", "septic?"])
    merged = store.supersede([made["a"], made["b"]], join_signal="same address")

    kept = store.set_tags(merged, ["barn", "her favourite"])

    assert set(kept) == {"barn", "her favourite"}
    assert set(store.tags_for(merged)) == {"barn", "her favourite"}
    #: Still on the record it was written on, not moved onto the merged one.
    assert store.tags_for_many([made["b"]])[made["b"]] == ("her favourite",)


def test_the_whole_list_is_what_is_sent_so_leaving_one_out_removes_it(store: Store) -> None:
    """feat-001/AC-28: what a set of ticked boxes is, sent as what it is."""
    made = load(store, [listing("a")])

    store.set_tags(made["a"], ["barn", "well", "drive by"])
    assert store.set_tags(made["a"], ["barn"]) == ("barn",)
    assert store.set_tags(made["a"], []) == ()
    #: The words survive losing their last property. That is what makes them a vocabulary rather
    #: than a side effect of whichever houses are currently tagged.
    assert {tag.name for tag in store.tags()} == {"barn", "well", "drive by"}


def test_the_sheet_and_the_table_read_a_property_s_tags_from_the_same_column(
    store: Store, db_path: Path
) -> None:
    """feat-011/AC-16: one column, so the spreadsheet and the screen cannot disagree."""
    made = load(store, [listing("a"), listing("b")], name="portales")
    store.set_tags(made["a"], ["barn", "her favourite"])

    from homescout.export import cols, rows_of

    rows = {row.listing_id: row for row in rows_of(store, made.run_id)}
    column = cols.BY_NAME["Tags"]

    assert column.origin == "annotation", "tags are shown as the tool's work rather than theirs"
    assert column.value(rows[made["a"]]) == "barn, her favourite"
    assert column.value(rows[made["b"]]) is None, "an untagged property reads as empty, not as ''"


def test_both_surfaces_reach_the_same_vocabulary(store: Store, db_path: Path) -> None:
    """feat-010/AC-63, feat-003/AC-33, constitution 8: both surfaces reach the same vocabulary.

    Not a formality. Tagging fifty properties with one word is the shape of the job the first time
    somebody decides a word was worth having, and fifty clicks is not how anybody does that.
    """
    made = load(store, [listing("a"), listing("b")])
    held = held_workspace(shared_store(db_path))

    with client(held) as browser:
        put = browser.put(
            f"/api/listings/{made['a']}/tags", json={"tags": ["Barn"]}, headers=ours()
        )
        assert put.status_code == 200, put.text
        assert put.json()["tags"] == ["Barn"]

        listed = browser.get("/api/tags", headers=reading()).json()["tags"]
        assert [tag["name"] for tag in listed] == ["Barn"]
        assert listed[0]["used"] == 1

        renamed = browser.post(
            "/api/tags/Barn/rename", json={"to": "outbuilding"}, headers=ours()
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["tag"]["used"] == 1

        shown = browser.get(f"/api/listings/{made['a']}", headers=reading()).json()
        assert shown["listing"]["tags"] == ["outbuilding"], "a property hides its own tags"

        gone = browser.delete("/api/tags/outbuilding", headers=ours())
        assert gone.json()["properties"] == 1
        assert browser.get("/api/tags", headers=reading()).json()["tags"] == []

    code, said, _ = invoke(["tags", "set", made["b"], "well"], db=db_path)
    assert code == 0, said
    assert api.tags_of(held, made["b"]) == ("well",)

    code, said, _ = invoke(["tags", "rename", "well", "cistern"], db=db_path)
    assert code == 0 and "cistern" in said, said
    assert api.tags_of(held, made["b"]) == ("cistern",)

    code, said, _ = invoke(["tags", "list"], db=db_path)
    assert code == 0 and "cistern" in said and "1 propert" in said, said

    #: No names is how a command line says "none of them", and it has to mean that rather than
    #: "leave it alone": a person clearing tags from a terminal has no other way to say it.
    code, said, _ = invoke(["tags", "set", made["b"]], db=db_path)
    assert code == 0, said
    assert api.tags_of(held, made["b"]) == ()


def test_a_bad_tag_is_refused_with_a_reason_rather_than_a_stack_trace(
    store: Store, db_path: Path
) -> None:
    """feat-001/AC-28: the refusal reaches the person who typed it, in words."""
    made = load(store, [listing("a")])
    held = held_workspace(shared_store(db_path))

    with pytest.raises(InvalidInput, match="comma"):
        api.set_tags(held, made["a"], ["well, unknown"])

    with pytest.raises(InvalidInput, match="No tag named"):
        api.rename_tag(held, "nothing here", "something")

    with client(held) as browser:
        refused = browser.post("/api/tags", json={"name": "a, b"}, headers=ours())
        assert refused.status_code == 400, refused.text
        assert "comma" in refused.text
