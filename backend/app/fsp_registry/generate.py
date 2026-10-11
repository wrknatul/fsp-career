"""Deterministic generator of the fictional FSP registry (SPEC 6.1 and 10).

    python -m app.fsp_registry.generate           # (re)write data/registry.json
    python -m app.fsp_registry.generate --check   # exit 1 if the file is out of date

Everything here is made up: names, birth dates, regions, competition titles and protocol
links. The demo candidate (`FSP-2024-00117`) is written out explicitly, not drawn at random.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

SEED = 42
OUTPUT_PATH = Path(__file__).parent / "data" / "registry.json"
ATHLETES_TOTAL = 24
DEMO_FSP_ID = "FSP-2024-00117"
REGISTRY_LAST_DATE = date(2025, 12, 31)

DISCIPLINES = ("algorithmic", "product", "security", "robotics", "uav")
RANKS = ("third", "second", "first", "kms", "ms")
TEAM_ROLES = ("captain", "backend", "frontend", "ml", "analyst", "designer", "member")

# id, title, discipline, level, kind, format, city, date_start, date_end, participants_total
# (for team competitions `participants_total` is the number of teams). 16 competitions:
# all five disciplines and all five levels are present.
_COMPETITIONS: tuple[tuple[Any, ...], ...] = (
    ("COMP-2023-01", "Открытый кубок «Лисья нора»", "algorithmic", "municipal", "cup",
     "individual", "Ижевск", "2023-02-18", "2023-02-18", 96),
    ("COMP-2023-02", "Первенство Поволжья по алгоритмам", "algorithmic", "regional",
     "junior_championship", "individual", "Самара", "2023-04-08", "2023-04-09", 148),
    ("COMP-2023-03", "Хакатон «Прототип-Урал»", "product", "regional", "festival",
     "team", "Екатеринбург", "2023-05-20", "2023-05-21", 62),
    ("COMP-2023-04", "Кубок защиты «Красная нить»", "security", "regional", "cup",
     "team", "Тула", "2023-06-10", "2023-06-11", 44),
    ("COMP-2023-05", "Чемпионат Сибири по алгоритмам", "algorithmic", "district",
     "championship", "individual", "Новосибирск", "2023-09-23", "2023-09-24", 215),
    ("COMP-2023-06", "Окружной хакатон «Волга-Продукт»", "product", "district",
     "championship", "team", "Нижний Новгород", "2023-10-14", "2023-10-15", 58),
    ("COMP-2023-07", "Кубок робототехники «Стальной жук»", "robotics", "district", "cup",
     "team", "Челябинск", "2023-11-18", "2023-11-19", 37),
    ("COMP-2024-01", "Соревнования БАС «Тихий вектор»", "uav", "regional", "festival",
     "team", "Калуга", "2024-03-16", "2024-03-17", 29),
    ("COMP-2024-02", "Всероссийская олимпиада по алгоритмам «Кремний»", "algorithmic",
     "national", "championship", "individual", "Москва", "2024-04-27", "2024-04-28", 412),
    ("COMP-2024-03", "Всероссийский хакатон «Цифровой горизонт»", "product", "national",
     "championship", "team", "Казань", "2024-06-08", "2024-06-10", 96),
    ("COMP-2024-04", "Чемпионат по защите информации «Нулевой день»", "security", "national",
     "championship", "team", "Санкт-Петербург", "2024-07-20", "2024-07-21", 71),
    ("COMP-2024-05", "Всероссийские соревнования «Сервопривод»", "robotics", "national",
     "championship", "team", "Тверь", "2024-09-14", "2024-09-15", 48),
    ("COMP-2024-06", "Кубок беспилотных систем «Верхний ярус»", "uav", "national", "cup",
     "team", "Краснодар", "2024-10-12", "2024-10-13", 33),
    ("COMP-2025-01", "Международный кубок «Меридиан-Код»", "algorithmic", "international",
     "cup", "individual", "Астана", "2025-03-22", "2025-03-23", 530),
    ("COMP-2025-02", "Международный чемпионат «Квантовый щит»", "security", "international",
     "championship", "team", "Ереван", "2025-05-17", "2025-05-18", 64),
    ("COMP-2025-03", "Хакатон «Кама-Продукт»", "product", "regional", "festival",
     "team", "Пермь", "2025-09-06", "2025-09-07", 41),
)

_COMPETITION_KEYS = (
    "competition_id",
    "title",
    "discipline",
    "level",
    "kind",
    "format",
    "city",
    "date_start",
    "date_end",
    "participants_total",
)
COMPETITIONS: dict[str, dict[str, Any]] = {
    row[0]: dict(zip(_COMPETITION_KEYS, row, strict=True)) for row in _COMPETITIONS
}

REGIONS: tuple[tuple[str, str], ...] = (
    ("Республика Татарстан", "Казань"),
    ("Новосибирская область", "Новосибирск"),
    ("Свердловская область", "Екатеринбург"),
    ("Нижегородская область", "Нижний Новгород"),
    ("Самарская область", "Самара"),
    ("Челябинская область", "Челябинск"),
    ("Краснодарский край", "Краснодар"),
    ("Томская область", "Томск"),
    ("Республика Башкортостан", "Уфа"),
    ("Пермский край", "Пермь"),
    ("Ростовская область", "Ростов-на-Дону"),
    ("Санкт-Петербург", "Санкт-Петербург"),
    ("Москва", "Москва"),
    ("Воронежская область", "Воронеж"),
    ("Красноярский край", "Красноярск"),
    ("Приморский край", "Владивосток"),
)

MALE_FIRST_NAMES = (
    "Андрей", "Борис", "Виктор", "Глеб", "Данил", "Егор", "Илья", "Кирилл", "Лев", "Матвей",
    "Никита", "Олег", "Павел", "Роман", "Святослав", "Тимур", "Фёдор", "Артём", "Денис",
    "Станислав",
)  # fmt: skip
FEMALE_FIRST_NAMES = (
    "Анна", "Вера", "Дарья", "Елена", "Ирина", "Ксения", "Марина", "Полина", "Софья",
    "Татьяна", "Юлия", "Алиса",
)  # fmt: skip
# Surnames in the masculine form; the feminine one is the same stem plus "а".
SURNAMES = (
    "Орлов", "Волков", "Зайцев", "Крылов", "Фролов", "Макаров", "Беляев", "Тихонов",
    "Лебедев", "Ковалёв", "Назаров", "Мартынов", "Сорокин", "Гусев", "Лазарев", "Панов",
    "Рябов", "Ширяев", "Богданов", "Дмитриев", "Захаров", "Комаров", "Носков",
    "Виноградов", "Горбунов", "Мельников", "Лаптев", "Журавлёв", "Исаев", "Кудрявцев",
)  # fmt: skip
# Masculine patronymics; the feminine form replaces the trailing "ич" with "на".
PATRONYMICS = (
    "Андреевич", "Борисович", "Викторович", "Дмитриевич", "Евгеньевич", "Максимович",
    "Николаевич", "Олегович", "Павлович", "Романович", "Сергеевич", "Степанович",
)  # fmt: skip
TEAM_NAMES = (
    "Кофе и Код", "Стек Вызовов", "Горячая Замена", "Тихий Рантайм", "Бинарное Дерево",
    "Сборка Мусора", "Холодный Старт", "Белый Список", "Глубокий Поиск", "Красный Флаг",
    "Мёртвый Код", "Чистый Коммит",
)  # fmt: skip


def _competition(competition_id: str) -> dict[str, Any]:
    return dict(COMPETITIONS[competition_id])


def _finalize_results(fsp_id: str, picks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order picks chronologically and give them ids and protocol links."""
    ordered = sorted(
        picks, key=lambda p: (COMPETITIONS[p["competition_id"]]["date_start"], p["competition_id"])
    )
    results = []
    for number, pick in enumerate(ordered, start=1):
        result_id = f"RES-{fsp_id.removeprefix('FSP-')}-{number}"
        protocol_path = f"{pick['competition_id']}/{result_id}".lower()
        results.append(
            {
                "result_id": result_id,
                "competition": _competition(pick["competition_id"]),
                "place": pick["place"],
                "team_name": pick["team_name"],
                "team_role": pick["team_role"],
                "protocol_url": f"https://fsp.example/protocols/{protocol_path}",
            }
        )
    return results


