from __future__ import annotations

from typing import Any

import pytest

from app import schemas
from app.core.errors import AppError
from app.domain import matcher
from app.services.search import build_query, eligible, load_snapshots

from .test_employer_kit import (
    API,
    add_offer,
    add_vacancy,
    build_candidate,
    build_roster,
    set_offer_status,
    skills,
)

URL = f"{API}/employer/search"

EVERYONE = [
    "alexey",
    "backend_junior",
    "backend_mid",
    "frontend_junior",
    "ml_senior",
    "fullstack_mid",
    "devops_junior",
    "qa_intern",
    "security_fsp",
    "analyst_junior",
]


@pytest.fixture()
def roster(make_candidate) -> dict[str, Any]:
    return build_roster(make_candidate)


def post_search(client, headers, **body: Any):
    return client.post(URL, json=body, headers=headers)


def found(response) -> list[int]:
    assert response.status_code == 200, response.text
    return [item["candidate"]["id"] for item in response.json()["items"]]


def ids_of(roster: dict[str, Any], names: list[str]) -> set[int]:
    return {roster[name].id for name in names}


def query(**fields: Any) -> schemas.MatchQuery:
    return schemas.MatchQuery(**fields)


# --- the loading rules ---------------------------------------------------------------------------


def test_snapshots_are_only_visible_candidates(db, roster):
    snapshots = load_snapshots(db)

    visible = {c.id for name, c in roster.items() if name != "hidden_backend"}
    assert {s.id for s in snapshots} == visible
    assert all(s.visible for s in snapshots)


def test_eligible_drops_candidates_without_a_stack(db, roster):
    snapshots = eligible(load_snapshots(db))

    assert {s.id for s in snapshots} == ids_of(roster, EVERYONE)
    assert all(s.category.stack is not None for s in snapshots)


def test_a_snapshot_is_built_from_the_stored_columns(db, roster):
    snapshot = next(s for s in load_snapshots(db) if s.id == roster["alexey"].id)

    assert snapshot.category.stack == "backend"
    assert snapshot.category.grade == "middle"
    assert len(snapshot.embedding) == 384
    assert snapshot.city == "Казань"
    assert snapshot.salary_expectation == 120_000
    assert snapshot.relocation is False
    assert len(snapshot.facts) == len(roster["alexey"].facts)


def test_a_missing_category_means_not_computed(db, make_candidate):
    make_candidate(
        facts=skills("python", "fastapi"), category=None, work_formats=["remote"], city="Тула"
    )

    snapshot = load_snapshots(db)[0]

    assert snapshot.category.stack is None
    assert snapshot.category.label == "Категория не определена"
    assert snapshot.embedding == []
    assert eligible([snapshot]) == []


def test_a_broken_stored_category_is_recomputed_from_the_facts(db, make_candidate):
    make_candidate(
        facts=skills("python", "fastapi", "postgresql", "docker"),
        category={"stack": "cobol"},
    )

    snapshot = load_snapshots(db)[0]

    assert snapshot.category.stack == "backend"


def test_a_foreign_vector_is_ignored(db, make_candidate):
    make_candidate(embedding=[0.1, 0.2, 0.3])

    assert load_snapshots(db)[0].embedding == []


# --- no filters ----------------------------------------------------------------------------------


def test_an_empty_query_lists_everyone_findable(client, employer_headers, roster):
    response = post_search(client, employer_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"total", "limit", "offset", "items", "parsed_query"}
    assert (body["total"], body["limit"], body["offset"]) == (10, 20, 0)
    assert body["parsed_query"] is None
    assert set(found(response)) == ids_of(roster, EVERYONE)


def test_a_query_with_only_filters_has_no_score(client, employer_headers, roster):
    body = post_search(client, employer_headers, stacks=["backend"]).json()

    assert body["items"]
    for item in body["items"]:
        assert item["score"] is None
        assert item["components"]["skill"] is None
        assert item["components"]["text"] is None


