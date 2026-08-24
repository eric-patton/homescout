"""What this layer is allowed to be, and what it is allowed to reach.

Three claims, and none of them is checked by using the interface. They are checked by looking at
what the package imports, what bytes it serves, and what it refuses to bind to, because all three
are properties that a working interface would satisfy either way and that erode one convenient
edit at a time.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from homescout.errors import InvalidInput
from homescout.store import Store
from homescout.web import serve as serving  # the module, not a function: see web/__init__.py
from web_fakes import STATIC, VENDOR, WEB, client, held_workspace, reading, shared_store

#: What this layer may not reach. Nothing here decides anything, so nothing here needs the store,
#: the loop, the criteria or the spreadsheet. If one of these ever has to be imported, a decision
#: was about to be written in the wrong place.
FORBIDDEN = (
    "homescout.store",
    "homescout.runner",
    "homescout.rules",
    "homescout.export",
    "homescout.sources",
    "homescout.merge",
    "homescout.extract",
    "homescout.enrich",
)


def python_files() -> list[Path]:
    return sorted(WEB.glob("*.py"))


def test_this_layer_reaches_the_core_and_nothing_else() -> None:
    """feat-010/AC-14: no business logic here, checked as an import graph rather than promised.

    `homescout.api` and `homescout.digest` and `homescout.errors` are the whole of what this may
    use, because a capability missing from `api` has to be a capability this interface cannot have.
    That is the right way round: it means the command line gets it too.
    """
    for module in python_files():
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            elif isinstance(node, ast.ImportFrom) and node.level:
                # `from .. import api` is exactly how this layer is meant to reach the core, so
                # what matters is the module it lands on rather than how far it climbed.
                inside = "homescout.web" if node.level == 1 else "homescout"
                names = [f"{inside}.{node.module}" if node.module else inside]
                names += [
                    f"{names[0]}.{alias.name}" if node.module else f"{inside}.{alias.name}"
                    for alias in node.names
                ]
            for name in names:
                for forbidden in FORBIDDEN:
                    assert not name.startswith(forbidden), (
                        f"{module.name} imports {name}. This layer calls the core and serializes; "
                        "anything it needs belongs in homescout.api where both surfaces reach it."
                    )


def without_comments(text: str) -> str:
    """The code, with the prose taken out.

    The same trick the source adapters use to scan themselves for credentials: a rule explained in a
    comment names the thing it forbids, and a scan that reads the comment finds it every time.
    """
    import re

    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


def test_the_scripts_never_build_markup() -> None:
    """The security requirement, made structural: there is no path from data to markup to take."""
    for script in sorted(STATIC.glob("*.js")):
        code = without_comments(script.read_text(encoding="utf-8"))
        for forbidden in (
            "innerHTML",
            "outerHTML",
            "insertAdjacentHTML",
            "document.write",
            "eval(",
        ):
            assert forbidden not in code, f"{script.name} uses {forbidden}"


def test_the_served_assets_are_the_files_as_committed(store: Store, db_path: Path) -> None:
    """feat-010/AC-16: no build step, and the proof is that the bytes match the repository."""
    with client(held_workspace(shared_store(db_path))) as browser:
        for name in ("app.css", "common.js", "results.js"):
            response = browser.get(f"/static/{name}", headers=reading())
            assert response.status_code == 200, name
            assert response.content == (STATIC / name).read_bytes(), name

        for path, page in (
            ("/", "searches.html"),
            ("/results/portales", "results.html"),
            ("/matches", "matches.html"),
        ):
            response = browser.get(path, headers=reading())
            assert response.status_code == 200, path
            assert response.content == (STATIC / page).read_bytes(), path


def test_every_surface_is_a_file_that_exists() -> None:
    """feat-010/AC-1: six surfaces, and each of them one page."""
    from homescout.web.wire import PAGES

    assert len(PAGES) == 7, "six surfaces from the spec, plus settings"
    for page in PAGES.values():
        assert (STATIC / page).is_file(), page
        assert (STATIC / page.replace(".html", ".js")).is_file(), page


def test_there_is_no_build_step() -> None:
    """AC-16 again, from the other side: nothing here is generated from anything."""
    for name in ("package.json", "webpack.config.js", "vite.config.js", "tsconfig.json"):
        assert not (WEB / name).exists()
    assert not any(STATIC.glob("*.min.js"))
    assert not any(STATIC.glob("*.map"))


# ---------------------------------------------------------------------------
# Where it listens
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.14", "::", "example.invalid"])
def test_a_routable_bind_address_is_refused(host: str, store: Store, db_path: Path) -> None:
    """feat-010/AC-15: there is no authentication here by design, so there is no network either."""
    with pytest.raises(InvalidInput) as raised:
        serving.serve(held_workspace(shared_store(db_path)), host=host)
    assert "127.0.0.1" in str(raised.value)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_a_loopback_address_is_allowed(host: str) -> None:
    assert serving.is_loopback(host)


def test_the_default_is_loopback() -> None:
    """Asserted rather than read: the default is the guarantee."""
    assert serving.DEFAULT_HOST == "127.0.0.1"
    assert serving.is_loopback(serving.DEFAULT_HOST)


def test_the_command_line_offers_no_way_to_move_it() -> None:
    """The stronger half of AC-15: not a knob that refuses, no knob."""
    from homescout.cli.main import build_parser

    for action in build_parser()._actions:
        found = getattr(action, "choices", None)
        if not isinstance(found, dict) or "serve" not in found:
            continue
        options = {o for a in found["serve"]._actions for o in a.option_strings}
        assert not {"--host", "--bind", "--address", "--interface"} & options


# ---------------------------------------------------------------------------
# The vendored library
# ---------------------------------------------------------------------------


def test_every_vendored_file_matches_its_recorded_fingerprint() -> None:
    """feat-010/AC-16: hand-vendored JavaScript usually has worse provenance than any other
    dependency in a project. This is the check that gives it the same provenance a lock file does.
    """
    import hashlib

    manifest = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"], "the manifest lists nothing"

    for entry in manifest["files"]:
        path = VENDOR / entry["file"]
        assert path.is_file(), f"{entry['file']} is in the manifest and not in the repository"
        body = path.read_bytes()
        assert len(body) == entry["bytes"], entry["file"]
        assert hashlib.sha256(body).hexdigest() == entry["sha256"], (
            f"{entry['file']} is not the file the manifest recorded"
        )
        assert entry["source"].startswith("https://"), entry["file"]
        assert entry["version"], entry["file"]


def test_nothing_is_vendored_that_the_manifest_does_not_name() -> None:
    """The other direction: a file that appeared without a fingerprint is the thing to catch."""
    manifest = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
    recorded = {entry["file"] for entry in manifest["files"]}
    present = {
        str(path.relative_to(VENDOR)).replace("\\", "/")
        for path in VENDOR.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    assert present == recorded


def test_the_licences_are_committed_beside_the_code() -> None:
    manifest = json.loads((VENDOR / "manifest.json").read_text(encoding="utf-8"))
    for package in manifest["packages"]:
        assert package["licence"] in ("BSD-2-Clause", "MIT"), package
    assert (VENDOR / "LICENSE-leaflet.txt").is_file()
    assert (VENDOR / "LICENSE-leaflet-draw.txt").is_file()