def _demo_athlete() -> dict[str, Any]:
    """The demo candidate (SPEC section 10), written out explicitly."""
    team = "Нулевой Деплой"
    picks = [
        # 2 national podium results: algorithmic 3rd, product 2nd (captain)
        {"competition_id": "COMP-2024-02", "place": 3, "team_name": None, "team_role": None},
        {"competition_id": "COMP-2024-03", "place": 2, "team_name": team, "team_role": "captain"},
        # 2 federal-district results
        {"competition_id": "COMP-2023-05", "place": 4, "team_name": None, "team_role": None},
        {"competition_id": "COMP-2023-06", "place": 3, "team_name": team, "team_role": "backend"},
        # 2 regional results
        {"competition_id": "COMP-2023-02", "place": 1, "team_name": None, "team_role": None},
        {"competition_id": "COMP-2023-03", "place": 2, "team_name": team, "team_role": "backend"},
    ]
    return {
        "fsp_id": DEMO_FSP_ID,
        "full_name": "Смирнов Алексей Игоревич",
        "birth_date": "2003-05-14",
        "region": "Республика Татарстан",
        "city": "Казань",
        "ranks": [
            {
                "rank": "kms",
                "discipline": "algorithmic",
                "assigned_at": "2024-06-15",
                "order_no": "ORD-2024-0381",
            }
        ],
        "results": _finalize_results(DEMO_FSP_ID, picks),
    }