def test_a_query_with_only_filters_is_ordered_by_track_record(client, employer_headers, roster):
    items = post_search(client, employer_headers).json()["items"]

    keys = [
        (-i["components"]["track_record"], -i["components"]["confidence"], i["candidate"]["id"])
        for i in items
    ]
    assert keys == sorted(keys)
    assert items[0]["candidate"]["id"] == roster["ml_senior"].id


def test_hidden_and_stackless_candidates_are_never_found(client, employer_headers, roster):
    found_ids = found(post_search(client, employer_headers, skills_optional=["python", "git"]))

    assert roster["hidden_backend"].id not in found_ids
    assert roster["no_stack"].id not in found_ids


def test_hidden_candidate_is_not_found_by_exact_filters(client, employer_headers, roster):
    response = post_search(
        client, employer_headers, stacks=["backend"], grades=["junior"], city="Москва"
    )

    assert found(response) == [roster["backend_junior"].id]


# --- each filter ---------------------------------------------------------------------------------


FILTER_CASES = [
    pytest.param(
        {"stacks": ["backend"]},
        ["alexey", "backend_junior", "backend_mid", "fullstack_mid"],
        id="backend-includes-fullstack",
    ),
    pytest.param(
        {"stacks": ["frontend"]},
        ["frontend_junior", "fullstack_mid"],
        id="frontend-includes-fullstack",
    ),
    pytest.param({"stacks": ["fullstack"]}, ["fullstack_mid"], id="fullstack-exact"),
    pytest.param({"stacks": ["ml", "devops"]}, ["ml_senior", "devops_junior"], id="two-stacks"),
    pytest.param({"stacks": ["mobile"]}, [], id="stack-nobody-has"),
    pytest.param({"grades": ["middle"]}, ["alexey", "backend_mid", "fullstack_mid"], id="grade"),
    pytest.param({"grades": ["intern", "senior"]}, ["qa_intern", "ml_senior"], id="two-grades"),
    pytest.param({"team_roles": ["researcher"]}, ["ml_senior"], id="team-role"),
    pytest.param({"team_roles": ["devops", "qa"]}, ["devops_junior", "qa_intern"], id="two-roles"),
    pytest.param(
        {"work_formats": ["office"]},
        ["backend_mid", "security_fsp", "fullstack_mid", "qa_intern"],
        id="work-format-office-and-undeclared",
    ),
    pytest.param(
        {"work_formats": ["remote"]},
        [
            "alexey",
            "backend_junior",
            "frontend_junior",
            "devops_junior",
            "fullstack_mid",
            "qa_intern",
        ],
        id="work-format-remote-and-undeclared",
    ),
    pytest.param({"city": "Казань"}, ["alexey", "analyst_junior"], id="city-and-relocation"),
    pytest.param({"city": "  казань "}, ["alexey", "analyst_junior"], id="city-case-and-spaces"),
    pytest.param(
        {"city": "Казань", "work_formats": ["remote"]},
        ["alexey", "backend_junior", "frontend_junior", "devops_junior"],
        id="city-with-remote",
    ),
    pytest.param(
        {"fsp_verified_only": True}, ["alexey", "ml_senior", "security_fsp"], id="fsp-verified-only"
    ),
    pytest.param(
        {"confirmed_only": True},
        ["alexey", "ml_senior", "security_fsp", "devops_junior"],
        id="confirmed-only-adds-a-passed-test",
    ),
    pytest.param({"disciplines": ["security"]}, ["security_fsp"], id="discipline"),
    pytest.param(
        {"disciplines": ["algorithmic"]}, ["alexey", "ml_senior"], id="discipline-algorithmic"
    ),
    pytest.param(
        {"disciplines": ["security", "product"]}, ["security_fsp", "alexey"], id="two-disciplines"
    ),
    pytest.param({"disciplines": ["robotics"]}, [], id="discipline-nobody-has"),
    pytest.param(
        {"salary_max": 100_000},
        [name for name in EVERYONE if name not in ("alexey", "backend_mid")],
        id="salary-max-passes-those-without-expectation",
    ),
    pytest.param(
        {"salary_max": 120_000},
        [name for name in EVERYONE if name != "backend_mid"],
        id="salary-max-is-inclusive",
    ),
    pytest.param(
        {"skills_required": ["python", "docker"], "strict_skills": True},
        ["alexey", "backend_junior"],
        id="strict-skills",
    ),
    pytest.param(
        {"stacks": ["backend"], "grades": ["middle"], "fsp_verified_only": True},
        ["alexey"],
        id="filters-combine",
    ),
]


