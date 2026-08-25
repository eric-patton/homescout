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