def _pick_place(rng: random.Random, participants: int) -> int:
    roll = rng.random()
    if roll < 0.30:
        return rng.randint(1, 3)
    if roll < 0.65:
        return rng.randint(4, 10)
    return rng.randint(11, min(participants, 40))


def _make_pick(rng: random.Random, competition_id: str) -> dict[str, Any]:
    competition = COMPETITIONS[competition_id]
    is_team = competition["format"] == "team"
    return {
        "competition_id": competition_id,
        "place": _pick_place(rng, competition["participants_total"]),
        "team_name": rng.choice(TEAM_NAMES) if is_team else None,
        "team_role": rng.choices(TEAM_ROLES, weights=(2, 3, 3, 2, 1, 1, 3))[0] if is_team else None,
    }


def _random_full_name(rng: random.Random, taken: set[str]) -> str:
    while True:
        surname = rng.choice(SURNAMES)
        patronymic = rng.choice(PATRONYMICS)
        if rng.random() < 0.7:
            name = f"{surname} {rng.choice(MALE_FIRST_NAMES)} {patronymic}"
        else:
            female_patronymic = patronymic.removesuffix("ич") + "на"
            name = f"{surname}а {rng.choice(FEMALE_FIRST_NAMES)} {female_patronymic}"
        if name not in taken:
            taken.add(name)
            return name


def _weighted_sample(
    rng: random.Random, items: list[str], weights: list[float], count: int
) -> list[str]:
    items, weights = list(items), list(weights)
    chosen = []
    for _ in range(min(count, len(items))):
        index = rng.choices(range(len(items)), weights=weights)[0]
        chosen.append(items.pop(index))
        weights.pop(index)
    return chosen


def build_registry() -> dict[str, Any]:
    rng = random.Random(SEED)
    competition_ids = list(COMPETITIONS)
    demo = _demo_athlete()
    taken_names = {demo["full_name"]}

    numbers = rng.sample([n for n in range(1, 400) if n != 117], ATHLETES_TOTAL - 1)
    drafts: list[dict[str, Any]] = []
    for index, number in enumerate(numbers):
        main_discipline = rng.choices(DISCIPLINES, weights=(4, 3, 2, 1, 1))[0]
        weights = [3.0 if COMPETITIONS[c]["discipline"] == main_discipline else 1.0
                   for c in competition_ids]  # fmt: skip
        count = rng.choice((1, 2, 2, 3, 3, 4, 5, 6))
        chosen = _weighted_sample(rng, competition_ids, weights, count)
        region, city = rng.choice(REGIONS)
        draft = {
            "index": index,
            "fsp_id": f"FSP-{rng.choice((2022, 2023, 2024, 2025))}-{number:05d}",
            "full_name": _random_full_name(rng, taken_names),
            "birth_date": date(rng.randint(1996, 2007), rng.randint(1, 12), rng.randint(1, 28)),
            "region": region,
            "city": city,
            "main_discipline": main_discipline,
            "picks": [_make_pick(rng, competition_id) for competition_id in chosen],
        }
        drafts.append(draft)

    # Every competition must appear in at least one result, so none is dead weight.
    used = {r["competition"]["competition_id"] for r in demo["results"]}
    used |= {pick["competition_id"] for draft in drafts for pick in draft["picks"]}
    for offset, competition_id in enumerate(c for c in competition_ids if c not in used):
        draft = drafts[offset % len(drafts)]
        draft["picks"].append(_make_pick(rng, competition_id))

    athletes = [demo]
    for draft in drafts:
        results = _finalize_results(draft["fsp_id"], draft["picks"])
        athletes.append(
            {
                "fsp_id": draft["fsp_id"],
                "full_name": draft["full_name"],
                "birth_date": draft["birth_date"].isoformat(),
                "region": draft["region"],
                "city": draft["city"],
                "ranks": _make_ranks(rng, draft, results),
                "results": results,
            }
        )

    registry = {
        "meta": {"fictional": True, "generator": "app.fsp_registry.generate", "seed": SEED},
        "athletes": athletes,
    }
    validate_registry(registry)
    return registry