@pytest.mark.parametrize(("body", "expected"), FILTER_CASES)
def test_filter(client, employer_headers, roster, body, expected):
    response = post_search(client, employer_headers, **body)

    assert set(found(response)) == ids_of(roster, expected)
    assert response.json()["total"] == len(expected)


def test_strict_skills_off_keeps_candidates_without_the_skill(client, employer_headers, roster):
    response = post_search(client, employer_headers, skills_required=["python", "docker"])

    assert set(found(response)) == ids_of(roster, EVERYONE)


def test_a_weak_skill_is_not_enough_for_strict_skills(
    client, employer_headers, roster, make_candidate
):
    # Docker is only a declared skill of this candidate: evidence 0.35 * 0.8 = 0.28 < 0.4.
    weak = build_candidate(
        make_candidate,
        [*skills("python", "fastapi", "postgresql"), *skills("docker", source="self", level=2)],
    )

    strict = post_search(client, employer_headers, skills_required=["docker"], strict_skills=True)
    lenient = post_search(client, employer_headers, skills_required=["docker"])

    assert weak.id not in found(strict)
    assert weak.id in found(lenient)
    assert set(found(strict)) == ids_of(roster, ["alexey", "backend_junior", "devops_junior"])


# --- ranking and the score -----------------------------------------------------------------------


def test_skills_give_a_score_and_order_by_it(client, employer_headers, roster):
    response = post_search(client, employer_headers, skills_required=["python", "docker"])

    items = response.json()["items"]
    scores = [item["score"] for item in items]
    assert all(score is not None for score in scores)
    assert all(0 <= score <= 100 and round(score, 1) == score for score in scores)
    keys = [(-i["score"], -i["components"]["confidence"], i["candidate"]["id"]) for i in items]
    assert keys == sorted(keys)
    # Whoever has python or docker is ahead of whoever has neither.
    owners = [
        "ml_senior",
        "alexey",
        "devops_junior",
        "backend_junior",
        "backend_mid",
        "fullstack_mid",
    ]
    assert {i["candidate"]["id"] for i in items[:6]} == ids_of(roster, owners)
    assert all(i["components"]["skill"] > 0 for i in items[:6])
    assert all(i["components"]["skill"] == 0 for i in items[6:])
    # The strongest python evidence (a passed test) and the best track record come first.
    assert items[0]["candidate"]["id"] == roster["ml_senior"].id


def test_components_stay_within_the_range(client, employer_headers, roster):
    items = post_search(
        client, employer_headers, skills_required=["python"], text="Нужен backend на Python"
    ).json()["items"]

    for item in items:
        components = item["components"]
        assert 0 <= components["skill"] <= 1
        assert 0 <= components["text"] <= 1
        assert 0 <= components["track_record"] <= 1
        assert 0 <= components["confidence"] <= 1
        assert 2 <= len(item["reasons"]) <= 4


