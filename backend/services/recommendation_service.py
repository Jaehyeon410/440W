from typing import Dict, List, Optional, Set

from ingredient_normalizer_v2 import normalize_ingredient_v2
from recipe_utils import normalize_ingredient, normalize_ingredient_list
from services.ingredient_metadata_service import get_metadata
from services.role_inference_service import build_recipe_context_from_recipe, infer_role_for_ingredient


MAIN_ROLE_BUCKET = {"main_component", "protein_base", "body_provider", "serving_base", "structure"}
SEASONING_ROLE_BUCKET = {
    "flavor_base",
    "flavor_booster",
    "sweetener",
    "acidity_provider",
    "richness",
    "sauce_base",
    "moisture_provider",
    "binder",
    "thickener",
    "emulsifier",
}
PRODUCE_ROLE_BUCKET = {"topping", "garnish", "texture_contrast", "flavor_base", "acidity_provider"}
STARCH_ROLE_BUCKET = {"serving_base", "structure", "binder", "thickener"}

# Metadata categories that genuinely belong in the seasoning bucket.
# Dairy, fat, protein, etc. should NOT be classified as seasoning even if
# their inferred role is flavor_booster / richness / sauce_base.
_SEASONING_CATEGORIES = frozenset({
    "seasoning", "aromatic", "condiment", "sweetener", "liquid",
})


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        key = str(value or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def infer_missing_buckets(
    recipe: Dict,
    missing_list: List[str],
    *,
    allow_generation: bool = True,
) -> Dict[str, List[str]]:
    missing_main: List[str] = []
    missing_seasoning: List[str] = []
    missing_produce: List[str] = []
    missing_starch: List[str] = []
    missing_misc: List[str] = []
    missing_other: List[str] = []

    recipe_context = build_recipe_context_from_recipe(recipe)

    for item in _dedupe(missing_list):
        try:
            normalized_item = normalize_ingredient_v2(item).to_dict()
            role_result = infer_role_for_ingredient(
                normalized_item, recipe_context, allow_generation=allow_generation,
            )
            inferred_role = str(role_result.get("inferred_role") or "").strip().lower()
        except Exception:  # noqa: BLE001
            inferred_role = ""

        if inferred_role in MAIN_ROLE_BUCKET:
            missing_main.append(item)
            continue

        if inferred_role in SEASONING_ROLE_BUCKET:
            # Guard: only truly seasoning-like categories belong here.
            # Dairy/fat/protein items with roles like flavor_booster or
            # richness should go to missing_other, not missing_seasoning.
            meta_cat = (str(get_metadata(item).get("category") or "")).strip().lower()
            if not meta_cat or meta_cat in _SEASONING_CATEGORIES:
                missing_seasoning.append(item)
                continue
            # Fall through to missing_other for non-seasoning categories

        missing_other.append(item)
        if inferred_role in PRODUCE_ROLE_BUCKET:
            missing_produce.append(item)
        elif inferred_role in STARCH_ROLE_BUCKET:
            missing_starch.append(item)
        else:
            missing_misc.append(item)

    return {
        "missing_main": missing_main,
        "missing_seasoning": missing_seasoning,
        "missing_produce": missing_produce,
        "missing_starch": missing_starch,
        "missing_misc": missing_misc,
        "missing_other": missing_other,
    }


_TOP_N_CANDIDATES = 20


def rank_recipes(candidate_recipes: List[Dict], user_ingredient_set: Set[str]) -> List[Dict]:
    # ── Phase 1: fast match-percent scoring (no Gemini / role inference) ──
    scored: List[tuple] = []
    for recipe in candidate_recipes:
        recipe_ingredients_norm = recipe["ingredients_norm"]
        importance = recipe.get("importance_norm") or {}
        if recipe_ingredients_norm:
            matched_weight = 0.0
            total_weight = 0.0
            missing_items: List[str] = []
            for item in recipe_ingredients_norm:
                w = importance.get(item, 1.0)
                total_weight += w
                if item in user_ingredient_set:
                    matched_weight += w
                else:
                    missing_items.append(item)
            match_percent = int(round((matched_weight / total_weight) * 100)) if total_weight > 0 else 0
        else:
            missing_items = []
            match_percent = 0

        scored.append((match_percent, len(missing_items), recipe["title"], recipe, missing_items))

    scored.sort(key=lambda t: (-t[0], t[1], t[2]))
    top_candidates = scored[:_TOP_N_CANDIDATES]

    # ── Phase 2: role inference only for top candidates ──
    ranked_results: List[Dict] = []
    for match_percent, _n_miss, _title, recipe, missing_items in top_candidates:
        missing_buckets = infer_missing_buckets(recipe, missing_items, allow_generation=False)
        missing_main = missing_buckets["missing_main"]
        missing_seasoning = missing_buckets["missing_seasoning"]
        missing_produce = missing_buckets["missing_produce"]
        missing_starch = missing_buckets["missing_starch"]
        missing_misc = missing_buckets["missing_misc"]
        missing_other = missing_buckets["missing_other"]
        total_missing = len(missing_main) + len(missing_seasoning) + len(missing_other)

        ranked_results.append(
            {
                "id": recipe["id"],
                "title": recipe["title"],
                "time_minutes": 0,
                "cook_now": total_missing <= 1,
                "missing_main": missing_main,
                "missing_seasoning": missing_seasoning,
                "missing_produce": missing_produce,
                "missing_starch": missing_starch,
                "missing_misc": missing_misc,
                "missing_other": missing_other,
                "match_percent": match_percent,
            }
        )

    return sorted(
        ranked_results,
        key=lambda item: (
            -item["match_percent"],
            len(item["missing_main"]) + len(item["missing_seasoning"]) + len(item["missing_other"]),
            item["title"],
        ),
    )[:5]


def build_recipe_response(recipe: Dict, user_ingredients: Optional[str]) -> Dict:
    user_ingredient_set = None
    if user_ingredients:
        user_list = [part.strip() for part in user_ingredients.split(",") if part.strip()]
        user_ingredient_set = set(normalize_ingredient_list(user_list))

    raw_items = recipe["ingredients_raw"]
    # Use pre-computed per-raw-item normalizations stored at load time to avoid
    # re-running normalize_ingredient() on every GET /api/recipe/{id} request.
    raw_norm = recipe.get("ingredients_raw_norm") or [normalize_ingredient(item) for item in raw_items]

    if user_ingredient_set is None:
        ingredient_items: List[Dict[str, str]] = [{"name": item, "status": "unknown"} for item in raw_items]
    else:
        ingredient_items = [
            {"name": raw_item, "status": "available" if norm_item in user_ingredient_set else "missing"}
            for raw_item, norm_item in zip(raw_items, raw_norm)
        ]

    if user_ingredient_set is None:
        missing_main: List[str] = []
        missing_seasoning: List[str] = []
        missing_produce: List[str] = []
        missing_starch: List[str] = []
        missing_misc: List[str] = []
        missing_other: List[str] = []
    else:
        missing_items = [item for item in recipe["ingredients_norm"] if item not in user_ingredient_set]
        missing_buckets = infer_missing_buckets(recipe, missing_items, allow_generation=False)
        missing_main = missing_buckets["missing_main"]
        missing_seasoning = missing_buckets["missing_seasoning"]
        missing_produce = missing_buckets["missing_produce"]
        missing_starch = missing_buckets["missing_starch"]
        missing_misc = missing_buckets["missing_misc"]
        missing_other = missing_buckets["missing_other"]

    # Expose per-ingredient importance for frontend validation.
    importance_norm = recipe.get("importance_norm") or {}

    return {
        "id": recipe["id"],
        "title": recipe["title"],
        "ingredients": ingredient_items,
        "steps": recipe["directions"],
        "missing_main": missing_main,
        "missing_seasoning": missing_seasoning,
        "missing_produce": missing_produce,
        "missing_starch": missing_starch,
        "missing_misc": missing_misc,
        "missing_other": missing_other,
        "ingredient_importance": importance_norm,
    }
