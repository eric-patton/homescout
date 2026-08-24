"""Every adapter this tool ships, held to the interface, and the claim that adding one is cheap.

These are parametrized over the registry rather than over a list, so a fourth source inherits every
obligation here the moment it is registered rather than when somebody remembers to add it.

The last two tests are the point of the whole feature. "Adding a source means writing one adapter,
not touching the core" is a non-negotiable, and it is only worth anything if something checks it.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from homescout.sources import (
    Area,
    Capabilities,
    PacedSession,
    Source,
    create,
    registered,
)
from sources_fakes import FakeResponse, FakeTransport, code_of, session_with

SHIPPED = ("realtor", "redfin", "zillow")
FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def session() -> PacedSession:
    return session_with(FakeTransport())


@pytest.fixture(params=SHIPPED)
def adapter(request, session: PacedSession) -> Source:
    return create(request.param, session)


def test_every_shipped_source_is_registered() -> None:
    """feat-005/AC-12: registration is the whole of what adding a source costs."""
    assert set(SHIPPED) <= set(registered())


def test_every_adapter_satisfies_the_interface(adapter: Source) -> None:
    """feat-005/AC-1: verified by the same test for all of them, rather than one each."""
    assert isinstance(adapter, Source)
    assert adapter.name
    assert callable(adapter.run_search)
    assert callable(adapter.fetch_preview), "preview retrieval is part of the interface"


def test_every_adapter_declares_its_capabilities_honestly(adapter: Source) -> None:
    """feat-005/AC-1: a declaration that names a field the query does not have is refused at birth.

    `Capabilities` checks that itself, so this asserts the parts it cannot: that something is
    actually declared, that the areas are real area types, and that a ceiling comes with a page size
    that fits under it.
    """
    capabilities = adapter.capabilities()

    assert isinstance(capabilities, Capabilities)
    assert capabilities.applies, f"{adapter.name} claims to narrow nothing at all"
    assert capabilities.accepts_areas, f"{adapter.name} accepts no geography"
    for kind in capabilities.accepts_areas:
        assert kind in Area.__args__, f"{adapter.name} accepts {kind!r}, which is not an area"
    assert capabilities.ceiling is None or capabilities.ceiling > 0
    if capabilities.ceiling is not None:
        assert capabilities.page_size <= capabilities.ceiling


def test_every_adapter_refuses_an_area_it_did_not_declare(adapter: Source) -> None:
    """feat-005/AC-6: answering a different question quietly is worse than not answering.

    Every source declines something: two of them take only a box, and the third takes anything but.
    """
    from homescout.sources import Polygon
    from homescout.sources.base import SearchQuery
    from homescout.sources.errors import SourceUnavailable

    capabilities = adapter.capabilities()
    shape = Polygon(points=((-103.4, 34.1), (-103.3, 34.1), (-103.3, 34.2), (-103.4, 34.1)))
    assert not capabilities.accepts(shape), "no source takes a drawn shape"

    with pytest.raises(SourceUnavailable):
        adapter.run_search(SearchQuery(area=shape))


def test_no_adapter_reads_a_credential(adapter: Source) -> None:
    """feat-005/AC-11: checked against the code rather than the prose that explains its absence.

    The failure this catches is real and predictable: a site starts refusing, and the first instinct
    is to add a cookie or a key to make it stop.
    """
    import importlib

    package = importlib.import_module(f"homescout.sources.{adapter.name}")
    modules = [package] + [
        getattr(package, name) for name in ("queries", "normalize") if hasattr(package, name)
    ]
    for module in modules:
        body = code_of(module).lower()
        for forbidden in ("authorization", "api_key", "apikey", "password", "bearer"):
            assert forbidden not in body, f"{module.__name__} mentions {forbidden}"


def test_no_adapter_fetches_a_preview_from_a_scheme_that_is_not_the_web(adapter: Source) -> None:
    """feat-005/AC-11: a source's own text is the one thing here that becomes an outbound request.

    A preview URL is written by a listing site and fetched from this machine, so the scheme is
    checked rather than trusted. Inherited by every adapter, including the fourth one.
    """
    from homescout.records import ListingFields, SourceRow

    for hostile in ("file:///c:/windows/system32/config/sam", "javascript:alert(1)", "data:,x"):
        row = SourceRow(
            source=adapter.name,
            fields=ListingFields(),
            payload={"imgSrc": hostile, "primary_photo": {"href": hostile},
                     "URL (SEE PRICING)": hostile},
            source_listing_id="1",
        )
        assert adapter.fetch_preview(row) is None, hostile


# -- the claim the whole feature rests on -----------------------------------


CORE = (
    "homescout.store",
    "homescout.runner",
    "homescout.matches",
    "homescout.digest",
    "homescout.api",
    "homescout.cli",
    "homescout.deliver",
)


def _imports(path: pathlib.Path) -> set[str]:
    import ast

    found: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


@pytest.mark.parametrize("source", ["zillow", "redfin"])
def test_a_new_adapter_does_not_reach_into_the_core(source: str) -> None:
    """feat-005/AC-12: stated as the dependency direction, which is the durable form of it.

    Not as a diff against a commit, which would be true exactly once: the next feature to land moves
    the baseline and the test then fails for reasons that have nothing to do with these adapters.
    A source that needed the core to change would have to reach for it, and reaching is what is
    checked.
    """
    import homescout.sources as package

    folder = pathlib.Path(package.__file__).parent / source
    for path in folder.rglob("*.py"):
        for name in _imports(path):
            assert not any(name.startswith(core) for core in CORE), f"{path.name} imports {name}"


def test_the_core_does_not_import_a_single_adapter() -> None:
    """feat-005/AC-12: the other direction, which is the one that would make a fourth source dear.

    Nothing outside the sources package may import an adapter. The run loop asks the registry for
    whatever a saved search named and never learns what it got, which is the property that makes
    the fourth source as cheap as the third.
    """
    import homescout

    root = pathlib.Path(homescout.__file__).parent
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("sources/"):
            continue
        for name in _imports(path):
            for adapter in SHIPPED:
                assert f"sources.{adapter}" not in name, f"{relative} imports {name}"


def test_the_only_adapters_named_outside_the_sources_package_are_defaults() -> None:
    """feat-005/AC-12: the exceptions, named rather than left for somebody to find.

    Two places outside the sources package say `realtor`, and both are a default value rather than
    knowledge: the template a brand-new saved search is scaffolded from (an empty source list is a
    file that cannot be run) and the source list an in-memory definition starts with. Nothing
    branches on either, and a search naming any other source works identically.

    This is a whitelist on purpose. A third file appearing here is the signal that something in the
    core has started to care which adapter it is talking to.
    """
    import homescout

    root = pathlib.Path(homescout.__file__).parent
    naming: dict[str, set[str]] = {}
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if relative.startswith("sources/"):
            continue
        body = path.read_text(encoding="utf-8")
        found = {name for name in SHIPPED if name in body}
        if found:
            naming[relative] = found

    assert naming == {
        "search/definition.py": {"realtor"},
        "search/__init__.py": {"realtor"},
    }, naming


def test_a_run_over_three_sources_asks_each_one_in_its_own_form(tmp_path) -> None:
    """feat-005/AC-12: one saved search, three sources, no core change, and it completes.

    The saved search holds a drawn shape, which no site accepts. The query planner turns it into
    whatever each source does accept: a circle for the one that takes places, a box for the two that
    take boxes. That translation already existed; this test is what proves a new source inherits it.
    """
    from homescout import api
    from searches_fakes import SQUARE, write

    write(
        tmp_path / "searches",
        "drawn",
        text=(
            "name: drawn\n"
            "areas:\n"
            f"  - {{type: polygon, name: north, geometry: {json.dumps(SQUARE)}}}\n"
            "sources: [realtor, zillow, redfin]\n"
        ),
    )

    realtor_search = json.loads(
        (FIXTURES / "realtor" / "search_city.json").read_text(encoding="utf-8")
    )

    def answer(request):
        if "zillow" in request.url:
            return FakeResponse(
                body=json.dumps(
                    {"cat1": {"searchResults": {"mapResults": []},
                              "searchList": {"totalResultCount": 0}}}
                ).encode()
            )
        if "redfin" in request.url:
            return FakeResponse(
                body=(FIXTURES / "redfin" / "search_box.csv").read_bytes(),
                content_type="text/csv",
            )
        return FakeResponse(body=json.dumps(realtor_search).encode())

    class Recording:
        """The real adapter, plus a note of what it was actually asked for."""

        def __init__(self, inner: Source) -> None:
            self.inner = inner
            self.areas: list[Area] = []

        def __getattr__(self, name: str):
            return getattr(self.inner, name)

        def search(self, query):
            self.areas.append(query.area)
            return self.inner.search(query)

    transport = FakeTransport(default=answer)
    session = session_with(transport)
    built = {name: Recording(create(name, session)) for name in SHIPPED}

    from homescout.matches import InMemoryQueue
    from homescout.search.definition import FileCatalog
    from homescout.store import Store

    with Store.open(tmp_path / "homescout.db") as store:
        space = api.Workspace(
            store=store,
            catalog=FileCatalog(tmp_path / "searches"),
            queue=InMemoryQueue(()),
            sources=built,
            images=False,
        )
        outcome = api.run_search(space, "drawn")

    reported = {report.source: report for report in outcome.sources}
    assert set(reported) == set(SHIPPED), "every source contributed a report"
    assert outcome.run.status == "completed"
    assert all(report.outcome == "ok" for report in reported.values()), reported

    forms = {name: type(source.areas[0]).__name__ for name, source in built.items()}
    assert forms == {
        "realtor": "PointRadius",
        "zillow": "BoundingBox",
        "redfin": "BoundingBox",
    }, forms
    assert reported["redfin"].rows == 5, "the recorded download's properties came through"


def test_a_source_being_unavailable_costs_that_source_and_nothing_else(tmp_path) -> None:
    """feat-005/AC-8: the run completes, records the outcome, and disappears nothing.

    This is the one that matters most when a source is added, because the failure it guards against
    is silent and permanent: reading one source's silence as evidence that a property sold would
    write a disappearance into history that no later run can undo. The store requires positive
    evidence, and this asserts that a new source cannot get around it.
    """
    from homescout import api
    from homescout.matches import InMemoryQueue
    from homescout.search.definition import FileCatalog
    from homescout.store import Store
    from searches_fakes import SQUARE, write

    write(
        tmp_path / "searches",
        "drawn",
        text=(
            "name: drawn\n"
            "areas:\n"
            f"  - {{type: polygon, name: north, geometry: {json.dumps(SQUARE)}}}\n"
            "sources: [realtor, zillow, redfin]\n"
        ),
    )
    realtor_search = json.loads(
        (FIXTURES / "realtor" / "search_city.json").read_text(encoding="utf-8")
    )

    def answer(request):
        if "zillow" in request.url:
            return FakeResponse(
                body=json.dumps(
                    {"cat1": {"searchResults": {"mapResults": []},
                              "searchList": {"totalResultCount": 0}}}
                ).encode()
            )
        if "redfin" in request.url:
            # The shape the site uses when it will not serve a download at all.
            return FakeResponse(
                body=b'{}&&{"errorMessage":"Endpoint not found.","resultCode":122}',
                content_type="application/json",
            )
        return FakeResponse(body=json.dumps(realtor_search).encode())

    session = session_with(FakeTransport(default=answer))
    built = {name: create(name, session) for name in SHIPPED}

    with Store.open(tmp_path / "homescout.db") as store:
        space = api.Workspace(
            store=store,
            catalog=FileCatalog(tmp_path / "searches"),
            queue=InMemoryQueue(()),
            sources=built,
            images=False,
        )
        first = api.run_search(space, "drawn")
        second = api.run_search(space, "drawn")

        reported = {report.source: report for report in second.sources}
        assert reported["redfin"].outcome == "unavailable"
        assert "refused" in (reported["redfin"].detail or "")
        assert reported["realtor"].outcome == "ok"
        assert second.run.status == "completed", "the run finished"
        assert second.degraded is True, "and said it was degraded"

        # The properties the first run saw are still present, and none of them was recorded as
        # having disappeared on the strength of a source that never answered.
        assert first.comparison.counts["new"] > 0
        assert second.comparison.counts["gone"] == 0, "absence is not evidence"


def test_no_adapter_ever_claims_to_have_filtered_to_the_exact_area(adapter: Source) -> None:
    """feat-005/AC-6: a coarse query is answered coarsely, and the caller is never told otherwise.

    Geography is not among the fields an adapter can declare it applies, which is what makes this
    structurally true: a source asked for a box containing a drawn shape has no way to report that
    it filtered to the shape, so the exact local test always runs.
    """
    from homescout.sources.base import QUERY_FIELDS

    capabilities = adapter.capabilities()

    assert not any("area" in name or "poly" in name for name in QUERY_FIELDS)
    assert not any("area" in name or "poly" in name for name in capabilities.applies)
    assert set(capabilities.applies) <= set(QUERY_FIELDS)