def test_missing_and_matched_skills(client, employer_headers, roster):
    items = post_search(
        client, employer_headers, stacks=["backend"], skills_required=["python", "docker"]
    ).json()["items"]

    by_id = {item["candidate"]["id"]: item for item in items}
    junior = by_id[roster["backend_junior"].id]
    assert {m["skill"] for m in junior["matched_skills"]} == {"python", "docker"}
    assert junior["missing_skills"] == []
    middle = by_id[roster["backend_mid"].id]
    assert {m["skill"] for m in middle["matched_skills"]} == {"python"}
    assert middle["missing_skills"] == [{"skill": "docker", "title": "Docker"}]


def test_top_achievements_come_from_the_fsp_results(client, employer_headers, roster):
    items = post_search(client, employer_headers, fsp_verified_only=True).json()["items"]

    alexey = next(i for i in items if i["candidate"]["id"] == roster["alexey"].id)
    assert [a["title"] for a in alexey["top_achievements"]] == [
        "Всероссийская олимпиада",
        "Региональный хакатон",
    ]
    assert alexey["top_achievements"][0] == {
        "title": "Всероссийская олимпиада",
        "level": "national",
        "place": 3,
        "year": 2025,
        "verification": "verified",
    }


def test_the_brief_of_a_match(client, employer_headers, roster):
    response = post_search(
        client, employer_headers, stacks=["backend"], grades=["middle"], fsp_verified_only=True
    )

    brief = response.json()["items"][0]["candidate"]
    assert set(brief) == {
        "id",
        "display_name",
        "city",
        "category",
        "salary_expectation",
        "relocation",
        "fsp_linked",
        "sport_rank",
        "about",
    }
    assert brief["id"] == roster["alexey"].id
    assert brief["display_name"] == "Алексей С."
    assert brief["city"] == "Казань"
    assert brief["salary_expectation"] == 120_000
    assert brief["fsp_linked"] is True
    assert brief["sport_rank"] == "kms"
    assert brief["about"] == "Люблю алгоритмы и backend"
    assert brief["category"]["stack"] == "backend"
    assert brief["category"]["grade"] == "middle"


def test_candidates_without_fsp_have_no_rank(client, employer_headers, roster):
    response = post_search(client, employer_headers, stacks=["frontend"], grades=["junior"])

    brief = response.json()["items"][0]["candidate"]
    assert brief["id"] == roster["frontend_junior"].id
    assert brief["fsp_linked"] is False
    assert brief["sport_rank"] is None


# --- text of the query ---------------------------------------------------------------------------

QUERY_TEXT = "Нужен middle backend: Python, FastAPI и Docker"


def test_text_adds_skills_and_reports_what_it_found(client, employer_headers, roster):
    response = post_search(client, employer_headers, text=QUERY_TEXT)

    body = response.json()
    assert body["parsed_query"] == {
        "skills": ["python", "fastapi", "docker"],
        "stack": "backend",
        "grade": "middle",
    }
    assert body["total"] == 10
    assert all(item["score"] is not None for item in body["items"])
    assert all(item["components"]["text"] is not None for item in body["items"])


def test_skills_from_the_text_work_as_optional_skills(client, employer_headers, roster):
    from_text = post_search(client, employer_headers, text=QUERY_TEXT).json()["items"]
    explicit = post_search(
        client, employer_headers, text=QUERY_TEXT, skills_optional=["python", "fastapi", "docker"]
    ).json()["items"]

    assert from_text == explicit
    junior = next(i for i in from_text if i["candidate"]["id"] == roster["backend_junior"].id)
    assert {m["skill"] for m in junior["matched_skills"]} == {"python", "fastapi", "docker"}
    assert junior["missing_skills"] == []


def test_text_skills_do_not_duplicate_required_ones(client, employer_headers, roster):
    items = post_search(
        client, employer_headers, text="Python и Docker", skills_required=["python"]
    ).json()["items"]

    junior = next(i for i in items if i["candidate"]["id"] == roster["backend_junior"].id)
    skills_seen = [m["skill"] for m in junior["matched_skills"]]
    assert sorted(skills_seen) == ["docker", "python"]


