"""Rule-based role inference service (Step 3).

This module infers ingredient roles in a specific recipe context using:
- Step 1 normalized ingredient V2 fields
- Step 2 ingredient metadata
- recipe directions/title/categories cues
- quantity/unit clues

It is intentionally additive and shadow-mode friendly.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from services.ingredient_metadata_service import get_metadata


FUNCTION_TO_ROLE = {
    "main_protein": "protein_base",
    "aromatic": "flavor_base",
    "seasoning": "flavor_booster",
    "sauce_base": "sauce_base",
    "flavor_base": "flavor_base",
    "body_provider": "body_provider",
    "fat_source": "richness",
    "acid_source": "acidity_provider",
    "sweetener": "sweetener",
    "binder": "binder",
    "starch_base": "structure",
    "liquid_base": "moisture_provider",
    "garnish": "garnish",
    "fresh_component": "main_component",
    "savory_component": "flavor_booster",
    "bulk_vegetable": "body_provider",
    "structure": "structure",
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

ROLE_PATTERNS = {
    "aerated_base": ["whip", "beating", "beat", "soft peaks", "stiff peaks", "foamy", "thickened"],
    "topping": ["top with", "topped", "sprinkle", "finish with", "garnish"],
    "garnish": ["garnish", "serve with", "finish with"],
    "texture_contrast": ["sprinkle", "crunch", "toasted", "top with"],
    "structure": ["knead", "dough", "rise", "proof", "loaf", "bread", "pizza"],
    "thickener": ["thicken", "thickened", "slurry", "whisk in", "gravy", "reduce", "simmer until"],
    "coating": ["coat", "dredge", "bread", "crust"],
    "sauce_base": ["sauce", "gravy", "whisk in", "simmer", "reduce"],
    "flavor_base": ["saute", "sweat", "cook onion", "cook garlic", "aromatic", "base"],
    "sweetener": ["sweeten", "sugar", "honey", "syrup", "beat with sugar"],
    "acidity_provider": ["vinaigrette", "dressing", "marinate", "acid", "lemon juice", "vinegar"],
    "binder": ["bind", "hold together", "mix with egg"],
    "emulsifier": ["emulsify", "whisk", "dressing", "mayonnaise"],
    "moisture_provider": ["broth", "stock", "water", "milk", "add liquid"],
    "body_provider": ["fold in", "mix in", "stir in", "combine"],
    "main_component": ["arrange", "serve", "roast", "grill", "main"],
    "serving_base": ["serve over", "on top of", "bed of", "base"],
    "richness": ["rich", "buttery", "cream", "finish with butter"],
    "flavor_booster": ["season", "boost", "extract", "zest", "spice"],
}

TITLE_HINTS = {
    "structure": ["bread", "loaf", "dough", "pizza"],
    "thickener": ["gravy", "roux", "sauce", "soup"],
    "sauce_base": ["sauce", "gravy", "soup", "stew"],
    "aerated_base": ["whipped", "mousse", "cream"],
    "acidity_provider": ["dressing", "vinaigrette", "marinade"],
    "topping": ["topping", "garnish", "salad"],
}

SMALL_UNITS = {"tsp", "tbsp"}
LARGE_UNITS = {"cup", "lb", "kg", "l"}


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
    # Use pre-computed parsed_ingredients (equipment lines and noise already removed)
    # so role inference and nearby-ingredient context are not polluted by metadata rows.
    # Falls back to ingredients_raw for backward compatibility with older recipe dicts.
    raw_for_context = recipe.get("parsed_ingredients") or recipe.get("ingredients_raw", [])
    return build_recipe_context(
        title=str(recipe.get("title", "")),
        normalized_ingredients=list(recipe.get("ingredients_v2", [])),
        raw_ingredients=[str(item) for item in raw_for_context],
        directions=[str(step) for step in recipe.get("directions", [])],
        categories=[str(item) for item in recipe.get("categories", [])],
        desc=str(recipe.get("desc", "")),
    )


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def _text_contains_any(text: str, patterns: List[str]) -> bool:
    lowered = _norm(text)
    return any(pattern in lowered for pattern in patterns)


def _ingredient_tokens(normalized_ingredient: Dict[str, Any]) -> List[str]:
    tokens: List[str] = []
    for key in ["canonical", "base", "raw"]:
        value = _norm(str(normalized_ingredient.get(key, "")))
        if not value:
            continue
        tokens.extend(value.split())
        tokens.append(value)
    return [token for token in tokens if token]


def _mentioned_in_step(normalized_ingredient: Dict[str, Any], step_text: str) -> bool:
    step = _norm(step_text)
    for token in _ingredient_tokens(normalized_ingredient):
        # Phrase tokens are matched as plain substring; single words use word boundaries
        # to avoid false positives like "oil" matching "boil".
        if " " in token:
            if token in step:
                return True
            continue

        if len(token) <= 2:
            continue

        if re.search(rf"\b{re.escape(token)}\b", step):
            return True
    return False


def _collect_step_matches(
    normalized_ingredient: Dict[str, Any],
    recipe_context: RecipeContext,
) -> List[Tuple[int, str]]:
    matches: List[Tuple[int, str]] = []
    for idx, step in enumerate(recipe_context.directions):
        if _mentioned_in_step(normalized_ingredient, step):
            matches.append((idx, _norm(step)))
    return matches


def _candidate_roles_from_metadata(
    metadata: Dict[str, Any],
) -> List[str]:
    primary_function = str(metadata.get("primary_function") or "").strip().lower()
    if primary_function in FUNCTION_TO_ROLE:
        roles = [FUNCTION_TO_ROLE[primary_function]]
    else:
        roles = []

    for fn in metadata.get("possible_functions", []):
        mapped = FUNCTION_TO_ROLE.get(str(fn).strip().lower())
        if mapped:
            roles.append(mapped)

    roles = [
        *roles,
        *[
            role
        for role in metadata.get("possible_functions", [])
        if isinstance(role, str) and role in ROLE_VOCABULARY
        ],
    ]

    for capability in metadata.get("special_capabilities", []):
        for hinted_role in CAPABILITY_ROLE_HINTS.get(str(capability), []):
            if hinted_role in ROLE_VOCABULARY:
                roles.append(hinted_role)

    # Safe generic fallbacks when metadata is sparse.
    properties = metadata.get("properties", {})
    texture = str(metadata.get("texture", ""))
    if not roles:
        if properties.get("acidity") == "high":
            roles.append("acidity_provider")
        if properties.get("sweetness") == "high":
            roles.append("sweetener")
        if texture in {"powder", "paste"}:
            roles.append("thickener")
        if texture == "liquid":
            roles.append("moisture_provider")

    if not roles:
        roles.append("main_component")

    deduped: List[str] = []
    seen = set()
    for role in roles:
        if role not in seen:
            seen.add(role)
            deduped.append(role)
    return deduped


def _score_with_direction_patterns(
    candidate_scores: Dict[str, float],
    normalized_ingredient: Dict[str, Any],
    recipe_context: RecipeContext,
    evidence: List[str],
) -> None:
    matches = _collect_step_matches(normalized_ingredient, recipe_context)
    if not matches:
        return

    direction_count = max(1, len(recipe_context.directions))
    for idx, step in matches:
        late_step = idx >= direction_count - 2

        for role, patterns in ROLE_PATTERNS.items():
            if role not in candidate_scores:
                continue
            if _text_contains_any(step, patterns):
                candidate_scores[role] += 0.25
                evidence.append(f"step cue '{role}' matched in step {idx + 1}")

        if late_step:
            for role in ["topping", "garnish", "texture_contrast"]:
                if role in candidate_scores:
                    candidate_scores[role] += 0.12
            evidence.append("appears in late step; topping/garnish roles boosted")


def _score_with_title_and_categories(
    candidate_scores: Dict[str, float],
    recipe_context: RecipeContext,
    evidence: List[str],
) -> None:
    recipe_text = " ".join([recipe_context.title, recipe_context.desc, *recipe_context.categories]).lower()
    for role, hints in TITLE_HINTS.items():
        if role in candidate_scores and _text_contains_any(recipe_text, hints):
            candidate_scores[role] += 0.2
            evidence.append(f"title/category hint matched '{role}'")


def _score_with_quantity_and_unit(
    candidate_scores: Dict[str, float],
    normalized_ingredient: Dict[str, Any],
    metadata: Dict[str, Any],
    evidence: List[str],
) -> None:
    quantity = normalized_ingredient.get("quantity")
    unit = _norm(str(normalized_ingredient.get("unit") or ""))
    properties = metadata.get("properties", {})
    canonical = _norm(str(normalized_ingredient.get("canonical", "")))
    base = _norm(str(normalized_ingredient.get("base", "")))

    if isinstance(quantity, (int, float)):
        if unit in SMALL_UNITS and quantity <= 2:
            if "sweetener" in candidate_scores and properties.get("sweetness") == "high":
                candidate_scores["sweetener"] += 0.28
                evidence.append("small spoon unit with sweet profile -> sweetener")
            if "flavor_booster" in candidate_scores:
                candidate_scores["flavor_booster"] += 0.18
                evidence.append("small spoon unit -> flavor booster tendency")

        if unit in LARGE_UNITS and quantity >= 1:
            for role in ["main_component", "body_provider", "sauce_base", "structure", "moisture_provider"]:
                if role in candidate_scores:
                    candidate_scores[role] += 0.16
            evidence.append("larger quantity -> base/body role tendency")

        # Protein-like ingredients in substantial amounts are typically main protein roles.
        possible_functions = {str(x).strip().lower() for x in metadata.get("possible_functions", [])}
        base = _norm(str(normalized_ingredient.get("base", "")))
        canonical = _norm(str(normalized_ingredient.get("canonical", "")))
        protein_tokens = {
            "chicken",
            "beef",
            "pork",
            "turkey",
            "shrimp",
            "fish",
            "tofu",
            "lamb",
            "ham",
            "bacon",
            "sausage",
            "steak",
            "flank",
            "sirloin",
            "ribeye",
        }
        if (
            "protein_base" in candidate_scores
            and quantity >= 1
            and (
                "protein_base" in possible_functions
                or base in protein_tokens
                or any(token in canonical for token in protein_tokens)
            )
        ):
            candidate_scores["protein_base"] += 0.24
            evidence.append("protein-like ingredient in substantial amount -> protein_base tendency")

        # Flour-like small amounts in liquid contexts are often thickening agents.
        if "thickener" in candidate_scores and ("flour" in canonical or base == "flour"):
            if (unit == "tbsp" and quantity <= 4) or (unit == "cup" and quantity <= 0.5):
                candidate_scores["thickener"] += 0.2
                evidence.append("flour in smaller measured amount -> thickener tendency")

    if base in {"water", "broth", "stock"}:
        for role in ["moisture_provider", "sauce_base"]:
            if role in candidate_scores:
                candidate_scores[role] += 0.24
        evidence.append("liquid stock/water ingredient -> moisture/sauce base tendency")


def _score_with_metadata_bias(
    candidate_scores: Dict[str, float],
    recipe_context: RecipeContext,
    metadata: Dict[str, Any],
    evidence: List[str],
) -> None:
    properties = metadata.get("properties", {})
    texture = str(metadata.get("texture", ""))
    recipe_text = " ".join([recipe_context.title, recipe_context.desc, *recipe_context.categories, *recipe_context.directions]).lower()

    if properties.get("acidity") == "high" and "acidity_provider" in candidate_scores:
        candidate_scores["acidity_provider"] += 0.22
        evidence.append("metadata acidity=high")

    if properties.get("sweetness") == "high" and "sweetener" in candidate_scores:
        candidate_scores["sweetener"] += 0.22
        evidence.append("metadata sweetness=high")

    if properties.get("fat") == "high":
        for role in ["richness", "emulsifier"]:
            if role in candidate_scores:
                candidate_scores[role] += 0.12
        evidence.append("metadata fat=high")

    if texture in {"powder", "paste"} and "thickener" in candidate_scores:
        candidate_scores["thickener"] += 0.12
        evidence.append("metadata texture supports thickening")

    for capability in metadata.get("special_capabilities", []):
        capability_text = str(capability)
        for role in CAPABILITY_ROLE_HINTS.get(capability_text, []):
            if role not in candidate_scores:
                continue

            if capability_text == "emulsifier":
                if _text_contains_any(recipe_text, ["dressing", "vinaigrette", "emulsify", "mayonnaise", "whisk"]):
                    candidate_scores[role] += 0.2
                    evidence.append("special capability 'emulsifier' in emulsification context")
                else:
                    candidate_scores[role] += 0.04
                    evidence.append("special capability 'emulsifier' (low context match)")
                continue

            candidate_scores[role] += 0.2
            evidence.append(f"special capability '{capability_text}' supports '{role}'")


def _top_role(candidate_scores: Dict[str, float]) -> Tuple[str, float]:
    ranked = sorted(candidate_scores.items(), key=lambda item: (-item[1], item[0]))
    role, score = ranked[0]

    if len(ranked) == 1:
        confidence = max(0.2, min(0.6, round(score, 2)))
        return role, confidence

    second_score = ranked[1][1]
    margin = max(0.0, score - second_score)
    confidence = max(0.25, min(0.95, round((score * 0.75) + (margin * 0.25), 2)))
    return role, confidence


def score_candidate_roles(
    normalized_ingredient: Dict[str, Any],
    recipe_context: RecipeContext,
    metadata: Dict[str, Any],
) -> Tuple[Dict[str, float], List[str]]:
    """Score metadata-supported candidate roles with transparent heuristics."""
    candidates = _candidate_roles_from_metadata(metadata)

    candidate_scores: Dict[str, float] = {role: 0.25 for role in candidates}
    evidence: List[str] = ["candidates seeded from ingredient metadata"]

    _score_with_metadata_bias(candidate_scores, recipe_context, metadata, evidence)
    _score_with_title_and_categories(candidate_scores, recipe_context, evidence)
    _score_with_direction_patterns(candidate_scores, normalized_ingredient, recipe_context, evidence)
    _score_with_quantity_and_unit(candidate_scores, normalized_ingredient, metadata, evidence)

    # Clamp scores to 0..1 for readability while preserving score spread.
    normalized_scores = {role: round(min(0.99, max(0.05, score)), 2) for role, score in candidate_scores.items()}
    return normalized_scores, evidence


def infer_role_for_ingredient(
    normalized_ingredient: Dict[str, Any],
    recipe_context: RecipeContext,
) -> Dict[str, Any]:
    """Infer a single ingredient role in recipe context."""
    canonical = _norm(str(normalized_ingredient.get("canonical", "")))
    base = _norm(str(normalized_ingredient.get("base", "")))
    metadata = get_metadata(canonical) if canonical else get_metadata(base)
    if metadata.get("possible_functions") == [] and canonical and base and canonical != base:
        metadata = get_metadata(base)

    role_scores, evidence = score_candidate_roles(normalized_ingredient, recipe_context, metadata)
    inferred_role, confidence = _top_role(role_scores)

    # Safety override: obvious protein ingredients should not be routed to
    # structure-like roles only because of bread/sauce context cues.
    protein_tokens = {
        "chicken",
        "beef",
        "pork",
        "turkey",
        "shrimp",
        "fish",
        "tofu",
        "lamb",
        "ham",
        "bacon",
        "sausage",
        "steak",
        "flank",
        "sirloin",
        "ribeye",
    }
    canonical_tokens = set(canonical.split())
    base_token = base
    meta_functions = {str(x).strip().lower() for x in metadata.get("possible_functions", [])}
    is_protein_like = (
        (base_token in protein_tokens)
        or bool(canonical_tokens.intersection(protein_tokens))
        or ("protein_base" in meta_functions)
    )
    if is_protein_like and inferred_role in {"structure", "serving_base", "body_provider"}:
        inferred_role = "protein_base"
        confidence = max(confidence, 0.55)
        evidence.append("protein heuristic override applied")

    result = RoleInferenceResult(
        ingredient_raw=str(normalized_ingredient.get("raw", "")),
        canonical=canonical,
        base=base,
        candidate_role_scores=role_scores,
        inferred_role=inferred_role,
        confidence=confidence,
        evidence=evidence[:6],
    )
    out = result.to_dict()
    out["role_behavior_profile"] = ROLE_BEHAVIOR_PROFILE.get(
        inferred_role,
        {
            "required_capabilities": [],
            "critical_functions": [inferred_role],
        },
    )
    return out


def infer_roles_for_recipe(
    normalized_ingredients: List[Dict[str, Any]],
    recipe_context: RecipeContext,
) -> List[Dict[str, Any]]:
    """Infer roles for all ingredients in a recipe (shadow mode output)."""
    results: List[Dict[str, Any]] = []
    for ingredient in normalized_ingredients:
        if not isinstance(ingredient, dict):
            continue
        results.append(infer_role_for_ingredient(ingredient, recipe_context))
    return results
