from __future__ import annotations

from typing import Any

import pytest

from .test_employer_kit import API, ROSTER_CATEGORIES, build_roster, skills

URL = f"{API}/employer/categories"
SEARCH_URL = f"{API}/employer/search"

STACKS = [
    "backend",
    "frontend",
    "fullstack",
    "mobile",
    "ml",
    "devops",
    "security",
    "embedded",
    "qa",
    "analyst",
]
GRADES = ["intern", "junior", "middle", "senior"]


@pytest.fixture()
def roster(make_candidate) -> dict[str, Any]:
    return build_roster(make_candidate)


def matrix(client, headers, **params: str) -> dict[str, Any]:
    response = client.get(URL, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def search_total(client, headers, **body: Any) -> int:
    response = client.post(SEARCH_URL, json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["total"]


def cell_map(body: dict[str, Any]) -> dict[tuple[str, str], tuple[int, int]]:
    return {(c["stack"], c["grade"]): (c["count"], c["fsp_verified"]) for c in body["cells"]}


# --- the fixture itself --------------------------------------------------------------------------


def test_roster_is_categorized_as_the_tests_expect(roster):
    for name, (stack, grade) in ROSTER_CATEGORIES.items():
        category = roster[name].category
        assert (category["stack"], category["grade"]) == (stack, grade), name
    assert roster["hidden_backend"].visible is False
    assert roster["no_stack"].category["stack"] is None


# --- the matrix ----------------------------------------------------------------------------------


def test_matrix_counts_only_visible_candidates_with_a_stack(client, employer_headers, roster):
    body = matrix(client, employer_headers)

    assert len(roster) == 12
    assert body["total_candidates"] == 10


def test_matrix_cells(client, employer_headers, roster):
    body = matrix(client, employer_headers)

    assert cell_map(body) == {
        ("backend", "junior"): (1, 0),
        ("backend", "middle"): (2, 1),
        ("frontend", "junior"): (1, 0),
        ("fullstack", "middle"): (1, 0),
        ("ml", "senior"): (1, 1),
        ("devops", "junior"): (1, 0),
        ("security", "junior"): (1, 1),
        ("qa", "intern"): (1, 0),
        ("analyst", "junior"): (1, 0),
    }


def test_matrix_cells_are_in_the_official_order(client, employer_headers, roster):
    body = matrix(client, employer_headers)

    keys = [(STACKS.index(c["stack"]), GRADES.index(c["grade"])) for c in body["cells"]]
    assert keys == sorted(keys)


def test_matrix_cells_are_never_empty(client, employer_headers, roster):
    body = matrix(client, employer_headers)

    assert body["cells"]
    assert all(cell["count"] > 0 for cell in body["cells"])
    assert all(cell["fsp_verified"] <= cell["count"] for cell in body["cells"])


def test_matrix_sums_agree(client, employer_headers, roster):
    body = matrix(client, employer_headers)

    total = body["total_candidates"]
    assert sum(cell["count"] for cell in body["cells"]) == total
    assert sum(item["count"] for item in body["by_stack"]) == total
    assert sum(item["count"] for item in body["by_grade"]) == total
    assert sum(item["count"] for item in body["by_team_role"]) == total
    assert sum(cell["fsp_verified"] for cell in body["cells"]) == body["fsp_verified_total"]


def test_matrix_slices(client, employer_headers, roster):
    body = matrix(client, employer_headers)

    assert {i["stack"]: i["count"] for i in body["by_stack"]} == {
        "backend": 3,
        "frontend": 1,
        "fullstack": 1,
        "ml": 1,
        "devops": 1,
        "security": 1,
        "qa": 1,
        "analyst": 1,
    }
    assert {i["grade"]: i["count"] for i in body["by_grade"]} == {
        "intern": 1,
        "junior": 5,
        "middle": 3,
        "senior": 1,
    }
    assert {i["team_role"]: i["count"] for i in body["by_team_role"]} == {
        "developer": 6,
        "researcher": 1,
        "devops": 1,
        "qa": 1,
        "analyst": 1,
    }
    # A candidate with several formats is counted in each; one without formats in none.
    assert {i["work_format"]: i["count"] for i in body["by_work_format"]} == {
        "remote": 4,
        "office": 2,
        "hybrid": 4,
    }
    # By FSP results: a candidate counts once per discipline.
    assert {i["discipline"]: i["count"] for i in body["by_discipline"]} == {
        "algorithmic": 2,
        "product": 1,
        "security": 1,
    }
    assert body["fsp_verified_total"] == 3


def test_matrix_slices_list_only_non_empty_entries(client, employer_headers, roster):
    body = matrix(client, employer_headers)

    for key in ("by_stack", "by_grade", "by_team_role", "by_work_format", "by_discipline"):
        assert all(item["count"] > 0 for item in body[key]), key


def test_matrix_of_an_empty_platform(client, employer_headers):
    body = matrix(client, employer_headers)

    assert body == {
        "total_candidates": 0,
        "cells": [],
        "by_stack": [],
        "by_grade": [],
        "by_team_role": [],
        "by_work_format": [],
        "by_discipline": [],
        "fsp_verified_total": 0,
    }


# --- narrowing -----------------------------------------------------------------------------------


def test_team_role_narrows_the_pool(client, employer_headers, roster):
    body = matrix(client, employer_headers, team_role="researcher")

    assert body["total_candidates"] == 1
    assert cell_map(body) == {("ml", "senior"): (1, 1)}
    assert body["fsp_verified_total"] == 1
    assert [i["discipline"] for i in body["by_discipline"]] == ["algorithmic"]


def test_work_format_narrows_the_pool(client, employer_headers, roster):
    body = matrix(client, employer_headers, work_format="remote")

    # Four who named "remote" and two who named no format at all (they fit any format).
    assert body["total_candidates"] == 6
    assert cell_map(body) == {
        ("backend", "junior"): (1, 0),
        ("backend", "middle"): (1, 1),
        ("frontend", "junior"): (1, 0),
        ("fullstack", "middle"): (1, 0),
        ("devops", "junior"): (1, 0),
        ("qa", "intern"): (1, 0),
    }


def test_both_parameters_narrow_together(client, employer_headers, roster):
    body = matrix(client, employer_headers, team_role="developer", work_format="office")

    # backend_mid and security_fsp work in an office; fullstack_mid named no format.
    assert body["total_candidates"] == 3
    assert {i["stack"]: i["count"] for i in body["by_stack"]} == {
        "backend": 1,
        "fullstack": 1,
        "security": 1,
    }


def test_a_narrowing_that_matches_nobody_gives_an_empty_matrix(client, employer_headers, roster):
    body = matrix(client, employer_headers, team_role="lead")

    assert body["total_candidates"] == 0
    assert body["cells"] == []


@pytest.mark.parametrize("params", [{"team_role": "ceo"}, {"work_format": "moon"}])
def test_unknown_parameter_values_are_rejected(client, employer_headers, assert_error, params):
    response = client.get(URL, params=params, headers=employer_headers)

    assert_error(response, 422, "VALIDATION_ERROR")


# --- the same pool as the search -----------------------------------------------------------------


def test_every_cell_equals_the_search_total(client, employer_headers, roster):
    body = matrix(client, employer_headers)
    cells = cell_map(body)

    for (stack, grade), (count, _) in cells.items():
        total = search_total(client, employer_headers, stacks=[stack], grades=[grade])
        # By the spec a "backend" or "frontend" search also finds fullstack candidates, which
        # the matrix counts in their own row.
        fullstack_count = cells.get(("fullstack", grade), (0, 0))[0]
        extra = fullstack_count if stack in ("backend", "frontend") else 0
        assert total == count + extra, (stack, grade)


def test_the_matrix_total_equals_an_unfiltered_search(client, employer_headers, roster):
    body = matrix(client, employer_headers)

    assert search_total(client, employer_headers) == body["total_candidates"]


@pytest.mark.parametrize(
    ("params", "body"),
    [
        ({"team_role": "developer"}, {"team_roles": ["developer"]}),
        ({"team_role": "researcher"}, {"team_roles": ["researcher"]}),
        ({"work_format": "remote"}, {"work_formats": ["remote"]}),
        ({"work_format": "office"}, {"work_formats": ["office"]}),
        ({"work_format": "hybrid"}, {"work_formats": ["hybrid"]}),
        (
            {"team_role": "developer", "work_format": "hybrid"},
            {"team_roles": ["developer"], "work_formats": ["hybrid"]},
        ),
    ],
)
def test_narrowed_matrix_equals_the_narrowed_search(client, employer_headers, roster, params, body):
    assert (
        matrix(client, employer_headers, **params)["total_candidates"]
        == search_total(client, employer_headers, **body)
    )


# --- who is counted ------------------------------------------------------------------------------


def test_a_candidate_who_hides_the_profile_leaves_the_matrix(client, db, employer_headers, roster):
    roster["frontend_junior"].visible = False
    db.commit()

    body = matrix(client, employer_headers)

    assert body["total_candidates"] == 9
    assert ("frontend", "junior") not in cell_map(body)


def test_a_hidden_candidate_who_returns_is_counted(client, db, employer_headers, roster):
    roster["hidden_backend"].visible = True
    db.commit()

    assert cell_map(matrix(client, employer_headers))[("backend", "junior")] == (2, 0)


def test_a_candidate_whose_category_was_not_computed_is_not_counted(
    client, employer_headers, make_candidate
):
    make_candidate(facts=skills("python", "fastapi", "postgresql"), category=None, visible=True)

    assert matrix(client, employer_headers)["total_candidates"] == 0


# --- access --------------------------------------------------------------------------------------


def test_matrix_needs_a_token(client, assert_error):
    assert_error(client.get(URL), 401, "UNAUTHORIZED")


def test_matrix_is_closed_to_candidates(client, candidate_headers, assert_error):
    assert_error(client.get(URL, headers=candidate_headers), 403, "FORBIDDEN")
