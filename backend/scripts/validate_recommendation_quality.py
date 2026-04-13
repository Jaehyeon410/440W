from __future__ import annotations

import json
from typing import Any, Dict, List

from ingredient_normalizer_v2 import normalize_ingredient_v2
from services.role_inference_service import build_recipe_context
from services.substitute_generation_service import generate_substitute_candidates
from services.substitute_ranking_service import rank_substitute_candidates


LEGACY_WEIGHTS = {
    "role_fit": 0.28,
    "function_overlap": 0.18,
    "texture_similarity": 0.16,
    "property_similarity": 0.14,
    "capability_match": 0.12,
    "context_fit": 0.08,
    "inventory_bonus": 0.04,
}


def _legacy_score(row: Dict[str, Any]) -> float:
    fs = row.get("feature_scores", {})
    weighted_sum = (
        (LEGACY_WEIGHTS["role_fit"] * float(fs.get("role_fit", 0.0)))
        + (LEGACY_WEIGHTS["function_overlap"] * float(fs.get("function_overlap", 0.0)))
        + (LEGACY_WEIGHTS["texture_similarity"] * float(fs.get("texture_similarity", 0.0)))
        + (LEGACY_WEIGHTS["property_similarity"] * float(fs.get("property_similarity", 0.0)))
        + (LEGACY_WEIGHTS["capability_match"] * float(fs.get("capability_match", 0.0)))
        + (LEGACY_WEIGHTS["context_fit"] * float(fs.get("context_fit", 0.0)))
        + (LEGACY_WEIGHTS["inventory_bonus"] * float(fs.get("inventory_bonus", 0.0)))
    )
    penalties = float(fs.get("same_family_penalty", 0.0)) + float(fs.get("weak_candidate_penalty", 0.0))
    return max(0.0, min(0.99, round(weighted_sum - penalties, 4)))


def _print_case(name: str, ranked_result: Dict[str, Any]) -> None:
    print("\n" + "=" * 76)
    print(name)
    print("=" * 76)

    before = int(ranked_result.get("candidate_count_before_filter", 0))
    after = int(ranked_result.get("candidate_count_after_filter", 0))
    dropped = int(ranked_result.get("not_recommended_count", 0))
    print(f"candidates: before={before}, after={after}, dropped={dropped}")

    ranked = ranked_result.get("ranked_candidates", [])
    if not ranked:
        print("No acceptable substitutes found (substitute 없음).")
        return

    print("top recommendations:")
    for row in ranked[:5]:
        legacy = _legacy_score(row)
        print(
            "-"
            f" {row.get('candidate')}"
            f" | legacy_score={legacy:.3f}"
            f" | new_score={float(row.get('rank_score', 0.0)):.3f}"
            f" | tier={row.get('recommendation_tier')}"
            f" | quality={row.get('quality_band')}"
            f" | conf={float(row.get('confidence', 0.0)):.2f}"
        )


def _run_one(
    source: str,
    inventory: List[str],
    title: str,
    directions: List[str],
    categories: List[str],
) -> Dict[str, Any]:
    recipe_context = build_recipe_context(
        title=title,
        normalized_ingredients=[],
        raw_ingredients=[source],
        directions=directions,
        categories=categories,
        desc="",
    )

    source_norm = normalize_ingredient_v2(source).to_dict()
    step4 = generate_substitute_candidates(
        source_norm,
        recipe_context,
        user_inventory=inventory,
        inventory_only=True,
    )
    return rank_substitute_candidates(step4, recipe_context=recipe_context)


def main() -> None:
    cases = [
        {
            "name": "Case 1: thickener quality (flour)",
            "source": "flour",
            "inventory": ["cornstarch", "potato starch", "broth", "water", "milk"],
            "title": "Simple Gravy",
            "directions": [
                "Melt butter and whisk in flour.",
                "Add broth and simmer until thickened.",
            ],
            "categories": ["sauce"],
        },
        {
            "name": "Case 2: aerated_base quality (cream)",
            "source": "cream",
            "inventory": ["milk", "yogurt", "water", "broth", "heavy cream"],
            "title": "Whipped Topping",
            "directions": [
                "Whip cream until soft peaks form.",
                "Serve immediately.",
            ],
            "categories": ["dessert"],
        },
        {
            "name": "Case 3: structure quality (flour, low-support inventory)",
            "source": "flour",
            "inventory": ["broth", "water", "vinegar"],
            "title": "Flatbread Dough",
            "directions": [
                "Mix flour with water to form dough.",
                "Knead and rest the dough.",
            ],
            "categories": ["bread"],
        },
    ]

    failures = 0
    for case in cases:
        try:
            result = _run_one(
                source=case["source"],
                inventory=case["inventory"],
                title=case["title"],
                directions=case["directions"],
                categories=case["categories"],
            )
            _print_case(case["name"], result)

            # Core quality assertions:
            for row in result.get("ranked_candidates", []):
                assert row.get("quality_band") not in {"weak_option", "reject"}
                assert row.get("recommendation_tier") in {"best", "acceptable"}

            if case["name"].startswith("Case 3"):
                assert len(result.get("ranked_candidates", [])) == 0

        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"FAIL: {case['name']} -> {exc}")

    print("\nsummary:")
    print(json.dumps({"total": len(cases), "failed": failures, "passed": len(cases) - failures}, indent=2))


if __name__ == "__main__":
    main()
