"""Substitute ranking service (refactored).

Simplified, importance-aware ranking with new weight structure.
Removed: compute_rank_confidence, weak_candidate_penalty, name_similarity
         penalty, same_family_penalty, context_fit.
Added: importance-aware thresholds, direct_substitute_bonus.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from services.ingredient_metadata_service import get_metadata
from services.role_inference_service import FUNCTION_TO_ROLE


# New simplified weights
RANK_WEIGHTS = {
    "function_overlap": 0.30,
    "texture_similarity": 0.20,
    "property_similarity": 0.20,
    "attribute_vector_similarity": 0.15,
    "role_support": 0.10,
    "inventory_bonus": 0.03,
    "direct_substitute_bonus": 0.02,
}

# Importance-aware acceptance thresholds
IMPORTANCE_THRESHOLDS = {
    "critical": 0.40,     # importance >= 0.65
    "important": 0.30,    # importance >= 0.35
    "flexible": 0.20,     # importance < 0.35
}

MIN_RECOMMEND_SCORE = 0.30
MIN_RECOMMEND_SCORE_INVENTORY_ONLY = 0.20

HARD_REJECT_RULES = {
    "aerated_base": {"water", "broth", "vinegar"},
    "structure": {"water", "broth", "vinegar"},
    "thickener": {"broth", "water", "almond", "walnut", "pecans"},
    "topping": {"broth", "water", "vinegar"},
    "sweetener": {"broth", "water"},
}

ROLE_REQUIRED_CAPABILITIES = {
    "aerated_base": {"whippable"},
    "thickener": {"gelatinizing"},
    "emulsifier": {"emulsifier"},
    "binder": {"emulsifier"},
}

ROLE_CRITICAL_FUNCTIONS = {
    "structure": {"structure", "protein_base", "body_provider"},
    "thickener": {"thickener", "binder"},
    "aerated_base": {"aerated_base", "body_provider"},
    "binder": {"binder", "emulsifier"},
}

ROLE_FUNCTION_ALIASES: Dict[str, str] = {
    "acidity_provider": "acid_source",
    "flavor_booster": "seasoning",
    "richness": "fat_source",
    "moisture_provider": "liquid_base",
    "main_component": "main_protein",
    "protein_base": "main_protein",
}

PROPERTY_LEVEL = {"low": 0.0, "medium": 0.5, "high": 1.0}

TEXTURE_VECTOR = {
    "powder": [1.0, 0.0, 0.0, 0.0, 0.0],
    "paste": [0.8, 0.2, 0.0, 0.0, 0.0],
    "solid": [0.0, 1.0, 0.0, 0.0, 0.0],
    "soft": [0.0, 0.8, 0.2, 0.0, 0.0],
    "creamy": [0.0, 0.0, 1.0, 0.0, 0.0],
    "liquid": [0.0, 0.0, 0.8, 0.2, 0.0],
    "crunchy": [0.0, 0.0, 0.0, 1.0, 0.0],
    "gel": [0.2, 0.0, 0.3, 0.0, 0.5],
}

FLAVOR_STRENGTH_VECTOR = {
    "mild": [1.0, 0.0, 0.0],
    "medium": [0.0, 1.0, 0.0],
    "strong": [0.0, 0.0, 1.0],
}


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def _property_similarity(src_value: str, cand_value: str) -> float:
    src = PROPERTY_LEVEL.get(_norm(src_value), 0.5)
    cand = PROPERTY_LEVEL.get(_norm(cand_value), 0.5)
    distance = abs(src - cand)
    return max(0.0, 1.0 - distance)


def _texture_similarity(src_texture: str, cand_texture: str) -> float:
    src = _norm(src_texture)
    cand = _norm(cand_texture)
    if not src or not cand:
        return 0.45
    if src == cand:
        return 1.0
    close_pairs = {
        ("creamy", "liquid"), ("liquid", "creamy"),
        ("powder", "paste"), ("paste", "powder"),
        ("solid", "soft"), ("soft", "solid"),
        ("crunchy", "solid"), ("solid", "crunchy"),
    }
    if (src, cand) in close_pairs:
        return 0.65
    return 0.25


def _metadata_for_item(canonical: str, base: str) -> Dict[str, Any]:
    canonical_key = _norm(canonical)
    base_key = _norm(base)
    if canonical_key:
        meta = get_metadata(canonical_key, allow_generation=False)
        if meta.get("possible_functions"):
            return meta
    if base_key:
        return get_metadata(base_key, allow_generation=False)
    return get_metadata(canonical_key, allow_generation=False)


def _euclidean_distance(values_a: List[float], values_b: List[float]) -> float:
    if not values_a or not values_b or len(values_a) != len(values_b):
        return 1.0
    return sum((a - b) ** 2 for a, b in zip(values_a, values_b)) ** 0.5


def _safe_level(value: str) -> float:
    return PROPERTY_LEVEL.get(_norm(value), 0.5)


def _attribute_vector(meta: Dict[str, Any]) -> List[float]:
    props = meta.get("properties", {})
    texture = _norm(str(meta.get("texture", "")))
    flavor_strength = _norm(str(meta.get("flavor_strength", "")))
    texture_vec = TEXTURE_VECTOR.get(texture, [0.2, 0.2, 0.2, 0.2, 0.2])
    flavor_vec = FLAVOR_STRENGTH_VECTOR.get(flavor_strength, [0.3, 0.4, 0.3])
    return [
        _safe_level(str(props.get("fat", "medium"))),
        _safe_level(str(props.get("moisture", "medium"))),
        _safe_level(str(props.get("acidity", "low"))),
        _safe_level(str(props.get("sweetness", "low"))),
        _safe_level(str(props.get("saltiness", "low"))),
        *texture_vec,
        *flavor_vec,
    ]


def _attribute_vector_similarity(source_meta: Dict[str, Any], candidate_meta: Dict[str, Any]) -> float:
    src = _attribute_vector(source_meta)
    cand = _attribute_vector(candidate_meta)
    distance = _euclidean_distance(src, cand)
    max_distance = (len(src) ** 0.5)
    return max(0.0, min(1.0, 1.0 - (distance / max_distance)))


def _structure_signal(candidate_functions: set, candidate_meta: Dict[str, Any]) -> float:
    signal = 0.0
    if candidate_functions.intersection({"structure", "protein_base", "body_provider", "binder"}):
        signal += 0.7
    caps = {str(item).strip().lower() for item in candidate_meta.get("special_capabilities", [])}
    if "fermentable" in caps or "emulsifier" in caps:
        signal += 0.2
    texture = _norm(str(candidate_meta.get("texture", "")))
    if texture in {"powder", "soft", "paste"}:
        signal += 0.1
    return min(1.0, signal)


def _importance_tier(importance: float) -> str:
    if importance >= 0.65:
        return "critical"
    if importance >= 0.35:
        return "important"
    return "flexible"


def apply_hard_rejects(
    source: Dict[str, Any],
    candidate: Dict[str, Any],
    source_meta: Optional[Dict[str, Any]] = None,
    candidate_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str]]:
    """Return (is_rejected, reason) for clearly invalid candidate pairs.

    Hard rejects are now based on source functions/capabilities, not a single
    inferred role.  We check all source functions and reject if the candidate
    is fundamentally incompatible with ANY critical function.
    """
    candidate_base = _norm(str(candidate.get("candidate_base") or ""))
    candidate_canonical = _norm(str(candidate.get("candidate_canonical") or candidate.get("candidate") or ""))
    candidate_tokens = set(re.findall(r"[a-z]+", candidate_canonical))

    if candidate_meta is None:
        candidate_meta = _metadata_for_item(
            canonical=str(candidate.get("candidate_canonical") or candidate.get("candidate") or ""),
            base=str(candidate.get("candidate_base") or ""),
        )
    candidate_caps = {str(item).strip().lower() for item in candidate_meta.get("special_capabilities", [])}
    candidate_functions = {str(item).strip().lower() for item in candidate_meta.get("possible_functions", [])}

    if source_meta is None:
        source_meta = _metadata_for_item(
            canonical=str(source.get("source_canonical") or source.get("canonical") or ""),
            base=str(source.get("source_base") or source.get("base") or ""),
        )
    source_functions = {str(item).strip().lower() for item in source_meta.get("possible_functions", [])}
    source_caps = {str(item).strip().lower() for item in source_meta.get("special_capabilities", [])}

    # Map source functions to roles to check hard reject rules
    source_roles = set()
    for fn in source_functions:
        mapped = FUNCTION_TO_ROLE.get(fn)
        if mapped:
            source_roles.add(mapped)

    for role in source_roles:
        for blocked in HARD_REJECT_RULES.get(role, set()):
            blocked_norm = _norm(blocked)
            if candidate_base == blocked_norm or blocked_norm in candidate_tokens:
                return True, f"hard reject: source role '{role}' incompatible with '{blocked_norm}'"

    # Capability-based hard rejects: if source requires a capability, candidate must have it
    if "emulsifier" in source_caps and "binder" in source_functions:
        if "emulsifier" not in candidate_caps:
            return True, "hard reject: binder source requires emulsifier capability"

    if "gelatinizing" in source_caps and ("thickener" in source_functions or "thickener" in source_roles):
        if "gelatinizing" not in candidate_caps:
            return True, "hard reject: thickener source requires gelatinizing capability"

    if "whippable" in source_caps and "aerated_base" in source_roles:
        if "whippable" not in candidate_caps:
            return True, "hard reject: aerated_base source requires whippable capability"

    if "structure" in source_roles and _structure_signal(candidate_functions, candidate_meta) < 0.35:
        return True, "hard reject: structure source requires stronger starch/protein support"

    return False, None


def extract_and_score(
    source: Dict[str, Any],
    candidate: Dict[str, Any],
    source_meta: Dict[str, Any],
    recipe_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Extract features and compute rank score for one candidate."""
    candidate_meta = _metadata_for_item(
        canonical=str(candidate.get("candidate_canonical") or candidate.get("canonical") or candidate.get("candidate") or ""),
        base=str(candidate.get("candidate_base") or candidate.get("base") or ""),
    )

    source_functions = {str(item).strip().lower() for item in source_meta.get("possible_functions", [])}
    candidate_functions = {str(item).strip().lower() for item in candidate_meta.get("possible_functions", [])}

    # --- function_overlap ---
    if source_functions and candidate_functions:
        overlap = len(source_functions.intersection(candidate_functions))
        union = len(source_functions.union(candidate_functions))
        function_overlap = overlap / union if union else 0.0
    else:
        function_overlap = 0.2

    # --- texture_similarity ---
    texture_sim = _texture_similarity(
        str(source_meta.get("texture", "")),
        str(candidate_meta.get("texture", "")),
    )

    # --- property_similarity ---
    src_props = source_meta.get("properties", {})
    cand_props = candidate_meta.get("properties", {})
    moisture_sim = _property_similarity(str(src_props.get("moisture", "medium")), str(cand_props.get("moisture", "medium")))
    fat_sim = _property_similarity(str(src_props.get("fat", "medium")), str(cand_props.get("fat", "medium")))
    acidity_sim = _property_similarity(str(src_props.get("acidity", "low")), str(cand_props.get("acidity", "low")))
    property_sim = (moisture_sim + fat_sim + acidity_sim) / 3.0

    # --- attribute_vector_similarity ---
    attr_vec_sim = _attribute_vector_similarity(source_meta, candidate_meta)

    # --- role_support (soft, from all source roles) ---
    source_roles = set()
    for fn in source_functions:
        mapped = FUNCTION_TO_ROLE.get(fn)
        if mapped:
            source_roles.add(mapped)
    # Check how many of the source's possible roles the candidate can also serve
    candidate_roles = set()
    for fn in candidate_functions:
        mapped = FUNCTION_TO_ROLE.get(fn)
        if mapped:
            candidate_roles.add(mapped)
    if source_roles:
        role_support = len(source_roles & candidate_roles) / len(source_roles)
    else:
        role_support = 0.3

    # Partial credit for same category
    source_category = _norm(str(source_meta.get("category") or ""))
    candidate_category = _norm(str(candidate_meta.get("category") or ""))
    if role_support < 0.5 and source_category and source_category == candidate_category:
        role_support = max(role_support, 0.45)

    # --- inventory_bonus ---
    inventory_bonus = 1.0 if bool(candidate.get("available_in_inventory")) else 0.0

    # --- direct_substitute_bonus ---
    is_direct = str(candidate.get("retrieval_source", "")) == "direct_substitute"
    direct_substitute_bonus = 1.0 if is_direct else 0.0

    # --- hard reject ---
    hard_reject, reject_reason = apply_hard_rejects(
        source, candidate,
        source_meta=source_meta,
        candidate_meta=candidate_meta,
    )

    feature_scores = {
        "function_overlap": round(function_overlap, 4),
        "texture_similarity": round(texture_sim, 4),
        "property_similarity": round(property_sim, 4),
        "attribute_vector_similarity": round(attr_vec_sim, 4),
        "role_support": round(role_support, 4),
        "inventory_bonus": round(inventory_bonus, 4),
        "direct_substitute_bonus": round(direct_substitute_bonus, 4),
        "hard_reject_flag": bool(hard_reject),
    }

    # --- compute rank_score ---
    if hard_reject:
        rank_score = 0.0
    else:
        rank_score = sum(
            RANK_WEIGHTS[key] * feature_scores[key]
            for key in RANK_WEIGHTS
        )

    # Same-canonical penalty (keep light — only if truly identical)
    source_canonical = _norm(str(source.get("source_canonical") or source.get("canonical") or ""))
    candidate_canonical_key = _norm(str(candidate.get("candidate_canonical") or candidate.get("candidate") or ""))
    if source_canonical and candidate_canonical_key and source_canonical == candidate_canonical_key:
        rank_score -= 0.15

    rank_score = max(0.0, min(0.99, round(rank_score, 4)))

    return {
        "feature_scores": feature_scores,
        "candidate_metadata": candidate_meta,
        "rank_score": rank_score,
        "reject_reason": reject_reason,
    }


