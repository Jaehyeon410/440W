from __future__ import annotations

import json
from typing import Any, Dict, List

from fastapi.testclient import TestClient

from main import app


USER_INGREDIENTS = [
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


def _print_json(title: str, payload: Any, max_len: int = 1800) -> None:
    print("\n" + "=" * 76)
    print(title)
    print("=" * 76)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(text) > max_len:
        print(text[:max_len] + "\n... (truncated)")
    else:
        print(text)


def _pick_substitutions(sub_payload: Dict[str, Any]) -> tuple[Dict[str, str], Dict[str, str]]:
    selected_main: Dict[str, str] = {}
    selected_seasoning: Dict[str, str] = {}

    main_options = sub_payload.get("main_options", {})
    for source, candidates in main_options.items():
        if isinstance(candidates, list) and candidates:
            first = candidates[0]
            candidate = str(first.get("to") or "").strip()
            if candidate:
                selected_main[source] = candidate
        if len(selected_main) >= 2:
            break

    seasoning_options = sub_payload.get("seasoning_options", {})
    for source, groups in seasoning_options.items():
        if not isinstance(groups, dict):
            continue
        pool = groups.get("similar", []) or groups.get("different", []) or []
        if pool:
            first = pool[0]
            candidate = str(first.get("to") or "").strip()
            if candidate:
                selected_seasoning[source] = candidate
        if len(selected_seasoning) >= 2:
            break

    return selected_main, selected_seasoning


def main() -> None:
    with TestClient(app) as client:
        recommend_req = {
            "ingredients": USER_INGREDIENTS,
            "preferences": {
                "time_limit": 35,
                "spicy": False,
                "lighter": False,
                "cuisine": "any",
            },
        }

        rec_res = client.post("/api/recommend", json=recommend_req)
        if rec_res.status_code != 200:
            raise RuntimeError(f"/api/recommend failed: {rec_res.status_code} {rec_res.text}")

        recipes = rec_res.json().get("recipes", [])
        if not recipes:
            raise RuntimeError("No recommended recipes returned")

        top_recipe = None
        recipe_detail = None
        sub_payload = None

        for recipe in recipes[:12]:
            candidate_id = str(recipe.get("id") or "")
            if not candidate_id:
                continue

            candidate_recipe_res = client.get(
                f"/api/recipe/{candidate_id}",
                params={"user_ingredients": ",".join(USER_INGREDIENTS)},
            )
            if candidate_recipe_res.status_code != 200:
                continue

            candidate_detail = candidate_recipe_res.json()
            candidate_sub_req = {
                "recipe_id": candidate_id,
                "user_ingredients": USER_INGREDIENTS,
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
            candidate_sub_res = client.post("/api/substitutions", json=candidate_sub_req)
            if candidate_sub_res.status_code != 200:
                continue

            candidate_sub_payload = candidate_sub_res.json()
            selected_main, selected_seasoning = _pick_substitutions(candidate_sub_payload)
            if selected_main or selected_seasoning:
                top_recipe = recipe
                recipe_detail = candidate_detail
                sub_payload = candidate_sub_payload
                break

            if top_recipe is None:
                # Keep a fallback candidate even if substitutions are empty.
                top_recipe = recipe
                recipe_detail = candidate_detail
                sub_payload = candidate_sub_payload

        if top_recipe is None or recipe_detail is None or sub_payload is None:
            raise RuntimeError("Failed to build a recipe + substitutions candidate")

        recipe_id = str(top_recipe.get("id") or "")
        _print_json("Chosen Recommendation", top_recipe)
        _print_json("Recipe Detail", recipe_detail)

        _print_json("Substitution Suggestions", sub_payload)

        selected_main, selected_seasoning = _pick_substitutions(sub_payload)
        _print_json(
            "Selected Substitutions",
            {
                "selected_main_subs": selected_main,
                "selected_seasoning_subs": selected_seasoning,
            },
        )

        remix_req = {
            "recipe_id": recipe_id,
            "user_ingredients": USER_INGREDIENTS,
            "selected_main_subs": selected_main,
            "selected_seasoning_subs": selected_seasoning,
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

        remix_res = client.post("/api/remix", json=remix_req)
        if remix_res.status_code != 200:
            raise RuntimeError(f"/api/remix failed: {remix_res.status_code} {remix_res.text}")

        remix_payload = remix_res.json()
        _print_json("Remix Result", remix_payload, max_len=3200)

        print("\nsummary:")
        print(json.dumps({
            "recipe_id": recipe_id,
            "main_sub_count": len(selected_main),
            "seasoning_sub_count": len(selected_seasoning),
            "changed_steps": remix_payload.get("changed_steps", []),
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