def test_the_text_hint_is_a_hint_and_not_a_filter(client, employer_headers, roster):
    body = post_search(client, employer_headers, text="Ищем senior frontend разработчика").json()

    assert body["parsed_query"]["stack"] == "frontend"
    assert body["parsed_query"]["grade"] == "senior"
    assert body["total"] == 10


def test_a_text_without_skills_still_scores(client, employer_headers, roster):
    body = post_search(client, employer_headers, text="Ищем увлечённого человека").json()

    assert body["parsed_query"] == {"skills": [], "stack": None, "grade": None}
    assert all(item["score"] is not None for item in body["items"])
    assert all(item["components"]["skill"] is None for item in body["items"])


def test_a_blank_text_is_no_text(client, employer_headers, roster):
    body = post_search(client, employer_headers, text="   ").json()

    assert body["parsed_query"] is None
    assert all(item["score"] is None for item in body["items"])


def test_text_ranks_matching_profiles_higher(client, employer_headers, roster):
    response = post_search(client, employer_headers, text="Kubernetes Terraform Ansible DevOps")

    assert found(response)[0] == roster["devops_junior"].id


def test_a_too_long_text_is_rejected(client, employer_headers, assert_error):
    assert_error(post_search(client, employer_headers, text="а" * 2001), 422, "VALIDATION_ERROR")


# --- invalid queries -----------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["skills_required", "skills_optional"])
def test_an_unknown_skill_is_a_validation_error(client, employer_headers, assert_error, field):
    response = post_search(client, employer_headers, **{field: ["python", "cobol"]})

    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert [item["field"] for item in body["details"]["errors"]] == [field]


@pytest.mark.parametrize(
    "body",
    [
        {"stacks": ["cobol"]},
        {"grades": ["guru"]},
        {"team_roles": ["ceo"]},
        {"work_formats": ["moon"]},
        {"disciplines": ["chess"]},
        {"salary_max": "много"},
        {"strict_skills": "maybe"},
        {"vacancy_id": 0},
        {"limit": 0},
        {"limit": 51},
        {"offset": -1},
    ],
)
def test_the_body_is_validated(client, employer_headers, assert_error, body):
    assert_error(post_search(client, employer_headers, **body), 422, "VALIDATION_ERROR")


# --- pagination ----------------------------------------------------------------------------------


def test_pages_are_consecutive_slices_of_one_ordering(client, employer_headers, roster):
    full = found(post_search(client, employer_headers, skills_required=["python"], limit=50))
    pages = []
    for offset in (0, 4, 8, 12):
        response = post_search(
            client, employer_headers, skills_required=["python"], limit=4, offset=offset
        )
        body = response.json()
        assert (body["total"], body["limit"], body["offset"]) == (10, 4, offset)
        pages.append(found(response))

    assert [len(page) for page in pages] == [4, 4, 2, 0]
    assert sum(pages, []) == full
    assert len(set(full)) == len(full) == 10


def test_total_counts_matches_after_filters_not_the_page(client, employer_headers, roster):
    body = post_search(client, employer_headers, stacks=["backend"], limit=1).json()

    assert body["total"] == 4
    assert len(body["items"]) == 1


def test_the_default_limit_is_twenty(client, employer_headers, make_candidate):
    for index in range(22):
        build_candidate(
            make_candidate,
            skills("python", "fastapi", "postgresql"),
            email=f"bulk{index}@example.test",
        )

    body = post_search(client, employer_headers).json()

    assert (body["total"], body["limit"], len(body["items"])) == (22, 20, 20)


def test_the_largest_page_is_fifty(client, employer_headers, make_candidate):
    for index in range(52):
        build_candidate(
            make_candidate,
            skills("python", "fastapi", "postgresql"),
            email=f"bulk{index}@example.test",
        )

    body = post_search(client, employer_headers, limit=50).json()

    assert (body["total"], len(body["items"])) == (52, 50)


