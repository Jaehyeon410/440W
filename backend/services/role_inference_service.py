"""Lightweight role-support utilities (refactored).

This module is NO LONGER a required pipeline stage.  It provides:
- RecipeContext dataclass (still used by callers for context passing)
- build_recipe_context / build_recipe_context_from_recipe (still used everywhere)
- soft_role_scores(): returns multi-role soft scores, NOT one authoritative role
- infer_role_for_ingredient(): kept as a thin compatibility wrapper for callers
  that still need the old signature (recommendation_service, remix_service, etc.)

The main substitution pipeline (substitutions_service) no longer calls this.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from services.ingredient_metadata_service import get_metadata


# ---------------------------------------------------------------------------
# Mapping tables (kept for soft scoring and external callers)
# ---------------------------------------------------------------------------

FUNCTION_TO_ROLE = {
    "main_protein": "protein_base",
    "aromatic": "flavor_base",
    "seasoning": "flavor_booster",
    "sauce_base": "sauce_base",
    "flavor_base": "flavor_base",
    "body_provider": "body_provider",
    "fat_source": "richness",
    "acid_source": "acidity_provider",
    "acidity_provider": "acidity_provider",
    "sweetener": "sweetener",
    "binder": "binder",
    "starch_base": "structure",
    "liquid_base": "moisture_provider",
    "garnish": "garnish",
    "fresh_component": "main_component",
    "savory_component": "flavor_booster",
    "bulk_vegetable": "body_provider",
    "structure": "structure",
    "flavor_booster": "flavor_booster",
}

ROLE_VOCABULARY = {
    "main_component",
    "protein_base",
    "serving_base",
    "body_provider",
    "richness",
    "sauce_base",
    "flavor_base",
    "flavor_booster",
    "sweetener",
    "acidity_provider",
    "binder",
    "structure",
    "thickener",
    "coating",
    "emulsifier",
    "aerated_base",
    "topping",
    "garnish",
    "texture_contrast",
    "moisture_provider",
}

CAPABILITY_ROLE_HINTS = {
    "whippable": ["aerated_base"],
    "emulsifier": ["emulsifier"],
    "gelatinizing": ["thickener"],
    "meltable": ["richness", "sauce_base"],
    "caramelizable": ["flavor_booster"],
    "fermentable": ["structure"],
}

ROLE_BEHAVIOR_PROFILE = {
    "binder": {
        "required_capabilities": ["emulsifier"],
        "critical_functions": ["binder", "emulsifier"],
    },
    "thickener": {
        "required_capabilities": ["gelatinizing"],
        "critical_functions": ["thickener", "binder"],
    },
    "aerated_base": {
        "required_capabilities": ["whippable"],
        "critical_functions": ["aerated_base", "body_provider"],
    },
    "structure": {
        "required_capabilities": [],
        "critical_functions": ["structure", "protein_base", "body_provider"],
    },
}



# ---------------------------------------------------------------------------
# RecipeContext (shared across the whole backend)
# ---------------------------------------------------------------------------

@dataclass
class RecipeContext:
    title: str
    normalized_ingredients: List[Dict[str, Any]]
    raw_ingredients: List[str]
    directions: List[str]
    categories: List[str]
    desc: str


@dataclass
class RoleInferenceResult:
    ingredient_raw: str
    canonical: str
    base: str
    candidate_role_scores: Dict[str, float]
    inferred_role: str
    confidence: float
    evidence: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_recipe_context(
    title: str,
    normalized_ingredients: List[Dict[str, Any]],
    raw_ingredients: List[str],
    directions: List[str],
    categories: Optional[List[str]] = None,
    desc: str = "",
) -> RecipeContext:
    return RecipeContext(
        title=(title or "").strip(),
        normalized_ingredients=normalized_ingredients or [],
        raw_ingredients=raw_ingredients or [],
        directions=directions or [],
        categories=categories or [],
        desc=desc or "",
    )


def build_recipe_context_from_recipe(recipe: Dict[str, Any]) -> RecipeContext:
    raw_for_context = recipe.get("parsed_ingredients") or recipe.get("ingredients_raw", [])
    return build_recipe_context(
        title=str(recipe.get("title", "")),
        normalized_ingredients=list(recipe.get("ingredients_v2", [])),
        raw_ingredients=[str(item) for item in raw_for_context],
        directions=[str(step) for step in recipe.get("directions", [])],
        categories=[str(item) for item in recipe.get("categories", [])],
        desc=str(recipe.get("desc", "")),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    return (text or "").strip().lower()


def soft_role_scores(
    normalized_ingredient: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, float]:
    """Return soft scores for ALL plausible roles from metadata only.

    Does NOT pick a winner.  Does NOT use recipe-context patterns.
    Intentionally simple and deterministic.
    """
    primary_fn = _norm(str(metadata.get("primary_function") or ""))
    primary_role = FUNCTION_TO_ROLE.get(primary_fn)
    scores: Dict[str, float] = {}

    for fn in metadata.get("possible_functions", []):
        mapped = FUNCTION_TO_ROLE.get(_norm(str(fn)))
        if mapped:
            scores[mapped] = scores.get(mapped, 0.0) + 0.30

    if primary_role:
        scores[primary_role] = scores.get(primary_role, 0.0) + 0.25

    for cap in metadata.get("special_capabilities", []):
        for role in CAPABILITY_ROLE_HINTS.get(str(cap), []):
            scores[role] = scores.get(role, 0.0) + 0.15

    if not scores:
        scores["main_component"] = 0.2

    return scores


# ---------------------------------------------------------------------------
# Compatibility wrapper: infer_role_for_ingredient
# Used by: recommendation_service, remix_service, rewrite_preview_service,
#          shadow_pipeline, debug scripts.
# ---------------------------------------------------------------------------

def infer_role_for_ingredient(
    normalized_ingredient: Dict[str, Any],
    recipe_context: RecipeContext,
    *,
    allow_generation: bool = True,
) -> Dict[str, Any]:
    """Thin compatibility wrapper.  Picks the top role from soft_role_scores.

    External callers (recommendation_service, remix_service) still depend
    on this signature.  The main substitution pipeline no longer uses it.
    """
    canonical = _norm(str(normalized_ingredient.get("canonical", "")))
    base = _norm(str(normalized_ingredient.get("base", "")))
    metadata = (
        get_metadata(canonical, allow_generation=allow_generation)
        if canonical
        else get_metadata(base, allow_generation=allow_generation)
    )
    if not metadata.get("possible_functions") and canonical and base and canonical != base:
        metadata = get_metadata(base, allow_generation=allow_generation)

    scores = soft_role_scores(normalized_ingredient, metadata)

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    inferred_role = ranked[0][0] if ranked else "main_component"
    top_score = ranked[0][1] if ranked else 0.2
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = max(0.0, top_score - second_score)
    confidence = max(0.25, min(0.95, round(top_score * 0.7 + margin * 0.3, 2)))

    # Protein safety override
    protein_tokens = {
        "chicken", "beef", "pork", "turkey", "shrimp", "fish",
        "tofu", "lamb", "ham", "bacon", "sausage",
    }
    meta_functions = {_norm(str(x)) for x in metadata.get("possible_functions", [])}
    is_protein_like = (
        base in protein_tokens
        or bool(set(canonical.split()) & protein_tokens)
        or "main_protein" in meta_functions
    )
    if is_protein_like and inferred_role in {"structure", "serving_base", "body_provider"}:
        inferred_role = "protein_base"
        confidence = max(confidence, 0.55)

    result = RoleInferenceResult(
        ingredient_raw=str(normalized_ingredient.get("raw", "")),
        canonical=canonical,
        base=base,
        candidate_role_scores=scores,
        inferred_role=inferred_role,
        confidence=confidence,
        evidence=["soft_role_scores"],
    )
    out = result.to_dict()
    out["role_behavior_profile"] = ROLE_BEHAVIOR_PROFILE.get(
        inferred_role,
        {"required_capabilities": [], "critical_functions": [inferred_role]},
    )
    return out


def infer_roles_for_recipe(
    normalized_ingredients: List[Dict[str, Any]],
    recipe_context: RecipeContext,
) -> List[Dict[str, Any]]:
    """Infer roles for all ingredients in a recipe."""
    return [
        infer_role_for_ingredient(ing, recipe_context)
        for ing in normalized_ingredients
        if isinstance(ing, dict)
    ]
