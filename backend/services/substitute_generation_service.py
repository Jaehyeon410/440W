"""Function-based substitute generation service (Step 4, shadow mode).

This service generates substitute candidates from:
- source ingredient normalization (V2)
- source metadata
- inferred role in recipe context
- role-based substitute pools
- candidate metadata compatibility
- optional user inventory filtering

It is additive only and does not replace existing substitution engine behavior.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ingredient_normalizer_v2 import normalize_ingredient_v2, normalize_ingredient_list_v2
from services.ingredient_metadata_service import get_metadata
from services.role_inference_service import RecipeContext, infer_role_for_ingredient


POOLS_FILE = Path(__file__).resolve().parents[1] / "substitute_pools.json"

ROLE_TITLE_HINTS = {
    "thickener": ["gravy", "sauce", "soup", "stew"],
    "structure": ["bread", "dough", "loaf", "pizza"],
    "aerated_base": ["whipped", "mousse", "dessert", "cream"],
    "topping": ["dessert", "salad", "garnish", "plated"],
    "flavor_base": ["sauce", "stew", "braise", "gravy"],
}

ROLE_POOL_ALIASES = {
    "protein_base": ["main_component", "body_provider"],
    "main_component": ["protein_base", "body_provider"],
    "flavor_booster": ["flavor_base", "acidity_provider"],
}

ROLE_REQUIRED_CAPABILITIES = {
    "aerated_base": {"whippable"},
    "thickener": {"gelatinizing"},
    "binder": {"emulsifier"},
}

ROLE_TEXTURE_PREFERENCES = {
    "thickener": {"powder", "paste"},
    "structure": {"powder", "soft"},
    "aerated_base": {"creamy"},
    "topping": {"crunchy", "soft"},
    "garnish": {"crunchy", "soft", "liquid"},
    "texture_contrast": {"crunchy"},
}

ROLE_EXCLUSION_HINTS = {
    "aerated_base": {"water", "broth", "milk"},
    "structure": {"broth", "water", "cornstarch", "potato starch", "arrowroot", "tapioca starch"},
    "thickener": {"almond", "walnut", "pecans", "broth", "water", "milk", "butter"},
    "topping": {"broth", "water"},
}

PROPERTY_LEVEL = {"low": 0, "medium": 1, "high": 2}
MIN_INVENTORY_ONLY_SCORE = 0.45
MIN_BASE_CANDIDATE_SCORE = 0.35

ROLE_MIN_THRESHOLDS = {
    "protein_base": {"base": 0.25, "inventory_only": 0.30},
    "main_component": {"base": 0.25, "inventory_only": 0.30},
}


@dataclass
class CandidateScore:
    score: float
    evidence: List[str]
    score_breakdown: Dict[str, float]
    warnings: List[str]


@lru_cache(maxsize=1)
def load_substitute_pools() -> Dict[str, List[str]]:
    """Load role-keyed substitute pools with safe fallback."""
    try:
        with POOLS_FILE.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[substitute_generation] failed to load pools: {exc}")
        return {}

    pools: Dict[str, List[str]] = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            pools[key] = [str(item).strip() for item in value if str(item).strip()]
    return pools


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def _inventory_lookup_keys(user_inventory: Optional[List[str]]) -> Set[str]:
    keys: Set[str] = set()
    if not user_inventory:
        return keys

    for item in normalize_ingredient_list_v2(user_inventory):
        for key in [item.get("canonical"), item.get("base"), item.get("normalized_text")]:
            value = _norm(str(key or ""))
            if value:
                keys.add(value)
    return keys


def _metadata_for_normalized(normalized: Dict[str, Any]) -> Dict[str, Any]:
    canonical = _norm(str(normalized.get("canonical") or ""))
    base = _norm(str(normalized.get("base") or ""))
    meta = get_metadata(canonical) if canonical else {}
    if meta.get("possible_functions"):
        return meta
    if base:
        return get_metadata(base)
    return get_metadata(canonical)


def _inventory_metadata_candidates(user_inventory: Optional[List[str]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not user_inventory:
        return out
    for item in normalize_ingredient_list_v2(user_inventory):
        meta = _metadata_for_normalized(item)
        out.append({"norm": item, "meta": meta})
    return out


def _resolve_source_and_role(
    missing_ingredient: Dict[str, Any],
    recipe_context: RecipeContext,
) -> Tuple[Dict[str, Any], str, float]:
    source = dict(missing_ingredient)
    if not source.get("canonical"):
        source = normalize_ingredient_v2(str(source.get("raw", ""))).to_dict()

    explicit_role = _norm(str(source.get("inferred_role") or ""))
    if explicit_role:
        confidence = float(source.get("role_confidence") or source.get("confidence") or 0.5)
        return source, explicit_role, max(0.0, min(0.99, confidence))

    inferred = infer_role_for_ingredient(source, recipe_context)
    return source, _norm(str(inferred.get("inferred_role", "main_component"))), float(inferred.get("confidence", 0.4))


def _resolve_pool_role(
    requested_role: str,
    source_norm: Dict[str, Any],
    pools: Dict[str, List[str]],
) -> Tuple[str, List[str], str]:
    role = _norm(requested_role)
    if role in pools:
        return role, pools[role], "requested_role_pool"

    for alias in ROLE_POOL_ALIASES.get(role, []):
        alias_norm = _norm(alias)
        if alias_norm in pools:
            return alias_norm, pools[alias_norm], "role_alias_pool"

    source_meta = _metadata_for_normalized(source_norm)
    for role_candidate in source_meta.get("possible_functions", []):
        role_candidate_norm = _norm(str(role_candidate))
        if role_candidate_norm in pools:
            return role_candidate_norm, pools[role_candidate_norm], "metadata_role_pool"
        for alias in ROLE_POOL_ALIASES.get(role_candidate_norm, []):
            alias_norm = _norm(alias)
            if alias_norm in pools:
                return alias_norm, pools[alias_norm], "metadata_role_alias_pool"

    return role, [], "no_pool_found"


def _property_similarity(src_value: str, cand_value: str) -> float:
    a = PROPERTY_LEVEL.get(_norm(src_value), 1)
    b = PROPERTY_LEVEL.get(_norm(cand_value), 1)
    distance = abs(a - b)
    if distance == 0:
        return 1.0
    if distance == 1:
        return 0.6
    return 0.2


def _candidate_available(candidate_norm: Dict[str, Any], inventory_keys: Set[str]) -> bool:
    if not inventory_keys:
        return False
    checks = {
        _norm(str(candidate_norm.get("canonical") or "")),
        _norm(str(candidate_norm.get("base") or "")),
        _norm(str(candidate_norm.get("normalized_text") or "")),
    }
    return any(item and item in inventory_keys for item in checks)


def _recipe_text(recipe_context: RecipeContext) -> str:
    return " ".join([recipe_context.title, recipe_context.desc, *recipe_context.categories, *recipe_context.directions]).lower()


def _is_candidate_role_compatible(role: str, candidate_meta: Dict[str, Any]) -> Tuple[bool, str]:
    role_norm = _norm(role)
    functions = {str(item).strip().lower() for item in candidate_meta.get("possible_functions", [])}
    caps = {str(item).strip().lower() for item in candidate_meta.get("special_capabilities", [])}

    if role_norm == "binder" and "emulsifier" not in caps:
        return False, "binder role requires emulsifier capability"
    if role_norm == "thickener" and "gelatinizing" not in caps:
        return False, "thickener role requires gelatinizing capability"
    if role_norm == "aerated_base" and "whippable" not in caps:
        return False, "aerated_base role requires whippable capability"
    if role_norm == "structure":
        structure_signal = 0
        if functions.intersection({"structure", "protein_base", "body_provider", "binder"}):
            structure_signal += 1
        texture = _norm(str(candidate_meta.get("texture", "")))
        if texture in {"powder", "soft", "paste"}:
            structure_signal += 1
        if structure_signal == 0:
            return False, "structure role requires starch/protein-like support"

    return True, ""


def score_substitute_candidate(
    source_ingredient: Dict[str, Any],
    candidate_ingredient: Dict[str, Any],
    inferred_role: str,
    recipe_context: RecipeContext,
) -> CandidateScore:
    """Lightweight explainable score for one candidate substitute."""
    source_meta = _metadata_for_normalized(source_ingredient)
    candidate_meta = _metadata_for_normalized(candidate_ingredient)

    evidence: List[str] = []
    warnings: List[str] = []
    breakdown: Dict[str, float] = {}
    score = 0.15

    role = _norm(inferred_role)
    candidate_functions = {str(item).strip().lower() for item in candidate_meta.get("possible_functions", [])}
    if role in candidate_functions:
        score += 0.35
        breakdown["role_function_match"] = 0.35
        evidence.append("candidate metadata contains inferred role")
    else:
        score -= 0.1
        breakdown["role_function_match"] = -0.1
        warnings.append("candidate metadata does not strongly support inferred role")

    source_category = _norm(str(source_meta.get("category", "")))
    candidate_category = _norm(str(candidate_meta.get("category", "")))
    if source_category and candidate_category and source_category == candidate_category:
        score += 0.10
        breakdown["category_match"] = 0.10
        evidence.append("source/candidate category match")

    source_parent = _norm(str(source_meta.get("parent") or ""))
    candidate_parent = _norm(str(candidate_meta.get("parent") or ""))
    if source_parent and candidate_parent and source_parent == candidate_parent:
        score += 0.08
        breakdown["parent_match"] = 0.08
        evidence.append("source/candidate parent match")

    src_texture = _norm(str(source_meta.get("texture", "")))
    cand_texture = _norm(str(candidate_meta.get("texture", "")))
    texture_pref = ROLE_TEXTURE_PREFERENCES.get(role, set())
    if src_texture and cand_texture and src_texture == cand_texture:
        score += 0.12
        breakdown["texture_match"] = 0.12
        evidence.append("source and candidate texture match")
    elif cand_texture in texture_pref:
        score += 0.08
        breakdown["texture_preference"] = 0.08
        evidence.append("candidate texture matches role preference")
    else:
        score -= 0.05
        breakdown["texture_penalty"] = -0.05

    src_props = source_meta.get("properties", {})
    cand_props = candidate_meta.get("properties", {})
    fat_sim = _property_similarity(str(src_props.get("fat", "medium")), str(cand_props.get("fat", "medium")))
    moisture_sim = _property_similarity(str(src_props.get("moisture", "medium")), str(cand_props.get("moisture", "medium")))
    score += (fat_sim * 0.1) + (moisture_sim * 0.1)
    breakdown["fat_similarity"] = round(fat_sim * 0.1, 3)
    breakdown["moisture_similarity"] = round(moisture_sim * 0.1, 3)
    evidence.append("fat/moisture similarity considered")

    required_caps = ROLE_REQUIRED_CAPABILITIES.get(role, set())
    candidate_caps = {str(item).strip().lower() for item in candidate_meta.get("special_capabilities", [])}
    if required_caps:
        matched = required_caps.intersection(candidate_caps)
        if matched:
            score += 0.12
            breakdown["capability_match"] = 0.12
            evidence.append(f"required capability matched: {', '.join(sorted(matched))}")
        else:
            score -= 0.14
            breakdown["capability_miss"] = -0.14
            warnings.append("missing role-critical capability")

    text = _recipe_text(recipe_context)
    for hint_role, patterns in ROLE_TITLE_HINTS.items():
        if hint_role != role:
            continue
        if any(pattern in text for pattern in patterns):
            score += 0.08
            breakdown["title_category_context"] = 0.08
            evidence.append("recipe title/category context supports inferred role")
            break

    candidate_base = _norm(str(candidate_ingredient.get("base") or ""))
    source_base = _norm(str(source_ingredient.get("base") or ""))
    source_canonical = _norm(str(source_ingredient.get("canonical") or ""))
    candidate_canonical = _norm(str(candidate_ingredient.get("canonical") or ""))

    # Keep same-family options as fallback, but prefer meaningful alternatives first.
    if source_base and candidate_base and source_base == candidate_base:
        score -= 0.06
        breakdown["same_base_penalty"] = -0.06
        warnings.append("candidate is same base family as source")

    if source_canonical and candidate_canonical and source_canonical == candidate_canonical:
        score -= 0.18
        breakdown["same_canonical_penalty"] = -0.18
        warnings.append("candidate is nearly identical to source ingredient")

    excluded = ROLE_EXCLUSION_HINTS.get(role, set())
    if candidate_base in excluded:
        score -= 0.35
        breakdown["hard_exclusion_penalty"] = -0.35
        warnings.append("candidate is a known poor fit for this role")

    return CandidateScore(
        score=max(0.0, min(0.99, round(score, 3))),
        evidence=evidence,
        score_breakdown=breakdown,
        warnings=warnings,
    )


def generate_substitute_candidates(
    missing_ingredient: Dict[str, Any],
    recipe_context: RecipeContext,
    user_inventory: Optional[List[str]] = None,
    inventory_only: bool = False,
) -> Dict[str, Any]:
    """Generate ranked candidate substitutes for one missing ingredient."""
    source_norm, inferred_role, role_confidence = _resolve_source_and_role(missing_ingredient, recipe_context)
    pools = load_substitute_pools()
    resolved_role, pool, role_resolution = _resolve_pool_role(inferred_role, source_norm, pools)
    source_meta = _metadata_for_normalized(source_norm)
    role_thresholds = ROLE_MIN_THRESHOLDS.get(_norm(resolved_role), {})
    min_base_score = float(role_thresholds.get("base", MIN_BASE_CANDIDATE_SCORE))
    min_inventory_score = float(role_thresholds.get("inventory_only", MIN_INVENTORY_ONLY_SCORE))

    inventory_keys = _inventory_lookup_keys(user_inventory)
    candidate_rows: List[Dict[str, Any]] = []

    candidate_names = [str(name).strip() for name in pool if str(name).strip()]
    for name in source_meta.get("direct_substitutes", []) or []:
        candidate_name = str(name).strip()
        if candidate_name and candidate_name not in candidate_names:
            candidate_names.append(candidate_name)

    source_category = _norm(str(source_meta.get("category") or ""))
    source_parent = _norm(str(source_meta.get("parent") or ""))
    for inv in _inventory_metadata_candidates(user_inventory):
        cand_meta = inv["meta"]
        cand_norm = inv["norm"]
        candidate_canonical = str(cand_norm.get("canonical") or cand_norm.get("base") or "").strip()
        if not candidate_canonical:
            continue
        candidate_category = _norm(str(cand_meta.get("category") or ""))
        candidate_parent = _norm(str(cand_meta.get("parent") or ""))
        if source_category and candidate_category == source_category and candidate_canonical not in candidate_names:
            candidate_names.append(candidate_canonical)
        elif source_parent and candidate_parent and candidate_parent == source_parent and candidate_canonical not in candidate_names:
            candidate_names.append(candidate_canonical)

    for candidate_name in candidate_names:
        candidate_norm = normalize_ingredient_v2(candidate_name).to_dict()

        source_key = _norm(str(source_norm.get("canonical") or source_norm.get("base") or ""))
        candidate_key = _norm(str(candidate_norm.get("canonical") or candidate_norm.get("base") or ""))
        if source_key and candidate_key and source_key == candidate_key:
            continue

        available = _candidate_available(candidate_norm, inventory_keys)
        if inventory_only and user_inventory is not None and not available:
            continue

        score_pack = score_substitute_candidate(source_norm, candidate_norm, resolved_role, recipe_context)

        candidate_meta = _metadata_for_normalized(candidate_norm)
        compatible, incompat_reason = _is_candidate_role_compatible(resolved_role, candidate_meta)
        if not compatible:
            continue

        if available:
            score = min(0.99, round(score_pack.score + 0.05, 3))
            evidence = [*score_pack.evidence, "candidate is available in user inventory"]
        else:
            score = score_pack.score
            evidence = score_pack.evidence

        if score < min_base_score:
            continue

        if inventory_only and score < min_inventory_score:
            continue

        candidate_rows.append(
            {
                "source_raw": str(source_norm.get("raw", "")),
                "source_canonical": str(source_norm.get("canonical", "")),
                "source_base": str(source_norm.get("base", "")),
                "inferred_role": resolved_role,
                "role_confidence": round(role_confidence, 2),
                "candidate": candidate_name,
                "candidate_canonical": str(candidate_norm.get("canonical", "")),
                "candidate_base": str(candidate_norm.get("base", "")),
                "available_in_inventory": available,
                "score": score,
                "evidence": evidence[:6],
                "score_breakdown": score_pack.score_breakdown,
                "warnings": score_pack.warnings,
                "hard_filters": [incompat_reason] if incompat_reason else [],
                "candidate_metadata_summary": {
                    "category": candidate_meta.get("category", ""),
                    "parent": candidate_meta.get("parent", None),
                    "texture": candidate_meta.get("texture", ""),
                    "possible_functions": candidate_meta.get("possible_functions", []),
                },
            }
        )

    if not candidate_rows and user_inventory:
        # Last-resort usable fallback for unknown ingredients.
        for inv in _inventory_metadata_candidates(user_inventory):
            candidate_norm = inv["norm"]
            candidate_name = str(candidate_norm.get("canonical") or candidate_norm.get("base") or "").strip()
            if not candidate_name:
                continue
            candidate_rows.append(
                {
                    "source_raw": str(source_norm.get("raw", "")),
                    "source_canonical": str(source_norm.get("canonical", "")),
                    "source_base": str(source_norm.get("base", "")),
                    "inferred_role": resolved_role,
                    "role_confidence": round(role_confidence, 2),
                    "candidate": candidate_name,
                    "candidate_canonical": str(candidate_norm.get("canonical", "")),
                    "candidate_base": str(candidate_norm.get("base", "")),
                    "available_in_inventory": True,
                    "score": 0.40,
                    "evidence": ["inventory fallback candidate"],
                    "score_breakdown": {"fallback": 0.40},
                    "warnings": ["metadata fallback route used"],
                    "hard_filters": [],
                    "candidate_metadata_summary": {
                        "category": inv["meta"].get("category", ""),
                        "parent": inv["meta"].get("parent", None),
                        "texture": inv["meta"].get("texture", ""),
                        "possible_functions": inv["meta"].get("possible_functions", []),
                    },
                }
            )
            if len(candidate_rows) >= 3:
                break

    candidate_rows.sort(key=lambda row: (-float(row["score"]), row["candidate"]))
    return {
        "source": source_norm,
        "inferred_role": resolved_role,
        "role_confidence": round(role_confidence, 2),
        "role_resolution": role_resolution,
        "inventory_only": inventory_only,
        "candidates": candidate_rows,
    }


def generate_candidates_for_recipe(
    missing_ingredients: List[Dict[str, Any]],
    recipe_context: RecipeContext,
    user_inventory: Optional[List[str]] = None,
    inventory_only: bool = False,
) -> List[Dict[str, Any]]:
    """Generate substitute candidates for multiple missing ingredients."""
    results: List[Dict[str, Any]] = []
    for item in missing_ingredients:
        if isinstance(item, str):
            normalized_item = normalize_ingredient_v2(item).to_dict()
            normalized_item["raw"] = item
            source = normalized_item
        elif isinstance(item, dict):
            source = item
        else:
            continue

        results.append(
            generate_substitute_candidates(
                source,
                recipe_context,
                user_inventory=user_inventory,
                inventory_only=inventory_only,
            )
        )

    return results