def test_offset_up_to_500_is_allowed(client, employer_headers, roster):
    body = post_search(client, employer_headers, offset=500).json()

    assert body["items"] == []
    assert body["total"] == 10


def test_offset_above_500_is_rejected(client, employer_headers, roster, assert_error):
    assert_error(post_search(client, employer_headers, offset=501), 422, "VALIDATION_ERROR")


# --- offer status --------------------------------------------------------------------------------


def test_offer_status_is_the_latest_offer_of_this_employer(
    client, db, employer_user, employer_headers, make_employer, roster
):
    mine = employer_user.employer
    other = make_employer(email="other.company@example.test")
    first = add_vacancy(db, mine, title="Первая")
    second = add_vacancy(db, mine, title="Вторая")
    foreign = add_vacancy(db, other, title="Чужая")
    add_offer(db, mine, roster["alexey"], first, status="declined")
    add_offer(db, mine, roster["alexey"], second, status="sent")
    add_offer(db, mine, roster["backend_mid"], first, status="accepted")
    add_offer(db, other, roster["frontend_junior"], foreign, status="accepted")

    items = post_search(client, employer_headers).json()["items"]

    statuses = {item["candidate"]["id"]: item["offer_status"] for item in items}
    assert statuses[roster["alexey"].id] == "sent"
    assert statuses[roster["backend_mid"].id] == "accepted"
    assert statuses[roster["frontend_junior"].id] is None
    assert statuses[roster["ml_senior"].id] is None


def test_offer_status_changes_with_the_answer(client, db, employer_user, employer_headers, roster):
    vacancy = add_vacancy(db, employer_user.employer)
    offer = add_offer(db, employer_user.employer, roster["alexey"], vacancy)
    filters = {"stacks": ["backend"], "grades": ["middle"], "fsp_verified_only": True}
    response = post_search(client, employer_headers, **filters)
    assert response.json()["items"][0]["offer_status"] == "sent"

    set_offer_status(db, offer, "declined")

    response = post_search(client, employer_headers, **filters)
    assert response.json()["items"][0]["offer_status"] == "declined"


# --- the vacancy ---------------------------------------------------------------------------------


def test_a_vacancy_supplements_the_query(client, db, employer_user, employer_headers, roster):
    vacancy = add_vacancy(
        db,
        employer_user.employer,
        stack="backend",
        grade="middle",
        skills_required=["python"],
        skills_optional=["docker"],
    )

    response = post_search(client, employer_headers, vacancy_id=vacancy.id)

    assert set(found(response)) == ids_of(roster, ["alexey", "backend_mid", "fullstack_mid"])
    assert all(item["score"] is not None for item in response.json()["items"])
    assert response.json()["parsed_query"] is None


def test_fields_of_the_request_win_over_the_vacancy(
    client, db, employer_user, employer_headers, roster
):
    vacancy = add_vacancy(db, employer_user.employer, stack="backend", grade="middle")

    response = post_search(client, employer_headers, vacancy_id=vacancy.id, grades=["junior"])

    assert found(response) == [roster["backend_junior"].id]


def test_the_vacancy_salary_limits_the_expectations(
    client, db, employer_user, employer_headers, roster
):
    vacancy = add_vacancy(
        db, employer_user.employer, stack="backend", grade="middle", salary_to=150_000
    )

    response = post_search(client, employer_headers, vacancy_id=vacancy.id)

    # alexey expects 120 000 and fits; backend_mid expects 200 000 and does not.
    assert set(found(response)) == ids_of(roster, ["alexey", "fullstack_mid"])


def test_the_vacancy_team_role_and_formats_filter(
    client, db, employer_user, employer_headers, roster
):
    vacancy = add_vacancy(
        db,
        employer_user.employer,
        stack="ml",
        grade="senior",
        team_role="researcher",
        work_formats=["hybrid"],
        skills_required=["python"],
    )

    response = post_search(client, employer_headers, vacancy_id=vacancy.id)

    assert found(response) == [roster["ml_senior"].id]


