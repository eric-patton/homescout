"""Turning what the core answers into the documents the pages read.

Everything here is a shape change and nothing here is a decision. The rule that keeps it that way:
each function takes a workspace, calls `api`, and rearranges. If one of them ever needs to work
something out, that working out belongs in `api` where both surfaces can reach it.

The envelope and most of the documents are the ones this product already produces for `--json`, so
a page and an automated caller read the same thing.
"""

from __future__ import annotations

from typing import Any

from .. import api
from . import settings

#: Which file is which surface. One page per surface, reloadable and bookmarkable, rather than one
#: application with routes: a failure on one cannot then take the others with it.
#:
#: Seven now. The spec named six screens; the seventh is where a person finds out what this
#: installation has set up and what it has not, which the six had no home for and which a person
#: otherwise discovers by reading a file.
PAGES: dict[str, str] = {
    "/": "searches.html",
    "/settings": "settings.html",
    "/search/{name}": "search.html",
    "/results/{name}": "results.html",
    "/listing/{listing_id}": "listing.html",
    "/changes/{name}": "changes.html",
    "/matches": "matches.html",
    "/fire/{name}": "fire.html",
}

#: Kept as names here because the pages read them, and defined once in `settings`.
TILES_VARIABLE = settings.TILES_VARIABLE
TILES_ATTRIBUTION_VARIABLE = settings.TILES_ATTRIBUTION_VARIABLE


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
            # Both are properties of the file, and the list is the only place they are visible.
            # Without them the card cannot say a search is set aside, and pausing one from here
            # looks like it did nothing at all.
            entry["paused"] = bool(getattr(definition, "paused", False))
            entry["archived"] = bool(getattr(definition, "archived", False))
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
    """One saved search, as the builder reads it. Assembled by the core; passed through here."""
    return api.search_document(workspace, name)


def comparison(workspace: api.Workspace, name: str, since: str | None) -> dict[str, Any]:
    """What changed, in the shape a digest already carries."""
    from .. import digest as digest_module

    found = api.changes(workspace, name, since=since)
    entry = digest_module.entry(workspace.store, search_name=name, comparison=found)
    return {"searches": [entry]}


def matches(workspace: api.Workspace) -> list[dict[str, Any]]:
    """The queue as the review page reads it, summaries and all.

    Straight through from `api.review_queue`, which already assembles what a person needs to decide
    a pair without opening either property. Nothing is rearranged here because there is nothing left
    to rearrange, and a shape change that is the identity function is the right amount of work for
    this layer to be doing.
    """
    return [dict(found) for found in api.review_queue(workspace)]


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


def places(workspace: api.Workspace) -> list[dict[str, Any]]:
    """The towns and counties this store's properties are in, so nobody has to guess a spelling."""
    return [dict(place) for place in api.places(workspace)]


def installation(workspace: api.Workspace) -> dict[str, Any]:
    """What the pages need to know about this installation.

    Named for what it answers rather than for the module it reads, because `settings` here would
    shadow `web.settings` and resolve differently depending on what was imported first.

    The map's tile source is the only interesting one, and its default is nothing at all.
    """
    source, attribution = settings.tiles(workspace.root)
    return {
        "map": {
            "tiles": source,
            "attribution": attribution,
            "variable": TILES_VARIABLE,
        },
        "hazards": api.hazard_layers(),
        **api.vocabulary(),
        "model": api.configuration(workspace)["model"],
    }


def tile_source(root: Any, environ: Any = None) -> str | None:
    return settings.tiles(root, environ)[0]
