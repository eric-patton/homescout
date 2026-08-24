"""The deterministic baseline, against sentences real people wrote.

Every string quoted here is in `tests/fixtures/extract/descriptions.json` or is a sentence from the
1,176 measured for this feature. That is deliberate: prose written to exercise a pattern proves the
pattern matches prose written to exercise it.

The trap cases carry as much weight as the recoveries, and more attention. A feature that reports a
private well on a quarter of every market because the market says "well-maintained" would be worse
than one that reports nothing at all, and there are 301 chances to make that mistake in the corpus.
"""

from __future__ import annotations

import pytest

from homescout.extract import Extracted, known_values, patterns, read_prose, values_for


class Prop:
    """A property that is nothing but its description."""

    def __init__(self, description: str | None) -> None:
        self.description = description


def one(text: str) -> dict[str, Extracted]:
    return values_for(Prop(text))


def value(text: str, field: str) -> str | None:
    return one(text)[field].value


# ---------------------------------------------------------------------------
# What the text says
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "field", "expected"),
    [
        # feat-009/AC-2: water, sewer, heating, cooling, gas and roof, from real sentences.
        ("This unique 2 story home is a 3 bedroom 3 bathrooms, with its own private well.",
         "water_source", "well"),
        ("Home is on City water.", "water_source", "city"),
        ("this property has coop water and septic system.", "water_source", "co-op"),
        ("The property also features a functioning irrigation well.",
         "water_source", "irrigation"),
        ("Electric power is supplied by PNM, and both residences are serviced by a septic system.",
         "sewer", "septic"),
        ("City water, electricity and city sewer on site.", "sewer", "city"),
        ("Central heat & air with ceiling fans throughout.", "heating", "central"),
        ("Central heat & air with ceiling fans throughout.", "cooling", "central"),
        ("Radiant in floor heating for cozy, comfortable winters.", "heating", "radiant"),
        ("Both units are heated with pellet stoves.", "heating", "pellet stove"),
        ("Living room boasts a cozy wood stove, ideal for keeping warm on chilly nights.",
         "heating", "wood stove"),
        ("New HVAC system, water heater, radiant baseboard heating.", "heating", "baseboard"),
        ("Additional features include vinyl windows, steel exterior doors, a natural gas furnace.",
         "heating", "furnace"),
        ("Inside, you'll stay comfortable year-round with refrigerated air.",
         "cooling", "refrigerated"),
        ("Amenities include: Seamless Metal Roof, A/C and evaporative cooling.",
         "cooling", "evaporative"),
        ("New mini-splits in each bedroom have been added to this affordable 2-bedroom home.",
         "cooling", "mini-split"),
        ("Natural gas, wooden spiral staircase, outside city limits, lots of parking.",
         "gas", "natural"),
        ("Heating is provided by propane, supplied via a 500-gallon tank.", "gas", "propane"),
        ("A durable metal roof offers low-maintenance protection.", "roof", "metal"),
        ("Recent upgrades include a new shingle roof installed in August 2025.", "roof", "shingle"),
        ("You'll have Peace of mind with a solid clay tile roof complete with gutters!",
         "roof", "tile"),
        ("A detached garage, flat roof and included kitchen appliances add exceptional value.",
         "roof", "flat"),
    ],
)
def test_a_stated_fact_is_recovered(sentence: str, field: str, expected: str) -> None:
    """feat-009/AC-1, feat-009/AC-2: the baseline runs with no configuration and finds these."""
    assert value(sentence, field) == expected


def test_provenance_is_on_every_recovered_value() -> None:
    """feat-009/AC-3: a value nobody can trace is a value nobody can weigh."""
    found = one("The property has a well, septic and electricity.")
    assert found["water_source"].provenance == "pattern"
    assert found["sewer"].provenance == "pattern"
    assert found["water_source"].evidence, "and it keeps the sentence it came from"


# ---------------------------------------------------------------------------
# What the text does not say
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        # 301 occurrences of `well` in the measured corpus, roughly one in seven about water.
        "Welcome home to this well-maintained and inviting property in Portales!",
        "This well kept home features a split floor plan and loads of personality.",
        "Spacious custom-built, one-owner home situated in a well-established neighborhood.",
        "The open-concept design features a well-appointed kitchen complete with appliances.",
        "Plenty of natural light pouring in from all directions as well as great finishes.",
        "The kitchen holds tons of cabinets as well.",
        "From the moment you walk in, youll notice how clean, well cared for this home feels.",
        "The primary bedroom is spacious and well-lit.",
        "The split floor plan provides privacy with a well-separated primary suite.",
        "Beyond the property lines, the neighborhood is prized for its well maintained homes.",
        "Whether you're looking for a hobby farm, this well-equipped acreage offers much.",
        "This is a cute, well-updated home that will qualify for all loan types.",
        "The bedrooms are well sized with generous closets.",
        "A location well built for a growing family.",
    ],
)
def test_the_adverb_is_not_a_water_supply(sentence: str) -> None:
    """feat-009/AC-5: the single most expensive false positive this feature could have."""
    assert value(sentence, "water_source") is None