def _make_ranks(
    rng: random.Random, draft: dict[str, Any], results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    # The first five generated athletes get the five ranks in turn, so every rank exists.
    if draft["index"] < len(RANKS):
        rank = RANKS[draft["index"]]
    elif rng.random() < 0.5:
        rank = rng.choice(RANKS[:3])
    else:
        return []

    discipline = draft["main_discipline"]
    in_discipline = [r for r in results if r["competition"]["discipline"] == discipline]
    base = (in_discipline or results)[0]
    discipline = base["competition"]["discipline"]
    assigned = date.fromisoformat(base["competition"]["date_end"]) + timedelta(
        days=rng.randint(20, 150)
    )
    year = min(assigned, REGISTRY_LAST_DATE).year
    return [
        {
            "rank": rank,
            "discipline": discipline,
            "assigned_at": min(assigned, REGISTRY_LAST_DATE).isoformat(),
            "order_no": f"ORD-{year}-{rng.randint(1, 9999):04d}",
        }
    ]


def validate_registry(registry: dict[str, Any]) -> None:
    athletes = registry["athletes"]
    if len(athletes) != ATHLETES_TOTAL:
        raise ValueError(f"expected {ATHLETES_TOTAL} athletes, got {len(athletes)}")
    ids = [a["fsp_id"] for a in athletes]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate fsp_id")
    names = [a["full_name"] for a in athletes]
    if len(set(names)) != len(names):
        raise ValueError("duplicate full_name")
    result_ids = [r["result_id"] for a in athletes for r in a["results"]]
    if len(set(result_ids)) != len(result_ids):
        raise ValueError("duplicate result_id")

    competitions = {
        r["competition"]["competition_id"]: r["competition"] for a in athletes for r in a["results"]
    }
    if not 14 <= len(competitions) <= 18:
        raise ValueError(f"expected 14-18 competitions, got {len(competitions)}")
    if {c["discipline"] for c in competitions.values()} != set(DISCIPLINES):
        raise ValueError("not all disciplines are present")
    levels = {"municipal", "regional", "district", "national", "international"}
    if {c["level"] for c in competitions.values()} != levels:
        raise ValueError("not all competition levels are present")
    if {rank["rank"] for a in athletes for rank in a["ranks"]} != set(RANKS):
        raise ValueError("not all sport ranks are present")

    for athlete in athletes:
        if not athlete["results"]:
            raise ValueError(f"{athlete['fsp_id']} has no results")
        seen: set[str] = set()
        for result in athlete["results"]:
            competition = result["competition"]
            if competition["competition_id"] in seen:
                raise ValueError(f"{athlete['fsp_id']}: competition repeated")
            seen.add(competition["competition_id"])
            if not 1 <= result["place"] <= competition["participants_total"]:
                raise ValueError(f"{result['result_id']}: place out of range")
            if not result["protocol_url"].startswith("https://fsp.example/protocols/"):
                raise ValueError(f"{result['result_id']}: unexpected protocol url")


def render(registry: dict[str, Any]) -> str:
    return json.dumps(registry, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="do not write, fail if out of date")
    args = parser.parse_args(argv)

    text = render(build_registry())
    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else None
        if current != text:
            print(f"{OUTPUT_PATH} is out of date: run python -m app.fsp_registry.generate")
            return 1
        print(f"{OUTPUT_PATH} is up to date")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    registry = json.loads(text)
    print(f"wrote {OUTPUT_PATH}: {len(registry['athletes'])} athletes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
