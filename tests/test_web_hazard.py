"""The fire map's tiles, which this machine fetches rather than the browser.

The map draws the same layer the enrichment pass reads. Nothing here talks to it: the fetching is
replaced, and what is tested is everything around the fetch, which is where the decisions are.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from homescout import api
from homescout.enrich import hazard
from homescout.errors import InvalidInput
from homescout.store import Store
from web_fakes import STATIC, client, held_workspace, listing, load, reading, shared_store

PNG = b"\x89PNG\r\n\x1a\nnot really, but it starts right"


def answering(monkeypatch, body: bytes = PNG, kind: str = "image/png", asked: list | None = None):
    """The map service, replaced. Records what it was asked for."""

    class Answer:
        headers = {"Content-Type": kind}

        def read(self) -> bytes:
            return body

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def opened(request, timeout=None):
        if asked is not None:
            asked.append(request.full_url)
        return Answer()

    monkeypatch.setattr(hazard.urllib.request, "urlopen", opened)


def test_a_rectangle_is_four_numbers_and_nothing_else() -> None:
    """feat-010/AC-55: the value comes from a page, and a page's values reach a URL.

    Not a sanitiser: a rectangle genuinely is four numbers, so parsing it as four numbers and
    rebuilding it from them leaves nothing of whatever was sent that was not one.
    """
    assert hazard.rectangle("-11897270,4383205,-11662500,4618000").count(",") == 3

    for wrong in ("", "1,2,3", "1,2,3,4,5", "1,2,3,four", "1,2,3,4&f=json", "*"):
        with pytest.raises(InvalidInput):
            hazard.rectangle(wrong)


def test_a_tile_is_a_tile_sized_thing() -> None:
    """feat-010/AC-55: a page asking for a ten-thousand pixel picture is not drawing a map."""
    assert hazard.dimensions("256,256") == "256,256"
    for wrong in ("256", "256,256,256", "0,256", "4096,4096", "-1,-1", "big,big"):
        with pytest.raises(InvalidInput):
            hazard.dimensions(wrong)


def test_a_tile_is_fetched_once_and_then_read_off_the_disk(tmp_path: Path, monkeypatch) -> None:
    """feat-010/AC-55: the model is republished every few years; a picture of it does not go off.

    Which is the whole of being polite here. A person panning around New Mexico generates the same
    rectangles over and over, and the second time costs that server nothing.
    """
    asked: list[str] = []
    answering(monkeypatch, asked=asked)

    first = hazard.tile(tmp_path, "https://example.invalid/ImageServer/exportImage", "wildfire",
                        "1.0,2.0,3.0,4.0", "256,256")
    second = hazard.tile(tmp_path, "https://example.invalid/ImageServer/exportImage", "wildfire",
                         "1.0,2.0,3.0,4.0", "256,256")

    assert first == second == PNG
    assert len(asked) == 1, "the same rectangle was fetched twice"
    assert "bbox=1.0%2C2.0%2C3.0%2C4.0" in asked[0]
    assert "f=image" in asked[0] and "format=png32" in asked[0]
    assert list((tmp_path / "tiles" / "wildfire").glob("*.png")), "nothing was kept"
    assert not list((tmp_path / "tiles" / "wildfire").glob("*.part")), "a half tile was left"


def test_an_answer_that_is_not_a_picture_is_a_failure(tmp_path: Path, monkeypatch) -> None:
    """feat-010/AC-55: an ArcGIS service answers an unusable request with JSON and a 200.

    So the status says nothing and the only honest test is what came back. Kept out of the cache
    too: a stored error would be a permanently broken tile.
    """
    answering(monkeypatch, body=b'{"error":{"code":400}}', kind="application/json")

    with pytest.raises(Exception, match="not a"):
        hazard.tile(tmp_path, "https://example.invalid/ImageServer/exportImage", "wildfire",
                    "1.0,2.0,3.0,4.0", "256,256")
    assert not (tmp_path / "tiles").exists(), "an error was kept as though it were a picture"


def test_the_layers_are_the_ones_the_enrichment_pass_already_reads() -> None:
    """feat-010/AC-55: no second address to keep current.

    An ArcGIS service that answers about a point at `identify` draws that data at `exportImage`, so
    the map's address is the provider's address asked a different question. Pointing the provider
    somewhere else moves the map with it.
    """
    from homescout.enrich import settings

    found = api.hazard_layers()

    assert "wildfire" in found
    assert found["wildfire"].startswith(settings.endpoint("wildfire").url.rsplit("/", 1)[0])
    assert found["wildfire"].endswith("/exportImage")


def test_the_map_asks_this_tool_for_its_tiles_and_not_the_far_server() -> None:
    """feat-010/AC-55: because a browser refuses a cross-origin image it was not clearly offered.

    Asking directly draws nothing at all: Chrome blocks it as an opaque response. It is also a
    second thing the browser talks to, which this product's privacy statement does not describe.
    """
    fire = (STATIC / "fire.js").read_text(encoding="utf-8")

    assert "/api/hazard/${encodeURIComponent(layer)}" in fire
    assert "imagery.geoplatform.gov" not in fire, "the far server's address is hard-coded"
    assert "exportImage" not in fire, "the page builds the far server's request itself"


def test_an_unknown_layer_is_refused_by_name(store: Store, db_path: Path) -> None:
    """feat-010/AC-55: the layer names come from a page too."""
    load(store, [listing("a")])
    held = held_workspace(shared_store(db_path))

    with pytest.raises(InvalidInput, match="not a layer"):
        api.hazard_tile(held, "../../etc/passwd", "1,2,3,4")


def test_a_tile_is_served_as_a_picture_the_browser_may_keep(
    store: Store, db_path: Path, monkeypatch
) -> None:
    """feat-010/AC-55: and never sniffed, which is the rule every other image here follows."""
    answering(monkeypatch)
    load(store, [listing("a")])
    held = held_workspace(shared_store(db_path))

    with client(held) as browser:
        answered = browser.get(
            "/api/hazard/wildfire?bbox=1,2,3,4&size=256,256", headers=reading())

    assert answered.status_code == 200, answered.text
    assert answered.headers["content-type"] == "image/png"
    assert answered.headers["x-content-type-options"] == "nosniff"
    assert "max-age" in answered.headers.get("cache-control", "")
    assert answered.content == PNG