def _recommendation_tier(rank_score: float, rejected: bool) -> str:
    if rejected or rank_score <= 0.0:
        return "not_recommended"
    if rank_score >= 0.60:
        return "best"
    if rank_score >= 0.35:
        return "acceptable"
    return "not_recommended"


def rank_substitute_candidates(
    step4_result: Dict[str, Any],
    recipe_context: Optional[Any] = None,
    importance: float = 0.5,
) -> Dict[str, Any]:
    """Rank candidates from candidate-first generation output."""
    source_norm = step4_result.get("source", {})
    source_meta = step4_result.get("source_meta") or _metadata_for_item(
        canonical=str(source_norm.get("canonical") or ""),
        base=str(source_norm.get("base") or ""),
    )
    inventory_only = bool(step4_result.get("inventory_only", False))

    # Importance-aware threshold
    tier = _importance_tier(importance)
    importance_threshold = IMPORTANCE_THRESHOLDS.get(tier, 0.30)
    min_score = max(
        importance_threshold,
        MIN_RECOMMEND_SCORE_INVENTORY_ONLY if inventory_only else MIN_RECOMMEND_SCORE,
    )

    all_candidates: List[Dict[str, Any]] = []
    for candidate in step4_result.get("candidates", []):
        item = dict(candidate)
        scored = extract_and_score(
            source={
                "source_canonical": str(source_norm.get("canonical") or ""),
                "source_base": str(source_norm.get("base") or ""),
            },
            candidate=item,
            source_meta=source_meta,
            recipe_context=recipe_context,
        )

        rank_score = scored["rank_score"]
        rejected = bool(scored["feature_scores"].get("hard_reject_flag"))
        rec_tier = _recommendation_tier(rank_score, rejected)

        all_candidates.append({
            "source_canonical": str(source_norm.get("canonical", "")),
            "source_base": str(source_norm.get("base", "")),
            "candidate": str(item.get("candidate", "")),
            "candidate_canonical": str(item.get("candidate_canonical", "")),
            "candidate_base": str(item.get("candidate_base", "")),
            "available_in_inventory": bool(item.get("available_in_inventory", False)),
            "retrieval_source": str(item.get("retrieval_source", "")),
            "rank_score": rank_score,
            "feature_scores": scored["feature_scores"],
            "recommendation_tier": rec_tier,
            "reject_reason": scored["reject_reason"],
        })

    all_candidates.sort(key=lambda row: (-row["rank_score"], row["candidate"]))

    ranked_candidates = [
        row for row in all_candidates
        if row["recommendation_tier"] != "not_recommended"
        and row["rank_score"] >= min_score
    ]

    return {
        "source": source_norm,
        "source_meta": source_meta,
        "inventory_only": inventory_only,
        "importance": importance,
        "importance_tier": tier,
        "ranked_candidates": ranked_candidates,
        "candidate_count_before_filter": len(all_candidates),
        "candidate_count_after_filter": len(ranked_candidates),
    }


def rank_candidates_for_recipe(
    step4_results: List[Dict[str, Any]],
    recipe_context: Optional[Any] = None,
    importance_map: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Rank candidates for a list of Step 4 source outputs."""
    imp = importance_map or {}
    results = []
    for result in step4_results:
        source_key = _norm(str(result.get("source", {}).get("canonical") or ""))
        importance_val = imp.get(source_key, 0.5)
        results.append(rank_substitute_candidates(
            result, recipe_context=recipe_context, importance=importance_val,
        ))
    return results