def test_an_inactive_vacancy_still_supplements_a_search(
    client, db, employer_user, employer_headers, roster
):
    vacancy = add_vacancy(db, employer_user.employer, stack="qa", grade="intern", is_active=False)

    response = post_search(client, employer_headers, vacancy_id=vacancy.id)

    assert found(response) == [roster["qa_intern"].id]


def test_a_foreign_vacancy_is_not_found(
    client, db, employer_headers, make_employer, assert_error, roster
):
    foreign = add_vacancy(db, make_employer(email="other.company@example.test"))

    assert_error(post_search(client, employer_headers, vacancy_id=foreign.id), 404, "NOT_FOUND")


def test_a_missing_vacancy_is_not_found(client, employer_headers, assert_error, roster):
    assert_error(post_search(client, employer_headers, vacancy_id=987_654), 404, "NOT_FOUND")


def test_foreign_and_missing_vacancies_look_the_same(
    client, db, employer_headers, make_employer, assert_error, roster
):
    foreign = add_vacancy(db, make_employer(email="other.company@example.test"))

    foreign_response = post_search(client, employer_headers, vacancy_id=foreign.id)
    missing_response = post_search(client, employer_headers, vacancy_id=987_654)

    one = assert_error(foreign_response, 404, "NOT_FOUND")
    two = assert_error(missing_response, 404, "NOT_FOUND")

    assert (one["message"], one["details"]) == (two["message"], two["details"])


# --- build_query: how the request and the vacancy are combined -----------------------------------


def test_build_query_without_a_vacancy(db, employer_user):
    result = build_query(
        db,
        employer_user.employer,
        query(
            stacks=["backend"], skills_required=["python"], strict_skills=True, salary_max=100_000
        ),
    )

    assert result.stacks == ["backend"]
    assert result.skills_required == ["python"]
    assert result.skills_optional == []
    assert result.strict_skills is True
    assert result.salary_max == 100_000
    assert result.text is None


def test_build_query_takes_the_fields_of_the_vacancy(db, employer_user):
    vacancy = add_vacancy(
        db,
        employer_user.employer,
        title="Python-разработчик",
        description="Пишем backend",
        stack="backend",
        grade="junior",
        team_role="developer",
        skills_required=["python", "fastapi"],
        skills_optional=["docker"],
        work_formats=["remote"],
        city="Казань",
        salary_to=180_000,
    )

    result = build_query(db, employer_user.employer, query(vacancy_id=vacancy.id))

    assert result.stacks == ["backend"]
    assert result.grades == ["junior"]
    assert result.team_roles == ["developer"]
    assert result.work_formats == ["remote"]
    assert result.city == "Казань"
    assert result.skills_required == ["python", "fastapi"]
    assert result.skills_optional == ["docker"]
    assert result.salary_max == 180_000
    assert result.text == "Python-разработчик\nПишем backend"


def test_build_query_without_a_vacancy_team_role_leaves_roles_open(db, employer_user):
    vacancy = add_vacancy(db, employer_user.employer, team_role=None)

    result = build_query(db, employer_user.employer, query(vacancy_id=vacancy.id))

    assert result.team_roles == []


def test_build_query_joins_skills_without_duplicates(db, employer_user):
    vacancy = add_vacancy(
        db,
        employer_user.employer,
        skills_required=["python", "fastapi"],
        skills_optional=["docker", "git"],
    )

    result = build_query(
        db,
        employer_user.employer,
        query(
            vacancy_id=vacancy.id,
            skills_required=["fastapi", "sql"],
            skills_optional=["git", "redis", "python"],
        ),
    )

    assert result.skills_required == ["fastapi", "sql", "python"]
    assert result.skills_optional == ["git", "redis", "docker"]


