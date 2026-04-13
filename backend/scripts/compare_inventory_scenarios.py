from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from fastapi.testclient import TestClient

from main import app


BASE_INGREDIENTS = [
    "onion",
    "green onion",
    "chicken",
    "beef",
    "egg",
    "salt",
    "sugar",
    "milk",
    "flour",
    "rice",
]

ENHANCED_INGREDIENTS = BASE_INGREDIENTS + ["oil", "yogurt", "cream"]


def _recommend(client: TestClient, ingredients: List[str]) -> List[Dict[str, Any]]:
    payload = {
        "ingredients": ingredients,
        "preferences": {
            "time_limit": 35,
            "spicy": False,
            "lighter": False,
            "cuisine": "any",
        },
    }
    res = client.post("/api/recommend", json=payload)
    if res.status_code != 200:
        raise RuntimeError(f"/api/recommend failed: {res.status_code} {res.text}")
    return list((res.json() or {}).get("recipes", []))


def _pick_recipe_with_missing(recipes: List[Dict[str, Any]]) -> Dict[str, Any]:
    for recipe in recipes:
        if recipe.get("missing_main") or recipe.get("missing_seasoning") or recipe.get("missing_other"):
            return recipe
    if not recipes:
        raise RuntimeError("No recommended recipes")
    return recipes[0]


def _substitutions(client: TestClient, recipe: Dict[str, Any], ingredients: List[str]) -> Dict[str, Any]:
    payload = {
        "recipe_id": recipe["id"],
        "user_ingredients": ingredients,
        "missing_main": recipe.get("missing_main", []),
        "missing_seasoning": recipe.get("missing_seasoning", []),
        "missing_other": recipe.get("missing_other", []),
        "preferences": {
            "time_limit": 35,
            "spicy": False,
            "lighter": False,
            "cuisine": "any",
        },
        "dietary": None,
        "allergies": None,
    }
    res = client.post("/api/substitutions", json=payload)
    if res.status_code != 200:
        raise RuntimeError(f"/api/substitutions failed: {res.status_code} {res.text}")
    return dict(res.json() or {})


def _pick_selected(sub_payload: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, str]]:
    main: Dict[str, str] = {}
    season: Dict[str, str] = {}

    for source, options in (sub_payload.get("main_options", {}) or {}).items():
        if isinstance(options, list) and options:
            candidate = str(options[0].get("to") or "").strip()
            if candidate:
                main[source] = candidate

    for source, groups in (sub_payload.get("seasoning_options", {}) or {}).items():
        if not isinstance(groups, dict):
            continue
        pool = groups.get("similar", []) or groups.get("different", []) or []
        if pool:
            candidate = str(pool[0].get("to") or "").strip()
            if candidate:
                season[source] = candidate

    return main, season


def _run_remix(
    client: TestClient,
    recipe_id: str,
    ingredients: List[str],
    selected_main: Dict[str, str],
    selected_season: Dict[str, str],
) -> Dict[str, Any]:
    payload = {
        "recipe_id": recipe_id,
        "user_ingredients": ingredients,
        "selected_main_subs": selected_main,
        "selected_seasoning_subs": selected_season,
        "preferences": {
            "time_limit": 35,
            "spicy": False,
            "lighter": False,
            "cuisine": "any",
        },
        "dietary": None,
        "allergies": None,
        "debug_v2": False,
    }
    res = client.post("/api/remix", json=payload)
    if res.status_code != 200:
        raise RuntimeError(f"/api/remix failed: {res.status_code} {res.text}")
    return dict(res.json() or {})


def _summarize_subs(sub_payload: Dict[str, Any]) -> Dict[str, Any]:
    main_options = sub_payload.get("main_options", {}) or {}
    season_options = sub_payload.get("seasoning_options", {}) or {}

    def count_main() -> int:
        total = 0
        for options in main_options.values():
            if isinstance(options, list):
                total += len(options)
        return total

    def count_season() -> int:
        total = 0
        for groups in season_options.values():
            if not isinstance(groups, dict):
                continue
            total += len(groups.get("similar", []) or [])
            total += len(groups.get("different", []) or [])
        return total

    return {
        "main_sources": len(main_options),
        "main_candidates": count_main(),
        "seasoning_sources": len(season_options),
        "seasoning_candidates": count_season(),
    }


def run_scenario(client: TestClient, ingredients: List[str]) -> Dict[str, Any]:
    recipes = _recommend(client, ingredients)
    target = _pick_recipe_with_missing(recipes)
    sub_payload = _substitutions(client, target, ingredients)
    selected_main, selected_season = _pick_selected(sub_payload)
    remix = _run_remix(client, target["id"], ingredients, selected_main, selected_season)

    return {
        "recipe_id": target["id"],
        "recipe_title": target.get("title", ""),
        "missing_main": target.get("missing_main", []),
        "missing_seasoning": target.get("missing_seasoning", []),
        "substitution_summary": _summarize_subs(sub_payload),
        "selected_main_subs": selected_main,
        "selected_seasoning_subs": selected_season,
        "remix_changed_steps": remix.get("changed_steps", []),
        "remix_flavor_change_summary": remix.get("flavor_change_summary", ""),
    }


def main() -> None:
    with TestClient(app) as client:
        base = run_scenario(client, BASE_INGREDIENTS)
        enhanced = run_scenario(client, ENHANCED_INGREDIENTS)

    print("\n" + "=" * 76)
    print("BASE INVENTORY RESULT")
    print("=" * 76)
    print(json.dumps(base, ensure_ascii=False, indent=2))

    print("\n" + "=" * 76)
    print("ENHANCED INVENTORY RESULT (+oil, yogurt, cream)")
    print("=" * 76)
    print(json.dumps(enhanced, ensure_ascii=False, indent=2))

    delta = {
        "base_main_candidates": base["substitution_summary"]["main_candidates"],
        "enhanced_main_candidates": enhanced["substitution_summary"]["main_candidates"],
        "base_seasoning_candidates": base["substitution_summary"]["seasoning_candidates"],
        "enhanced_seasoning_candidates": enhanced["substitution_summary"]["seasoning_candidates"],
        "base_selected_count": len(base["selected_main_subs"]) + len(base["selected_seasoning_subs"]),
        "enhanced_selected_count": len(enhanced["selected_main_subs"]) + len(enhanced["selected_seasoning_subs"]),
    }

    print("\n" + "=" * 76)
    print("COMPARISON DELTA")
    print("=" * 76)
    print(json.dumps(delta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
