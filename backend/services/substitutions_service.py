from typing import Dict, List, Tuple

from api.schemas import SubstitutionsRequest
from ingredient_normalizer_v2 import normalize_ingredient_v2
from recipe_utils import normalize_ingredient
from services.role_inference_service import build_recipe_context_from_recipe, infer_role_for_ingredient
from services.substitute_generation_service import generate_substitute_candidates
from services.substitute_ranking_service import rank_substitute_candidates


PRODUCE_LIKE_ROLES = {"topping", "garnish", "texture_contrast", "flavor_base", "acidity_provider"}
STARCH_LIKE_ROLES = {"serving_base", "structure", "binder", "thickener"}


def _normalize_key(text: str) -> str:
    return normalize_ingredient(text or "").strip().lower()


def _role_category(inferred_role: str) -> str:
    role = str(inferred_role or "").strip().lower()
    if role in PRODUCE_LIKE_ROLES:
        return "produce"
    if role in STARCH_LIKE_ROLES:
        return "starch"
    return "misc"


def _build_ranked_candidates_for_item(
    item: str,
    recipe_context,
    user_ingredients: List[str],
) -> Tuple[str, List[Dict], str]:
    source_key = _normalize_key(item)
    try:
        normalized_item = normalize_ingredient_v2(item).to_dict()
        role_result = infer_role_for_ingredient(normalized_item, recipe_context)
        inferred_role = str(role_result.get("inferred_role") or "")
        normalized_item["inferred_role"] = inferred_role
        normalized_item["role_confidence"] = float(role_result.get("confidence") or 0.0)

        step4 = generate_substitute_candidates(
            normalized_item,
            recipe_context,
            user_inventory=list(user_ingredients or []),
            inventory_only=True,
        )
        step5 = rank_substitute_candidates(step4, recipe_context=recipe_context)
    except Exception:  # noqa: BLE001
        return source_key, [], ""

    mapped = []
    for row in step5.get("ranked_candidates", []):
        mapped.append(
            {
                "to": str(row.get("candidate") or ""),
                "reason": (
                    f"role={row.get('inferred_role', '')}, "
                    f"tier={row.get('recommendation_tier', 'acceptable')}, "
                    f"score={float(row.get('rank_score', 0.0)):.2f}, "
                    f"confidence={float(row.get('confidence', 0.0)):.2f}"
                ),
                "quality_band": str(row.get("quality_band") or ""),
                "recommendation_tier": str(row.get("recommendation_tier") or "acceptable"),
                "rank_score": float(row.get("rank_score") or 0.0),
                "confidence": float(row.get("confidence") or 0.0),
            }
        )

    return source_key, mapped, inferred_role


def _build_v2_ranked_options(
    missing_items: List[str],
    recipe: Dict,
    user_ingredients: List[str],
) -> Tuple[Dict[str, List[Dict]], Dict[str, str]]:
    recipe_context = build_recipe_context_from_recipe(recipe)
    options: Dict[str, List[Dict]] = {}
    role_map: Dict[str, str] = {}

    for item in missing_items:
        source_key, mapped, inferred_role = _build_ranked_candidates_for_item(item, recipe_context, user_ingredients)
        options[source_key] = mapped
        role_map[source_key] = inferred_role

    return options, role_map


def _build_v2_seasoning_options(
    missing_items: List[str],
    recipe: Dict,
    user_ingredients: List[str],
) -> Dict[str, Dict[str, List[Dict]]]:
    # Keep existing response shape: {source: {similar: [...], different: [...]}}
    ranked_options, _ = _build_v2_ranked_options(missing_items, recipe, user_ingredients)
    out: Dict[str, Dict[str, List[Dict]]] = {}
    for source, candidates in ranked_options.items():
        similar = [item for item in candidates if item.get("recommendation_tier") in {"best", "acceptable"}]
        out[source] = {
            "similar": similar,
            "different": [],
        }
    return out


def _build_other_options_and_notes(
    missing_items: List[str],
    recipe: Dict,
    user_ingredients: List[str],
) -> Tuple[Dict[str, Dict], Dict[str, str]]:
    ranked_options, role_map = _build_v2_ranked_options(missing_items, recipe, user_ingredients)

    other_options: Dict[str, Dict] = {}
    other_notes: Dict[str, str] = {}

    for source, suggested in ranked_options.items():
        inferred_role = role_map.get(source, "")
        category = _role_category(inferred_role)

        other_options[source] = {
            "category": category,
            "suggested": suggested,
            "fallback_actions": ["skip", "add_to_shopping_list"],
        }

        if suggested:
            other_notes[source] = (
                f"Role-inferred as {inferred_role or 'other'} ({category}). "
                "Try one of the suggested pantry substitutes."
            )
        else:
            other_notes[source] = (
                f"Role-inferred as {inferred_role or 'other'} ({category}), "
                "but no matching pantry substitute was found."
            )

    return other_options, other_notes


def build_substitutions_response(
    payload: SubstitutionsRequest,
    recipe: Dict,
) -> Dict:
    # v2 recommendation path: role inference + generation + ranking with
    # weak/reject candidates filtered out in ranking layer.
    main_options, _ = _build_v2_ranked_options(
        payload.missing_main,
        recipe,
        payload.user_ingredients,
    )
    seasoning_options = _build_v2_seasoning_options(
        payload.missing_seasoning,
        recipe,
        payload.user_ingredients,
    )
    other_options, other_notes = _build_other_options_and_notes(
        payload.missing_other,
        recipe,
        payload.user_ingredients,
    )

    return {
        "main_options": main_options,
        "seasoning_options": seasoning_options,
        "other_options": other_options,
        "other_notes": other_notes,
    }
