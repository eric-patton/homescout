"""Turning what the core answers into the documents the pages read.

Everything here is a shape change and nothing here is a decision. The rule that keeps it that way:
each function takes a workspace, calls `api`, and rearranges. If one of them ever needs to work
something out, that working out belongs in `api` where both surfaces can reach it.

The envelope and most of the documents are the ones this product already produces for `--json`, so
a page and an automated caller read the same thing.
"""

from __future__ import annotations

import os
from typing import Any

from .. import api

#: Which file is which surface. One page per surface, reloadable and bookmarkable, rather than one
#: application with routes: a failure on one cannot then take the others with it.
PAGES: dict[str, str] = {
    "/": "searches.html",
    "/search/{name}": "search.html",
    "/results/{name}": "results.html",
    "/listing/{listing_id}": "listing.html",
    "/changes/{name}": "changes.html",
    "/matches": "matches.html",
}

#: A tile source, if the person configured one. Empty by default and deliberately so: asking a tile
#: server for tiles tells it which part of the world is being looked at, and `product-global.md`
#: lists exactly four kinds of outbound traffic this product makes, none of which is that.
TILES_VARIABLE = "HOMESCOUT_MAP_TILES"
TILES_ATTRIBUTION_VARIABLE = "HOMESCOUT_MAP_ATTRIBUTION"


def searches(workspace: api.Workspace) -> list[dict[str, Any]]:
    """The list surface: every saved search, with what its last run found."""
    found: list[dict[str, Any]] = []
    for name in api.list_searches(workspace):
        entry: dict[str, Any] = {"name": name}
        try:
            definition = api.show_search(workspace, name)
            entry["description"] = getattr(definition, "description", None)
            entry["sources"] = list(getattr(definition, "sources", ()))
            entry["areas"] = len(getattr(definition, "areas", ()))
            entry["problems"] = [
                {"location": p.location, "message": p.message, "severity": p.severity}
                for p in definition.problems()
            ]
        except Exception as exc:  # noqa: BLE001 - one unreadable file must not empty the list
            entry["problems"] = [{"location": name, "message": str(exc), "severity": "problem"}]
        entry.update(api.run_status(workspace, name))
        found.append(entry)
    return found


def search(workspace: api.Workspace, name: str) -> dict[str, Any]:
    """One saved search, as the builder reads it."""
    definition = api.show_search(workspace, name)
    return {
        "name": name,
        "description": getattr(definition, "description", None),
        "sources": list(getattr(definition, "sources", ())),
        "areas": [_area(area) for area in getattr(definition, "areas", ())],
        "exclusions": [_area(area) for area in getattr(definition, "exclusions", ())],
        "problems": [
            {"location": p.location, "message": p.message, "severity": p.severity}
            for p in definition.problems()
        ],
        "model_extraction": bool(getattr(definition, "model_extraction", False)),
    }


def _area(area: Any) -> dict[str, Any]:
    """One geographic component, in this tool's own vocabulary rather than any map library's."""
    shape = getattr(area, "geometry", None) or getattr(area, "shape", None)
    return {
        "kind": getattr(area, "kind", None),
        "name": getattr(area, "name", None),
        "value": getattr(area, "value", None),
        "excluded": bool(getattr(area, "excluded", False)),
        "geometry": _geojson(shape),
    }


def _geojson(shape: Any) -> Any:
    """A drawn shape as GeoJSON, or nothing when the area is a named place."""
    if shape is None:
        return None
    for attribute in ("geojson", "as_geojson", "__geo_interface__"):
        found = getattr(shape, attribute, None)
        if callable(found):
            return found()
        if found is not None:
            return found
    return None


def comparison(workspace: api.Workspace, name: str, since: str | None) -> dict[str, Any]:
    """What changed, in the shape a digest already carries."""
    from .. import digest as digest_module

    found = api.changes(workspace, name, since=since)
    entry = digest_module.entry(workspace.store, search_name=name, comparison=found)
    return {"searches": [entry]}


def matches(workspace: api.Workspace) -> list[dict[str, Any]]:
    return [
        {
            "id": found.id,
            "listing_ids": list(found.listing_ids),
            "agreed": list(found.agreed),
            "conflicted": list(found.conflicted),
            "noticed_at": found.noticed_at,
        }
        for found in api.pending_matches(workspace)
    ]


def areas(workspace: api.Workspace) -> list[dict[str, Any]]:
    return [
        {
            "area_type": note.area_type,
            "area_value": note.area_value,
            "notes": note.notes,
            "updated_at": note.updated_at,
        }
        for note in api.area_notes(workspace)
    ]


def settings(workspace: api.Workspace) -> dict[str, Any]:
    """What the pages need to know about this installation.

    The map's tile source is the only interesting one, and its default is nothing at all. See
    `TILES_VARIABLE`.
    """
    from ..deliver.settings import environment

    values = environment(workspace.root)
    tiles = (values.get(TILES_VARIABLE) or "").strip()
    return {
        "map": {
            "tiles": tiles or None,
            "attribution": (values.get(TILES_ATTRIBUTION_VARIABLE) or "").strip() or None,
            "variable": TILES_VARIABLE,
        },
        "area_kinds": list(api.AREA_KINDS),
    }


def tile_source(root: Any, environ: Any = None) -> str | None:
    from ..deliver.settings import environment

    values = environment(root, environ if environ is not None else os.environ)
    return (values.get(TILES_VARIABLE) or "").strip() or None
