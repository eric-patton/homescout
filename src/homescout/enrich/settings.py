"""Where each public service lives, as configuration rather than as a constant in a module.

Every address here was verified on 2026-08-23, and the reason this file exists at all is that the
one the brief gave for flood zones had already died by then: `hazards.fema.gov/gis/nfhl/rest/...`
answers 404 and the service moved under `/arcgis/rest/...`. These are public services run by
agencies with their own reorganizations, and the next one to move should be a line in an environment
file rather than a release (AC-14).

Each entry can be overridden by an environment variable, and the pacing is the same paced session
the listing sources use, at the floor delay rather than the shipped default: a federal open-data
endpoint is a different relationship from a listing site that would rather you went away, but it is
still somebody's server and a backfill over a county is thousands of points.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..sources.politeness import PolitenessConfig, SourcePolicy

#: One second between requests to any one provider, which is the floor the politeness layer permits
#: and refuses to go below. Providers do not wait on each other: pacing is per key.
PROVIDER_DELAY_SECONDS = 1.0
PROVIDER_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True, slots=True)
class Endpoint:
    """One service address, and what to call it in a message when it fails."""

    url: str
    description: str


#: The addresses as they stand. Each is overridable by `HOMESCOUT_ENRICH_<NAME>_URL`.
DEFAULTS: dict[str, Endpoint] = {
    "flood": Endpoint(
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query",
        "FEMA National Flood Hazard Layer, flood hazard zones",
    ),
    "elevation": Endpoint(
        "https://epqs.nationalmap.gov/v1/json",
        "USGS National Map elevation point query",
    ),
    "aquifer": Endpoint(
        "https://arcgis.water.nv.gov/arcgis/rest/services/BaseLayers/"
        "USGS_Aquifers_Principal/MapServer/0/query",
        "USGS principal aquifers of the United States",
    ),
    "wildfire": Endpoint(
        "https://imagery.geoplatform.gov/iipp/rest/services/Fire_Aviation/"
        "USFS_EDW_RMRS_WildfireHazardPotentialClassified/ImageServer/identify",
        "USFS wildfire hazard potential, classified",
    ),
    "boundaries": Endpoint(
        "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Current/MapServer",
        "Census TIGERweb boundaries",
    ),
    "geocode": Endpoint(
        "https://geocoding.geo.census.gov/geocoder/geographies/coordinates",
        "Census geocoder, what contains a point",
    ),
    "broadband": Endpoint(
        "https://broadbandmap.fcc.gov/api/public/map/location",
        "FCC National Broadband Map, which needs a token",
    ),
}

#: Where a token lives when a provider needs one. Read from the environment or the uncommitted
#: `.env` beside the database, never from a saved search and never from code, which is where the
#: constitution puts every secret in this product.
BROADBAND_TOKEN = "HOMESCOUT_FCC_TOKEN"


def endpoint(name: str) -> Endpoint:
    """This provider's address, with the environment having the last word."""
    default = DEFAULTS[name]
    override = os.environ.get(f"HOMESCOUT_ENRICH_{name.upper()}_URL")
    return Endpoint(override, default.description) if override else default


def token(variable: str) -> str | None:
    """A credential, from the environment first and the `.env` beside the database second.

    The same two places and the same order as the digest and the extraction model, through the same
    loader, because there is one file to look in for every setting in this product and a person who
    put a mail password in it will put an FCC key there too. The settings page has always counted
    that file when it reported a key as present; until this read it, that report could be true while
    the provider that needed the key saw nothing.

    The file matters for a second reason. This interface is started at log on and keeps the
    environment it was born with, so a variable set afterwards does not reach it until it is
    restarted. A line in the file reaches it on the next lookup.
    """
    found = os.environ.get(variable)
    if found and found.strip():
        return found.strip()

    from ..api import database_path
    from ..deliver.settings import ENV_FILE, read_env_file

    beside = database_path().resolve().parent / ENV_FILE
    written = read_env_file(beside).get(variable, "").strip()
    return written or None


def pacing(providers: tuple[str, ...]) -> PolitenessConfig:
    """The same politeness the sources get, at the floor delay, keyed per provider."""
    policy = SourcePolicy(delay=PROVIDER_DELAY_SECONDS, timeout=PROVIDER_TIMEOUT_SECONDS)
    return PolitenessConfig(default=policy, per_source={name: policy for name in providers})