@pytest.mark.parametrize(
    ("sentence", "field"),
    [
        # feat-009/AC-5: roughly three in ten utility mentions in real prose are like these.
        ("Water well, electricity, and septic needed.", "sewer"),
        ("Water well, electricity, and septic needed.", "water_source"),
        ("Utilities such as electric, water, and sewer are nearby, adding to the appeal.", "sewer"),
        ("City water is available.", "water_source"),
        ("Gas, city water, and electric are all available utilities!", "water_source"),
        ("Property can be annexed into the city which would give the buyer city water & sewer.",
         "sewer"),
        ("There is a city water line coming down Example Street approximately 600-700 ft.",
         "water_source"),
        ("City water extends down Example Street.", "water_source"),
        ("Two site-built additions include venting for a pellet or wood stove.", "heating"),
        ("There's also a designated spot for a wood-burning stove, perfect for cozy evenings.",
         "heating"),
        # A roof's age is not a roof.
        ("Recent updates add value, including a 200-amp electrical service upgrade, new roof.",
         "roof"),
        ("New roof will be installed soon!", "roof"),
        ("There is a two-car garage, roof is approximately one year old.", "roof"),
        # A kind is what this feature records, and these name none.
        ("Stay comfortable year-round with an energy-efficient AC unit.", "cooling"),
        ("The 3-bedroom home features air conditioning for year-round comfort.", "cooling"),
        # A rhetorical negative about an appliance is not a fact about a supply.
        ("A wood-burning fireplace anchors the living area with a warmth no gas insert can match.",
         "gas"),
    ],
)
def test_a_possibility_is_not_a_fact(sentence: str, field: str) -> None:
    """feat-009/AC-5: available, nearby, needed, planned and somewhere-to-put-one all mean no."""
    assert value(sentence, field) is None


def test_a_description_that_says_nothing_says_nothing() -> None:
    """feat-009/AC-5: the criterion's own test, over prose that mentions none of the six fields."""
    silent = [
        "CLEAN, COZY and WELL-KEPT! Enjoy comfortable living in this well-maintained single-wide "
        "mobile home situated on an extra-large city lot. This home features a sunny and spacious "
        "living area, two bedrooms and two beautifully updated bathrooms.",
        "Country property. 12.04 Acres. Close proximity to town.",
        "This home is a JEWEL-just waiting for someone to put the finishing touches on and restore "
        "it to all of it's former glory! Some great work has already been done and this home would "
        "be a perfect candidate for a REHAB loan to finish the few items that are left.",
        "Build your dream home on this 3-acre lot in a new subdivision north of town.",
        "The inviting country-style kitchen and dining area includes nice cabinetry and a pantry "
        "for storage. You'll appreciate the newer carpet and quality finishes throughout.",
    ]
    for text in silent:
        found = one(text)
        assert set(found) == set(values_for(Prop(None))), "every field is always present"
        assert all(entry.value is None for entry in found.values()), text[:60]
        assert all(entry.provenance is None for entry in found.values())


# ---------------------------------------------------------------------------
# What the text says it does not have
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sentence", "field"),
    [
        ("The propane tank was removed from property.", "gas"),
        ("Three mini-splits efficiently heat and cool this all-electric home-no propane required.",
         "gas"),
        ("Property does not have a water well or septic installation.", "water_source"),
        ("A versatile hobby room, office, or guest room (no permanent heat source).", "heating"),
    ],
)
def test_a_stated_absence_is_a_value(sentence: str, field: str) -> None:
    """feat-009/AC-5, the known-negative edge case: 'no gas' is knowledge, not an empty field."""
    found = one(sentence)[field]
    assert found.value == "none"
    assert found.determined, "and it reaches a criterion, unlike an empty field"


def test_a_negation_does_not_reach_across_a_clause() -> None:
    """The corpus sentence that caught this: a `not` about restoration, four words from the water.

    Read literally by an earlier draft, this said the property had no water. It has no water
    *connection*, which the prospect rule reaches by the right route.
    """
    text = (
        "AN OLD HOUSE ON THE PROPERTY BUT IT IS NOT RESTORED, CO-OP WATER IS IN THE ROAD "
        "NEXT TO THE LAND BUT NO METER CONNECTION."
    )
    assert value(text, "water_source") is None


