"""Every scenario in the spec, with the spec's own values.

The table under test is the most consequential twenty lines in the feature. `matched` is narrow,
`distinct` is narrow, and everything else that shares a signal falls to a person, because failing to
merge costs a duplicate row and merging wrongly costs a price history that is fiction.
"""

from __future__ import annotations

import pytest

from homescout.merge import Candidate, outcome_for, parse
from homescout.merge.signals import DEFAULT_TOLERANCE_METRES, metres_between, normalize_parcel

ZIP = "88888"


def row(
    listing_id: str,
    line: str | None = None,
    *,
    unit: str | None = None,
    postal: str = ZIP,
    at: tuple[float, float] | None = None,
    parcel: str = "",
) -> Candidate:
    return Candidate(
        listing_id=listing_id,
        address=parse(line, unit=unit, postal=postal),
        latitude=at[0] if at else None,
        longitude=at[1] if at else None,
        parcel=parcel,
    )


NEAR = (34.1800000, -103.3300000)
#: About thirty metres north of it, which is inside the tolerance and is the widest true pair in
#: the corpus.
CLOSE = (34.1802700, -103.3300000)
#: About a kilometre away.
FAR = (34.1890000, -103.3300000)


def test_the_same_house_formatted_differently() -> None:
    """feat-006/AC-1: the spec's first scenario, with the brief's own pair.

    And the provenance names what justified it, which is the other half of the scenario.
    """
    outcome, signals = outcome_for(
        row("a", "1747 S Roosevelt Rd 10 1/2"),
        row("b", "1747 South Roosevelt Road 10 1/2"),
    )

    assert outcome == "matched"
    assert any("the same address" in note for note in signals.agreed)
    assert signals.conflicted == ()


def test_a_parcel_number_settles_it() -> None:
    """feat-006/AC-4: agreement matches regardless of what the addresses say."""
    outcome, signals = outcome_for(
        row("a", "1747 S Roosevelt Rd", parcel="12-345-678-90"),
        row("b", "Tract 4 of the Roosevelt Subdivision", parcel="1234567890"),
    )

    assert outcome == "matched"
    assert any("parcel number" in note for note in signals.agreed)


def test_a_parcel_number_rules_it_out() -> None:
    """feat-006/AC-4: disagreement is distinct regardless of the addresses agreeing perfectly."""
    outcome, signals = outcome_for(
        row("a", "612 E 17th Ln", at=NEAR, parcel="111-222-333"),
        row("b", "612 E 17th Ln", at=NEAR, parcel="444-555-666"),
    )

    assert outcome == "distinct"
    assert any("different parcel numbers" in note for note in signals.conflicted)


def test_one_parcel_number_settles_nothing() -> None:
    """feat-006/AC-5: it neither confirms nor rules out, so the rest of the signals decide."""
    outcome, signals = outcome_for(
        row("a", "612 E 17th Ln", at=NEAR, parcel="111-222-333"),
        row("b", "612 E 17th Ln", at=CLOSE),
    )

    assert outcome == "matched", "decided by the address and the coordinates"
    assert signals.parcel == "unknown"
    assert any("only one of them" in note for note in signals.unknown)


def test_a_parcel_number_too_short_to_mean_anything_is_not_a_parcel_number() -> None:
    """feat-006/AC-4: because a source writing `0` in that column must not merge a whole county."""
    assert normalize_parcel("12-345-678-90") == "1234567890"
    assert normalize_parcel("0") == ""
    assert normalize_parcel(None) == ""
    assert normalize_parcel("  ") == ""


def test_coordinates_confirm_a_probable_match() -> None:
    """feat-006/AC-6: the spec's scenario, at thirty metres."""
    outcome, signals = outcome_for(row("a", "612 E 17th Ln", at=NEAR),
                                   row("b", "612 E 17th Ln", at=CLOSE))

    assert outcome == "matched"
    assert signals.place == "agreed"
    assert signals.metres is not None and signals.metres < DEFAULT_TOLERANCE_METRES


def test_coordinates_contradict_an_address_match() -> None:
    """feat-006/AC-6: ambiguous, not matched and not distinct, and the contradiction is stated.

    This is the corpus's own hardest real case: `612 E 17th Ln` and `612 E 17th St`, a hundred
    metres apart, with different floor areas. Two houses on two similarly named streets, or one
    house geocoded twice. Nothing here can tell, and a person can tell instantly.
    """
    outcome, signals = outcome_for(row("a", "612 E 17th Ln", at=NEAR),
                                   row("b", "612 E 17th St", at=FAR))

    assert outcome == "ambiguous"
    assert any("further than" in note for note in signals.conflicted)
    assert any("the same address" in note for note in signals.agreed)


def test_a_unit_number_is_not_noise() -> None:
    """feat-006/AC-3: different units are different properties, whatever else agrees."""
    outcome, signals = outcome_for(
        row("a", "2128 Verity", unit="Unit B", at=NEAR),
        row("b", "2128 Verity", unit="Unit C", at=NEAR),
    )

    assert outcome == "distinct"
    assert any("unit designation" in note for note in signals.conflicted)


