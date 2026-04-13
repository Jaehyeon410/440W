from __future__ import annotations

import json
import os

import requests


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000")


def _print_result(name: str, response: requests.Response) -> None:
    print(f"{name}: status={response.status_code}")
    if response.headers.get("content-type", "").startswith("application/json"):
        payload = response.json()
        if isinstance(payload, dict):
            print(f"{name}: keys={sorted(payload.keys())}")
        else:
            print(f"{name}: type={type(payload).__name__}")
    else:
        print(f"{name}: body={response.text[:160]}")


def main() -> None:
    recommend_payload = {
        "ingredients": ["salt", "butter", "milk"],
        "preferences": {
            "time_limit": 30,
            "spicy": False,
            "lighter": False,
            "cuisine": "any",
        },
    }
    r0 = requests.post(f"{BASE_URL}/api/recommend", json=recommend_payload, timeout=30)
    _print_result("recommend", r0)

    recipe_id = ""
    if r0.status_code == 200:
        recipes = (r0.json() or {}).get("recipes", [])
        if recipes:
            recipe_id = str(recipes[0].get("id") or "")

    if not recipe_id:
        print("summary:", json.dumps({"error": "No recipe id from /api/recommend"}, ensure_ascii=True))
        return

    r1 = requests.get(f"{BASE_URL}/api/recipe/{recipe_id}", timeout=20)
    _print_result("recipe", r1)

    substitutions_payload = {
        "recipe_id": recipe_id,
        "user_ingredients": ["milk", "butter", "cornstarch", "salt"],
        "missing_main": ["flour"],
        "missing_seasoning": ["pepper"],
        "missing_other": [],
        "preferences": None,
        "dietary": None,
        "allergies": None,
    }
    r2 = requests.post(f"{BASE_URL}/api/substitutions", json=substitutions_payload, timeout=30)
    _print_result("substitutions", r2)

    selected_main_subs = {}
    selected_seasoning_subs = {}
    if r2.status_code == 200:
        sub_json = r2.json() or {}
        main_options = sub_json.get("main_options", {})
        for source, options in main_options.items():
            if isinstance(options, list) and options:
                selected_main_subs[source] = str(options[0].get("to") or "")
                break

        seasoning_options = sub_json.get("seasoning_options", {})
        for source, option_groups in seasoning_options.items():
            if not isinstance(option_groups, dict):
                continue
            similar = option_groups.get("similar", [])
            different = option_groups.get("different", [])
            candidates = similar if similar else different
            if candidates:
                selected_seasoning_subs[source] = str(candidates[0].get("to") or "")
                break

    if not selected_main_subs and not selected_seasoning_subs:
        print("summary:", json.dumps({"error": "No valid substitution options to test remix"}, ensure_ascii=True))
        return

    remix_payload = {
        "recipe_id": recipe_id,
        "user_ingredients": ["milk", "butter", "cornstarch", "salt"],
        "selected_main_subs": selected_main_subs,
        "selected_seasoning_subs": selected_seasoning_subs,
        "preferences": {
            "time_limit": 30,
            "spicy": False,
            "lighter": False,
            "cuisine": "any",
        },
        "dietary": None,
        "allergies": None,
        "debug_v2": False,
    }
    r3 = requests.post(f"{BASE_URL}/api/remix", json=remix_payload, timeout=45)
    _print_result("remix", r3)

    preview_payload = {
        "recipe_id": recipe_id,
        "user_ingredients": ["milk", "butter", "cornstarch", "salt"],
        "selected_main_subs": selected_main_subs,
        "selected_seasoning_subs": selected_seasoning_subs,
    }
    r4 = requests.post(f"{BASE_URL}/api/rewrite-preview", json=preview_payload, timeout=45)
    _print_result("rewrite_preview", r4)

    summary = {
        "recipe_ok": r1.status_code == 200,
        "substitutions_ok": r2.status_code == 200,
        "remix_ok": r3.status_code == 200,
        "rewrite_preview_ok": r4.status_code == 200,
    }
    print("summary:", json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