def test_a_negation_does_not_reach_an_unrelated_claim() -> None:
    """`no propane required` denies the propane and not the three mini-splits beside it."""
    text = "Three mini-splits efficiently heat and cool this all-electric home-no propane required."
    found = one(text)
    assert found["gas"].value == "none"
    assert found["cooling"].value == "mini-split", "the cooling is not negated by the gas"


# ---------------------------------------------------------------------------
# Two answers is not an answer
# ---------------------------------------------------------------------------


def test_a_description_that_says_two_things_says_neither() -> None:
    """feat-009/AC-5, the conflicting-values edge case: never silently pick one."""
    text = "The property includes a well, two septic systems, and access to city water."
    found = one(text)
    assert found["water_source"].value is None, "a well and a town supply is not a water source"
    assert found["water_source"].conflicted
    assert len(found["water_source"].evidence) >= 1, "and the sentences are kept for a person"
    assert found["sewer"].value == "septic", "the sewer was not in doubt"


def test_a_conflicted_field_is_unknown_to_a_criterion() -> None:
    """Because a rule asking for a well must not fire on a property that also says city water."""
    text = "The property includes a well, two septic systems, and access to city water."
    assert "water_source" not in known_values(one(text))
    assert known_values(one(text))["sewer"] == "septic"


# ---------------------------------------------------------------------------
# Reading prose at all
# ---------------------------------------------------------------------------


def test_no_description_is_not_an_error() -> None:
    """The spec's own edge case: extraction produces nothing and reports nothing unusual."""
    for absent in (None, "", "   "):
        assert read_prose(absent) is None
        assert all(entry.value is None for entry in values_for(Prop(absent)).values())


def test_a_very_long_description_is_cut_and_says_so() -> None:
    """The spec's own edge case: bounded before anything reads it, and the cut is recorded."""
    from homescout.extract.text import MAX_LENGTH

    long = "A lovely home. " * 1000 + "It has a private well."
    prose = read_prose(long)
    assert prose is not None
    assert prose.truncated
    assert len(prose.text) == MAX_LENGTH


def test_a_claim_and_a_hedge_in_different_sentences_are_two_statements() -> None:
    """The window never leaves its sentence, or this property would lose its septic tank."""
    text = "The property is served by a septic system. City water is available at the road."
    found = one(text)
    assert found["sewer"].value == "septic"
    assert found["water_source"].value is None


def test_the_claim_a_sentence_makes_is_found_wherever_it_sits() -> None:
    """A long sentence with the fact at the end is the common shape in real prose."""
    text = (
        "Self-sufficient with 3.7 KW solar system/AGM batteries, aerobic septic system, "
        "3 GPM well with storage tank, rain harvest catchment system and enclosed garden."
    )
    found = one(text)
    assert found["sewer"].value == "septic"
    assert found["water_source"].value == "well"


def test_matching_is_settled_by_specificity_rather_than_by_order() -> None:
    """`irrigation well` is one claim, not an irrigation well and a well arguing with each other."""
    assert patterns.CLAIMS["water_source"][0].value == "irrigation"
    assert value("Irrigation well.", "water_source") == "irrigation"


# ---------------------------------------------------------------------------
# Defects found by reading real output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        # Found in an exported sheet: this recorded the heating and lost the cooling, because the
        # pattern wanted "heat and air" exactly and listings write "heating and air conditioning".
        "The 3-bedroom, 2-bath mobile home features central heating and air conditioning.",
        "Additional features include central heating and cooling, energy-efficient windows.",
        "Central heating and cooling provide year-round comfort.",
        "Stay comfortable year-round with forced central heat/air and ceiling fans.",
        "Additional highlights include a spacious 3-car garage, central heating and air.",
        "Central heat & air with ceiling fans throughout.",
        "Home also includes Central Heat & Air, a 1 Car Garage, Fireplace and Fenced Yard.",
    ],
)
def test_one_sentence_about_both_fills_both(sentence: str) -> None:
    """feat-009/AC-2: a house with central heat and central air has both, not one of them."""
    found = one(sentence)
    assert found["heating"].value == "central", sentence
    assert found["cooling"].value == "central", sentence


def test_a_sentence_about_only_cooling_fills_only_cooling() -> None:
    """feat-009/AC-2, the other direction: the fix must not invent a heating system."""
    found = one("Both homes are equipped with central air conditioning.")
    assert found["cooling"].value == "central"
    assert found["heating"].value is None
