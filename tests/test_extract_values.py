"""Provenance, precedence, and what an unfilled field means to a criterion.

Three questions this file answers, and the third is the one the rule engine depends on:

- how was this value determined, and can a person see why
- what happens when two things have an opinion
- what does a criterion do about a field nobody could determine
"""

from __future__ import annotations

from extract_fakes import described, load
from homescout.extract import Extracted, known_values, values_for
from homescout.records import ListingFields
from homescout.rules.definition import Rule
from homescout.rules.parse import parse
from homescout.rules.verdicts import record
from homescout.rules.verdicts import values_for as rule_values
from homescout.store import Store

WELL = "This unique 2 story home is a 3 bedroom 3 bathrooms, with its own private well."
SILENT = "Country property. 12.04 Acres. Close proximity to town."


class Supplied:
    """A property whose source returned one of the six fields as data.

    No shipped adapter does this: all three normalization modules were read while this feature was
    planned and none maps heating, cooling, water, sewer, gas or roof. The precedence is built and
    proved anyway, because the day a source starts returning one is the day it matters, and finding
    out then that prose quietly overwrote it would be finding out too late.
    """

    def __init__(self, description: str | None = None, **given: str) -> None:
        self.description = description
        for name, value in given.items():
            setattr(self, name, value)


def rule(expression: str, rule_id: str = "r1", severity: str = "flag") -> Rule:
    return Rule(id=rule_id, when=expression, severity=severity, expression=parse(expression))


def test_a_source_supplied_value_is_never_overwritten() -> None:
    """feat-009/AC-4: prose is the fallback, not the authority."""
    found = values_for(Supplied(WELL, water_source="city"))
    assert found["water_source"].value == "city"
    assert found["water_source"].provenance == "source"


def test_a_source_supplied_value_wins_even_where_prose_disagrees_with_itself() -> None:
    """feat-009/AC-4: a conflict in the text is not a reason to ignore what the source said."""
    both = "The property includes a well, two septic systems, and access to city water."
    found = values_for(Supplied(both, water_source="well"))
    assert found["water_source"].value == "well"
    assert not found["water_source"].conflicted


def test_the_model_only_fills_what_the_patterns_left_empty() -> None:
    """feat-009/AC-3: precedence is source, then pattern, then model, and it is tested downwards."""
    from_model = {
        "water_source": Extracted("water_source", "city", "model", ("city water",)),
        "sewer": Extracted("sewer", "septic", "model", ("septic tank",)),
    }
    found = values_for(Supplied(WELL), model=from_model)
    assert found["water_source"].value == "well", "the patterns settled this one"
    assert found["water_source"].provenance == "pattern"
    assert found["sewer"].value == "septic", "and the model settled this one"
    assert found["sewer"].provenance == "model"


def test_every_field_is_always_present_however_little_is_known() -> None:
    """feat-009/AC-3: a caller never branches on shape, only on whether a value is there."""
    for subject in (Supplied(None), Supplied(SILENT), Supplied(WELL)):
        found = values_for(subject)
        assert set(found) == {"water_source", "sewer", "heating", "cooling", "gas", "roof"}
        assert all(isinstance(entry, Extracted) for entry in found.values())


def test_an_undetermined_field_is_absent_rather_than_empty() -> None:
    """feat-009/AC-14: the evaluator reads absent as unknown, which is what it is."""
    assert known_values(values_for(Supplied(SILENT))) == {}
    assert known_values(values_for(Supplied(WELL))) == {"water_source": "well"}


def test_a_stated_absence_does_reach_a_criterion() -> None:
    """feat-009/AC-14: `none` is a value. A property with no gas can be asked about."""
    text = "The propane tank was removed from property."
    assert known_values(values_for(Supplied(text)))["gas"] == "none"


# ---------------------------------------------------------------------------
# Through the rule engine, which is where these values are for
# ---------------------------------------------------------------------------


def test_a_criterion_naming_an_extracted_field_finds_one(store: Store) -> None:
    """feat-009/AC-14: the six names are members of the rule engine's field namespace."""
    loaded = load(store, [described("p1", WELL)])
    values = rule_values(store, loaded["p1"], run_id=loaded.run_id)
    assert values["water_source"] == "well"


def test_an_unfilled_extracted_field_is_undetermined_rather_than_false(store: Store) -> None:
    """feat-009/AC-14: the whole point. A test that could not be run is not a test that failed."""
    loaded = load(store, [described("p1", SILENT), described("p2", WELL)])
    verdicts = record(store, [rule('water_source == "well"')], loaded.run_id)
    by_listing = {v.listing_id: v for v in verdicts}

    assert by_listing[loaded["p2"]].verdict == "fired"
    assert by_listing[loaded["p1"]].verdict == "undetermined"
    assert "water_source" in by_listing[loaded["p1"]].missing


def test_a_drop_rule_cannot_remove_a_property_for_want_of_a_description(store: Store) -> None:
    """feat-009/AC-14, said the way it will be felt: no house is excluded by a silent listing."""
    from homescout.rules.results import results

    loaded = load(store, [described("p1", None), described("p2", WELL)])
    record(store, [rule('sewer == "city"', severity="drop")], loaded.run_id)

    kept = {r.listing_id for r in results(store, loaded.run_id)}
    assert kept == {loaded["p1"], loaded["p2"]}, "neither is dropped for a silent listing"


def test_the_namespace_declares_every_extracted_field_as_filled() -> None:
    """feat-009/AC-14: a rule naming one of these no longer gets told nothing fills it."""
    from homescout.extract import NAMES
    from homescout.rules import namespace as ns

    for name in NAMES:
        field = ns.find(name)
        assert field is not None and field.origin == "extracted"
        assert field.populated, f"{name} is filled by this build and must say so"


def test_the_vocabulary_and_the_namespace_agree() -> None:
    """feat-009/AC-2: checked at import, and asserted here so the check itself cannot be deleted."""
    from homescout.extract import fields as fx
    from homescout.rules import namespace as ns

    declared = {name for name, field in ns.FIELDS.items() if field.origin == "extracted"}
    assert declared == set(fx.NAMES)


def test_a_listing_record_still_carries_no_extracted_field() -> None:
    """The measurement this feature was planned on, kept true by a test.

    No source supplies any of the six. When one starts, this fails, and the failure is the reminder
    to check that the precedence in `values_for` does what the day requires.
    """
    from homescout.extract import NAMES
    from homescout.records import FIELD_NAMES

    assert not set(NAMES) & set(FIELD_NAMES)
    assert ListingFields().description is None
