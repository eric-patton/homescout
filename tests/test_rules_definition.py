"""A rules section: its three parts, and everything that can be wrong with it at once.

The section lives in the saved search file, so these tests run both against the reader directly and
through `homescout searches validate`, which is where a person actually meets the messages.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homescout.rules.definition import SEVERITIES, check_section, read
from homescout.search import blocking, notices
from searches_fakes import catalog, sourced, write

RULES = """\
name: {name}
areas:
  - {{type: zip, value: "88130"}}
sources: [fake]
rules:
{body}
"""


@pytest.fixture(autouse=True)
def registered():
    with sourced("fake"):
        yield


def with_rules(tmp_path: Path, name: str, body: str):
    write(tmp_path / "searches", name, text=RULES.format(name=name, body=body))
    return catalog(tmp_path / "searches").load(name)


def test_a_rule_is_an_id_an_expression_and_a_severity() -> None:
    """feat-008/AC-1: the three parts, and the four things firing can mean."""
    made, problems = read(
        [
            {"id": "stale", "when": "dom > 180", "severity": "flag"},
            {"id": "no-fiber", "when": "upload_mbps < 100", "severity": "drop"},
            {"id": "big-lot", "when": "lot_sqft > 200000", "severity": "boost"},
            {"id": "tiny", "when": "sqft < 800", "severity": "demote"},
        ]
    )

    assert [rule.id for rule in made] == ["stale", "no-fiber", "big-lot", "tiny"]
    assert sorted(rule.severity for rule in made) == sorted(SEVERITIES)
    assert [p.severity for p in problems] == ["notice"], "only the unfilled field is remarked on"


@pytest.mark.parametrize(
    ("entry", "because"),
    [
        ({"when": "dom > 1", "severity": "flag"}, "needs an id"),
        ({"id": "a", "severity": "flag"}, "needs a `when`"),
        ({"id": "a", "when": "dom > 1"}, "is not a severity"),
        ({"id": "a", "when": "dom > 1", "severity": "delete"}, "is not a severity"),
        ({"id": "a", "when": "dom > 1", "severity": "flag", "colour": "red"}, "not part of a rule"),
        ("just a string", "written as an id"),
    ],
)
def test_a_rule_missing_a_part_is_a_validation_failure(entry, because: str) -> None:
    """feat-008/AC-1: all three are required, and a fourth key is a typo worth reporting."""
    problems = check_section([entry])

    assert any(because in p.message for p in problems), [p.message for p in problems]


def test_two_rules_with_one_name_is_a_failure_that_names_it() -> None:
    """feat-008/AC-2: a badge that could mean either of two criteria says nothing."""
    problems = check_section(
        [
            {"id": "stale", "when": "dom > 180", "severity": "flag"},
            {"id": "stale", "when": "dom > 365", "severity": "drop"},
        ]
    )

    assert len(problems) == 1
    assert "two rules are both called 'stale'" in problems[0].message
    assert problems[0].where == (1, "id")


def test_an_expression_that_cannot_be_read_names_the_rule_and_the_position() -> None:
    """feat-008/AC-15: which criterion, and where in it, because a run costs requests."""
    problems = check_section([{"id": "broken", "when": "dom > > 180", "severity": "flag"}])

    assert len(problems) == 1
    assert "the rule 'broken' cannot be read" in problems[0].message
    assert "at character" in problems[0].message


def test_every_problem_in_a_section_is_reported_at_once() -> None:
    """feat-008/AC-1, feat-008/AC-2: five criteria, five answers, one pass."""
    problems = check_section(
        [
            {"id": "ok", "when": "dom > 180", "severity": "flag"},
            {"id": "ok", "when": "dom > 1", "severity": "flag"},
            {"id": "unreadable", "when": "dom >", "severity": "flag"},
            {"id": "unknown-field", "when": "uplaod_mbps < 1", "severity": "flag"},
            {"id": "wrong-severity", "when": "dom > 1", "severity": "warn"},
        ]
    )

    assert len(problems) == 4
    assert [p.where[0] for p in problems] == [1, 2, 3, 4]


def test_a_search_carrying_rules_validates_from_the_command_line(tmp_path: Path) -> None:
    """feat-008/AC-1, feat-008/AC-15: where a person actually meets these messages."""
    from cli_fakes import invoke

    with_rules(
        tmp_path,
        "criteria",
        "  - {id: stale, when: 'dom > 180', severity: flag}\n"
        "  - {id: broken, when: 'dom >', severity: flag}\n",
    )

    code, out, err = invoke(
        ["searches", "validate", "criteria", "--json"], db=tmp_path / "homescout.db"
    )

    assert code == 2, err
    answer = json.loads(out)
    assert answer["valid"] is False
    assert any("the rule 'broken'" in p["message"] for p in answer["problems"])
    assert any("criteria.yaml:" in p["location"] for p in answer["problems"])


def test_a_rule_naming_a_field_nobody_fills_yet_does_not_stop_the_search(tmp_path: Path) -> None:
    """feat-008/AC-14: the brief's own example search, which drops on an enriched value.

    It runs. Every property is undetermined for that rule, so nothing is dropped, and the definition
    says so once rather than per property.
    """
    definition = with_rules(
        tmp_path, "brief", "  - {id: no-fiber, when: 'upload_mbps < 100', severity: drop}\n"
    )

    assert blocking(definition.problems()) == ()
    assert len(notices(definition.problems())) == 1
    assert "location enrichment" in notices(definition.problems())[0].message
    assert [rule.id for rule in definition.rules] == ["no-fiber"]


def test_a_definition_with_a_broken_rule_is_not_run(tmp_path: Path) -> None:
    """feat-008/AC-15: nothing is evaluated, and no source is contacted."""
    from homescout import api
    from homescout.search import InvalidSearch
    from homescout.store import Store
    from searches_fakes import Hostile

    with_rules(tmp_path, "bad", "  - {id: broken, when: 'not_a_field > 1', severity: drop}\n")

    with Store.open(tmp_path / "homescout.db") as store:
        workspace = api.Workspace(
            store=store,
            catalog=catalog(tmp_path / "searches"),
            queue=None,
            sources={"fake": Hostile()},
        )
        with pytest.raises(InvalidSearch):
            api.run_search(workspace, "bad")
