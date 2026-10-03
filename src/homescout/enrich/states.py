"""The states, by the three names the federal government uses for each of them.

The FCC's file listing says `state_fips` and `state_name`; its availability rows say `state_usps`;
a person says `NM`. One table, so a state named at the command line reaches a file listing without
three different lookups scattered through the code.

Territories are here because the FCC publishes them and a property could be in one. The count is
therefore fifty-six rather than fifty.
"""

from __future__ import annotations

#: USPS code to (FIPS, name), which are the two the FCC's listing speaks.
STATES: dict[str, tuple[str, str]] = {
    "AL": ("01", "Alabama"),
    "AK": ("02", "Alaska"),
    "AZ": ("04", "Arizona"),
    "AR": ("05", "Arkansas"),
    "CA": ("06", "California"),
    "CO": ("08", "Colorado"),
    "CT": ("09", "Connecticut"),
    "DE": ("10", "Delaware"),
    "DC": ("11", "District of Columbia"),
    "FL": ("12", "Florida"),
    "GA": ("13", "Georgia"),
    "HI": ("15", "Hawaii"),
    "ID": ("16", "Idaho"),
    "IL": ("17", "Illinois"),
    "IN": ("18", "Indiana"),
    "IA": ("19", "Iowa"),
    "KS": ("20", "Kansas"),
    "KY": ("21", "Kentucky"),
    "LA": ("22", "Louisiana"),
    "ME": ("23", "Maine"),
    "MD": ("24", "Maryland"),
    "MA": ("25", "Massachusetts"),
    "MI": ("26", "Michigan"),
    "MN": ("27", "Minnesota"),
    "MS": ("28", "Mississippi"),
    "MO": ("29", "Missouri"),
    "MT": ("30", "Montana"),
    "NE": ("31", "Nebraska"),
    "NV": ("32", "Nevada"),
    "NH": ("33", "New Hampshire"),
    "NJ": ("34", "New Jersey"),
    "NM": ("35", "New Mexico"),
    "NY": ("36", "New York"),
    "NC": ("37", "North Carolina"),
    "ND": ("38", "North Dakota"),
    "OH": ("39", "Ohio"),
    "OK": ("40", "Oklahoma"),
    "OR": ("41", "Oregon"),
    "PA": ("42", "Pennsylvania"),
    "RI": ("44", "Rhode Island"),
    "SC": ("45", "South Carolina"),
    "SD": ("46", "South Dakota"),
    "TN": ("47", "Tennessee"),
    "TX": ("48", "Texas"),
    "UT": ("49", "Utah"),
    "VT": ("50", "Vermont"),
    "VA": ("51", "Virginia"),
    "WA": ("53", "Washington"),
    "WV": ("54", "West Virginia"),
    "WI": ("55", "Wisconsin"),
    "WY": ("56", "Wyoming"),
    "AS": ("60", "American Samoa"),
    "GU": ("66", "Guam"),
    "MP": ("69", "Northern Mariana Islands"),
    "PR": ("72", "Puerto Rico"),
    "UM": ("74", "U.S. Minor Outlying Islands"),
    "VI": ("78", "United States Virgin Islands"),
}

#: FIPS back to USPS, for turning the first two digits of a census block into a state.
BY_FIPS: dict[str, str] = {fips: code for code, (fips, _name) in STATES.items()}


def known(code: str) -> bool:
    return (code or "").strip().upper() in STATES


def fips_of(code: str) -> str | None:
    found = STATES.get((code or "").strip().upper())
    return found[0] if found else None


def name_of(code: str) -> str | None:
    found = STATES.get((code or "").strip().upper())
    return found[1] if found else None


def of_block(block: str) -> str | None:
    """The state a census block is in, which is its first two digits."""
    return BY_FIPS.get((block or "")[:2])


def codes() -> tuple[str, ...]:
    return tuple(sorted(STATES))