def test_build_query_request_values_win_over_the_vacancy(db, employer_user):
    vacancy = add_vacancy(
        db,
        employer_user.employer,
        stack="backend",
        grade="junior",
        team_role="developer",
        work_formats=["remote"],
        city="Казань",
        salary_to=180_000,
    )

    result = build_query(
        db,
        employer_user.employer,
        query(
            vacancy_id=vacancy.id,
            stacks=["frontend"],
            grades=["senior"],
            team_roles=["lead"],
            work_formats=["office"],
            city="Москва",
            salary_max=250_000,
        ),
    )

    assert result.stacks == ["frontend"]
    assert result.grades == ["senior"]
    assert result.team_roles == ["lead"]
    assert result.work_formats == ["office"]
    assert result.city == "Москва"
    assert result.salary_max == 250_000


def test_build_query_puts_the_request_text_before_the_vacancy_text(db, employer_user):
    vacancy = add_vacancy(db, employer_user.employer, title="Вакансия", description="Описание")

    request = query(vacancy_id=vacancy.id, text="Мой запрос")

    result = build_query(db, employer_user.employer, request)

    assert result.text == "Мой запрос\nВакансия\nОписание"


def test_build_query_adds_skills_of_the_text_to_the_optional_ones(db, employer_user):
    result = build_query(
        db,
        employer_user.employer,
        query(
            text="Нужны Python, Redis и Kafka",
            skills_required=["python"],
            skills_optional=["redis"],
        ),
    )

    assert result.skills_required == ["python"]
    assert result.skills_optional == ["redis", "kafka"]


def test_build_query_takes_skills_from_the_request_text_only(db, employer_user):
    vacancy = add_vacancy(
        db,
        employer_user.employer,
        description="Опыт с Kubernetes приветствуется",
        skills_required=["python"],
    )

    result = build_query(db, employer_user.employer, query(vacancy_id=vacancy.id, text="Docker"))

    assert result.skills_optional == ["docker"]


def test_build_query_rejects_unknown_skills_of_the_request(db, employer_user):
    with pytest.raises(AppError) as error:
        build_query(db, employer_user.employer, query(skills_required=["cobol"]))

    assert (error.value.error_code, error.value.status_code) == ("VALIDATION_ERROR", 422)


def test_build_query_rejects_unknown_skills_of_the_vacancy(db, employer_user):
    vacancy = add_vacancy(db, employer_user.employer, skills_required=["cobol"])

    with pytest.raises(AppError) as error:
        build_query(db, employer_user.employer, query(vacancy_id=vacancy.id))

    assert (error.value.error_code, error.value.status_code) == ("VALIDATION_ERROR", 422)


def test_build_query_refuses_a_foreign_vacancy(db, employer_user, make_employer):
    foreign = add_vacancy(db, make_employer(email="other.company@example.test"))

    with pytest.raises(AppError) as error:
        build_query(db, employer_user.employer, query(vacancy_id=foreign.id))

    assert (error.value.error_code, error.value.status_code) == ("NOT_FOUND", 404)


def test_build_query_result_is_understood_by_the_matcher(db, employer_user, roster):
    vacancy = add_vacancy(db, employer_user.employer, stack="backend", grade="middle")
    domain_query = build_query(db, employer_user.employer, query(vacancy_id=vacancy.id))

    ranked = matcher.rank(domain_query, eligible(load_snapshots(db)))

    expected = ids_of(roster, ["alexey", "backend_mid", "fullstack_mid"])
    assert {r.candidate_id for r in ranked} == expected


# --- access --------------------------------------------------------------------------------------


def test_search_needs_a_token(client, assert_error):
    assert_error(client.post(URL, json={}), 401, "UNAUTHORIZED")


def test_search_is_closed_to_candidates(client, candidate_headers, assert_error):
    assert_error(client.post(URL, json={}, headers=candidate_headers), 403, "FORBIDDEN")