def test_a_unit_on_one_side_only_is_not_a_disagreement() -> None:
    """feat-006/AC-3: one source breaking the unit out and another folding it in is the norm.

    The corpus has exactly this: Realtor.com writes the unit as its own field, Redfin writes the
    same house with no unit at all. Reading that as a difference would refuse every merge involving
    a source that does not break it out.
    """
    outcome, _ = outcome_for(
        row("a", "2128 Verity Unit B", unit="Unit B", at=NEAR),
        row("b", "2128 Verity Unit B", at=CLOSE),
    )

    assert outcome == "matched"


def test_land_with_no_street_address_is_never_matched_on_coordinates() -> None:
    """feat-006/AC-8: the spec's scenario, and the reason the whole queue exists for acreage.

    Twenty metres apart with the same lot size is not evidence on a parcel measured in acres: the
    centroid of one and the centroid of its neighbour are closer than that.
    """
    outcome, signals = outcome_for(
        row("a", "Bigler Addition Block 2 Lot 3", at=NEAR),
        row("b", "000 TBD Alder Addition Block 2 Lot 3 Rd", at=(34.18002, -103.33)),
    )

    assert outcome == "ambiguous"
    assert any("no street address" in note for note in signals.unknown)


def test_land_with_a_parcel_number_is_still_decided_by_it() -> None:
    """feat-006/AC-8: the strongest outcome without a parcel number is ambiguous. With one it is
    not, which is what "without a parcel number" in the criterion means."""
    outcome, _ = outcome_for(
        row("a", "Bigler Addition Block 2 Lot 3", at=NEAR, parcel="99-88-77-66"),
        row("b", "Block 2 Lot 3", at=NEAR, parcel="99887766"),
    )

    assert outcome == "matched"


def test_two_rows_with_nothing_in_common_are_not_a_pair_at_all() -> None:
    """feat-006/AC-9: the queue is for questions, and this is not one.

    Everything that reaches the queue costs a person a decision, so a pair sharing no signal must
    not reach it.
    """
    outcome, _ = outcome_for(row("a", "612 E 17th Ln", at=NEAR),
                             row("b", "9 Rushmore Way", postal="10001", at=(40.7, -74.0)))

    assert outcome == "unrelated"


def test_an_address_match_with_no_coordinates_at_all_still_matches() -> None:
    """feat-006/AC-6: coordinates confirm a match; their absence does not withhold one.

    A source that gives no coordinates would otherwise make every one of its rows ambiguous, which
    would put the whole of that source in front of a person every night.
    """
    outcome, signals = outcome_for(row("a", "612 E 17th Ln"), row("b", "612 E 17th Ln"))

    assert outcome == "matched"
    assert signals.place == "unknown"


@pytest.mark.parametrize(
    "point",
    [(0.0, 0.0), (34.0, -103.0), (None, None), (34.18, None), (999.0, -103.0)],
    ids=["null island", "whole degrees", "absent", "half absent", "impossible"],
)
def test_a_coordinate_that_is_really_a_shrug_is_treated_as_absent(point) -> None:
    """feat-006, the spec's edge case: one bad coordinate must not make every pair ambiguous."""
    outcome, signals = outcome_for(
        row("a", "612 E 17th Ln", at=point if point[0] is not None else None),
        row("b", "612 E 17th Ln", at=NEAR),
    )

    assert signals.place == "unknown"
    assert outcome == "matched", "decided by the address, with the coordinates ignored"


def test_the_tolerance_is_configurable(monkeypatch) -> None:
    """feat-006/AC-7: and its default is the value the brief names."""
    from homescout.merge.signals import tolerance

    assert DEFAULT_TOLERANCE_METRES == 50.0
    assert tolerance() == 50.0

    monkeypatch.setenv("HOMESCOUT_MERGE_TOLERANCE_METRES", "150")
    assert tolerance() == 150.0

    outcome, _ = outcome_for(row("a", "612 E 17th Ln", at=NEAR),
                             row("b", "612 E 17th St", at=(34.18090, -103.33)))
    assert outcome == "matched", "a hundred metres is inside a hundred and fifty"

    for nonsense in ("", "wide", "-3", "0"):
        monkeypatch.setenv("HOMESCOUT_MERGE_TOLERANCE_METRES", nonsense)
        assert tolerance() == 50.0, nonsense


def test_the_distance_arithmetic_is_right_enough_to_trust() -> None:
    """feat-006/AC-6: because every coordinate decision rests on it."""
    one_degree_of_latitude = metres_between((34.0, -103.0), (35.0, -103.0))

    assert 110_500 < one_degree_of_latitude < 111_500
    assert metres_between(NEAR, NEAR) == 0.0
    assert 25 < metres_between(NEAR, CLOSE) < 35


def test_the_signals_are_sentences_a_person_can_act_on() -> None:
    """feat-006/AC-9: the queue is read by somebody deciding, not by a program.

    A confidence score would say the same thing and tell them nothing. "Same street number,
    different town" and "same everything, coordinates a kilometre apart" are different questions.
    """
    _, signals = outcome_for(row("a", "612 E 17th Ln", at=NEAR),
                             row("b", "612 E 17th St", at=FAR))

    said = " ".join((*signals.agreed, *signals.conflicted, *signals.unknown))
    assert "612 E 17th Ln" in said, "it quotes what the sources actually wrote"
    assert "m apart" in said
    assert all(note == note.strip() and note[0].islower() for note in signals.agreed)