#: Which states share a border, for the records that are published a state at a time but answer a
#: question about distance. A dam ten miles from a house in Raton is in Colorado, and a record
#: holding New Mexico's dams alone would say the nearest one was somewhere else (feat-007/AC-53).
#:
#: Land borders only, and the Four Corners counts: Arizona and Colorado touch at a point, as do New
#: Mexico and Utah, and a point is enough to put a dam within ten miles. A test asserts the table
#: is symmetric, because a border one state knows about and the other does not is a typing mistake.
NEIGHBOURS: dict[str, tuple[str, ...]] = {
    "AL": ("FL", "GA", "MS", "TN"),
    "AZ": ("CA", "CO", "NM", "NV", "UT"),
    "AR": ("LA", "MO", "MS", "OK", "TN", "TX"),
    "CA": ("AZ", "NV", "OR"),
    "CO": ("AZ", "KS", "NE", "NM", "OK", "UT", "WY"),
    "CT": ("MA", "NY", "RI"),
    "DE": ("MD", "NJ", "PA"),
    "DC": ("MD", "VA"),
    "FL": ("AL", "GA"),
    "GA": ("AL", "FL", "NC", "SC", "TN"),
    "ID": ("MT", "NV", "OR", "UT", "WA", "WY"),
    "IL": ("IA", "IN", "KY", "MO", "WI"),
    "IN": ("IL", "KY", "MI", "OH"),
    "IA": ("IL", "MN", "MO", "NE", "SD", "WI"),
    "KS": ("CO", "MO", "NE", "OK"),
    "KY": ("IL", "IN", "MO", "OH", "TN", "VA", "WV"),
    "LA": ("AR", "MS", "TX"),
    "ME": ("NH",),
    "MD": ("DC", "DE", "PA", "VA", "WV"),
    "MA": ("CT", "NH", "NY", "RI", "VT"),
    "MI": ("IN", "OH", "WI"),
    "MN": ("IA", "ND", "SD", "WI"),
    "MS": ("AL", "AR", "LA", "TN"),
    "MO": ("AR", "IA", "IL", "KS", "KY", "NE", "OK", "TN"),
    "MT": ("ID", "ND", "SD", "WY"),
    "NE": ("CO", "IA", "KS", "MO", "SD", "WY"),
    "NV": ("AZ", "CA", "ID", "OR", "UT"),
    "NH": ("MA", "ME", "VT"),
    "NJ": ("DE", "NY", "PA"),
    "NM": ("AZ", "CO", "OK", "TX", "UT"),
    "NY": ("CT", "MA", "NJ", "PA", "VT"),
    "NC": ("GA", "SC", "TN", "VA"),
    "ND": ("MN", "MT", "SD"),
    "OH": ("IN", "KY", "MI", "PA", "WV"),
    "OK": ("AR", "CO", "KS", "MO", "NM", "TX"),
    "OR": ("CA", "ID", "NV", "WA"),
    "PA": ("DE", "MD", "NJ", "NY", "OH", "WV"),
    "RI": ("CT", "MA"),
    "SC": ("GA", "NC"),
    "SD": ("IA", "MN", "MT", "ND", "NE", "WY"),
    "TN": ("AL", "AR", "GA", "KY", "MO", "MS", "NC", "VA"),
    "TX": ("AR", "LA", "NM", "OK"),
    "UT": ("AZ", "CO", "ID", "NM", "NV", "WY"),
    "VT": ("MA", "NH", "NY"),
    "VA": ("DC", "KY", "MD", "NC", "TN", "WV"),
    "WA": ("ID", "OR"),
    "WV": ("KY", "MD", "OH", "PA", "VA"),
    "WI": ("IA", "IL", "MI", "MN"),
    "WY": ("CO", "ID", "MT", "NE", "SD", "UT"),
}


def neighbours(code: str) -> tuple[str, ...]:
    """The states sharing a border with this one. Islands and Alaska have none."""
    return NEIGHBOURS.get((code or "").strip().upper(), ())
