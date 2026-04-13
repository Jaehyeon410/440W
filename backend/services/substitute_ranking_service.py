"""Substitute ranking service (Step 5, shadow mode).

This layer consumes Step 4 candidate generation output and applies stronger,
normalized ranking with hard rejects and separate confidence logic.

It does not replace current user-facing substitution flow.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from services.ingredient_metadata_service import get_metadata


# Role/function and cooking behavior are intentionally dominant.
RANK_WEIGHTS = {
    "role_fit": 0.30,
    "function_overlap": 0.22,
    "behavior_match": 0.18,
    "attribute_vector_similarity": 0.14,
    "property_similarity": 0.10,
    "context_fit": 0.04,
    "inventory_bonus": 0.02,
}

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

ROLE_CONTEXT_HINTS = {
    "thickener": ["gravy", "sauce", "soup", "stew", "thicken", "simmer"],
    "structure": ["bread", "dough", "knead", "rise", "loaf", "pizza"],
    "aerated_base": ["whip", "soft peaks", "stiff peaks", "mousse", "dessert"],
    "topping": ["top", "sprinkle", "garnish", "plated", "serve"],
    "sweetener": ["sweet", "sugar", "dessert", "syrup"],
}

QUALITY_THRESHOLDS = {
    "best_match": 0.80,
    "good_with_adjustment": 0.64,
    "workable": 0.38,
}

MIN_RECOMMEND_SCORE = 0.54
MIN_RECOMMEND_SCORE_INVENTORY_ONLY = 0.40

PROPERTY_LEVEL = {"low": 0.0, "medium": 0.5, "high": 1.0}

DEFAULT_LIKE_PROPERTIES = {
    "fat": "low",
    "moisture": "medium",
    "sweetness": "low",
    "acidity": "low",
    "saltiness": "low",
}

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
        ("creamy", "liquid"),
        ("liquid", "creamy"),
        ("powder", "paste"),
        ("paste", "powder"),
        ("solid", "soft"),
        ("soft", "solid"),
        ("crunchy", "solid"),
        ("solid", "crunchy"),
    }
    if (src, cand) in close_pairs:
        return 0.65
    return 0.25


def _context_text(recipe_context: Optional[Any]) -> str:
    if recipe_context is None:
        return ""

    title = getattr(recipe_context, "title", "")
    desc = getattr(recipe_context, "desc", "")
    categories = getattr(recipe_context, "categories", []) or []
    directions = getattr(recipe_context, "directions", []) or []
    return " ".join([str(title), str(desc), *[str(x) for x in categories], *[str(x) for x in directions]]).lower()


def _metadata_for_item(canonical: str, base: str) -> Dict[str, Any]:
    canonical_key = _norm(canonical)
    base_key = _norm(base)

    if canonical_key:
        meta = get_metadata(canonical_key)
        if meta.get("possible_functions"):
            return meta
    if base_key:
        return get_metadata(base_key)
    return get_metadata(canonical_key)


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


def _name_similarity(source_text: str, candidate_text: str) -> float:
    src_tokens = {token for token in re.findall(r"[a-z]+", _norm(source_text)) if token}
    cand_tokens = {token for token in re.findall(r"[a-z]+", _norm(candidate_text)) if token}
    if not src_tokens or not cand_tokens:
        return 0.0
    overlap = len(src_tokens.intersection(cand_tokens))
    union = len(src_tokens.union(cand_tokens))
    return overlap / union if union else 0.0


def _structure_signal(candidate_functions: set[str], candidate_meta: Dict[str, Any]) -> float:
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


def _metadata_completeness(meta: Dict[str, Any]) -> float:
    # Default-like metadata from fallback should be treated as low completeness.
    if (
        not meta.get("possible_functions")
        and _norm(str(meta.get("texture", ""))) == "solid"
        and {k: _norm(str(v)) for k, v in dict(meta.get("properties", {})).items()} == DEFAULT_LIKE_PROPERTIES
        and not meta.get("special_capabilities")
    ):
        return 0.2

    score = 0.0
    if meta.get("possible_functions"):
        score += 0.35
    if meta.get("texture"):
        score += 0.2
    if meta.get("properties"):
        score += 0.25
    if meta.get("special_capabilities") is not None:
        score += 0.2
    return min(1.0, score)


def apply_hard_rejects(
    source: Dict[str, Any],
    candidate: Dict[str, Any],
    inferred_role: str,
    recipe_context: Optional[Any] = None,
    source_meta: Optional[Dict[str, Any]] = None,
    candidate_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str]]:
    """Return (is_rejected, reason) for clearly invalid role-candidate pairs."""
    role = _norm(inferred_role)
    candidate_base = _norm(str(candidate.get("candidate_base") or ""))
    candidate_canonical = _norm(str(candidate.get("candidate_canonical") or candidate.get("candidate") or ""))
    candidate_tokens = set(re.findall(r"[a-z]+", candidate_canonical))
    candidate_meta = candidate_meta or _metadata_for_item(
        canonical=str(candidate.get("candidate_canonical") or candidate.get("candidate") or ""),
        base=str(candidate.get("candidate_base") or ""),
    )
    candidate_caps = {str(item).strip().lower() for item in candidate_meta.get("special_capabilities", [])}
    candidate_functions = {str(item).strip().lower() for item in candidate_meta.get("possible_functions", [])}

    for blocked in HARD_REJECT_RULES.get(role, set()):
        blocked_norm = _norm(blocked)
        if candidate_base == blocked_norm or blocked_norm in candidate_tokens:
            return True, f"hard reject: role '{role}' incompatible with '{blocked_norm}'"

    if role == "binder" and "emulsifier" not in candidate_caps:
        return True, "hard reject: binder role requires emulsifier capability"

    if role == "thickener" and "gelatinizing" not in candidate_caps:
        return True, "hard reject: thickener role requires gelatinizing capability"

    if role == "aerated_base" and "whippable" not in candidate_caps:
        return True, "hard reject: aerated_base role requires whippable capability"

    if role == "structure" and _structure_signal(candidate_functions, candidate_meta) < 0.35:
        return True, "hard reject: structure role requires stronger starch/protein support"

    return False, None


def extract_candidate_features(
    source: Dict[str, Any],
    candidate: Dict[str, Any],
    recipe_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Extract normalized feature scores for ranking one candidate."""
    role = _norm(str(source.get("inferred_role") or ""))

    source_meta = _metadata_for_item(
        canonical=str(source.get("source_canonical") or source.get("canonical") or ""),
        base=str(source.get("source_base") or source.get("base") or ""),
    )
    candidate_meta = _metadata_for_item(
        canonical=str(candidate.get("candidate_canonical") or candidate.get("canonical") or candidate.get("candidate") or ""),
        base=str(candidate.get("candidate_base") or candidate.get("base") or ""),
    )

    source_functions = {str(item).strip().lower() for item in source_meta.get("possible_functions", [])}
    candidate_functions = {str(item).strip().lower() for item in candidate_meta.get("possible_functions", [])}

    candidate_name_for_tokens = _norm(
        str(candidate.get("candidate_canonical") or candidate.get("candidate") or candidate.get("candidate_base") or "")
    )
    protein_tokens = {"chicken", "beef", "pork", "turkey", "shrimp", "fish", "tofu", "lamb", "ham", "bacon", "sausage"}
    protein_token_hit = any(token in candidate_name_for_tokens for token in protein_tokens)

    role_fit = 1.0 if role and role in candidate_functions else 0.25
    if role in {"protein_base", "main_component"} and protein_token_hit:
        role_fit = max(role_fit, 0.72)

    if source_functions and candidate_functions:
        overlap = len(source_functions.intersection(candidate_functions))
        union = len(source_functions.union(candidate_functions))
        function_overlap = overlap / union if union else 0.0
    else:
        function_overlap = 0.2

    texture_similarity = _texture_similarity(
        str(source_meta.get("texture", "")),
        str(candidate_meta.get("texture", "")),
    )

    src_props = source_meta.get("properties", {})
    cand_props = candidate_meta.get("properties", {})
    moisture_similarity = _property_similarity(str(src_props.get("moisture", "medium")), str(cand_props.get("moisture", "medium")))
    fat_similarity = _property_similarity(str(src_props.get("fat", "medium")), str(cand_props.get("fat", "medium")))
    acidity_similarity = _property_similarity(str(src_props.get("acidity", "low")), str(cand_props.get("acidity", "low")))
    prop_values = [moisture_similarity, fat_similarity, acidity_similarity]
    property_similarity = sum(prop_values) / len(prop_values)

    required = ROLE_REQUIRED_CAPABILITIES.get(role, set())
    candidate_caps = {str(item).strip().lower() for item in candidate_meta.get("special_capabilities", [])}
    if not required:
        capability_match = 0.6
    else:
        capability_match = 1.0 if required.intersection(candidate_caps) else 0.0

    critical_funcs = ROLE_CRITICAL_FUNCTIONS.get(role, set())
    if critical_funcs and candidate_functions:
        behavior_match = len(candidate_functions.intersection(critical_funcs)) / len(critical_funcs)
    elif critical_funcs:
        behavior_match = 0.0
    else:
        behavior_match = 0.5

    if required:
        # capability is a stronger behavior signal when role is capability-sensitive
        behavior_match = min(1.0, (behavior_match * 0.6) + (capability_match * 0.4))

    attribute_vector_similarity = _attribute_vector_similarity(source_meta, candidate_meta)

    text = _context_text(recipe_context)
    hints = ROLE_CONTEXT_HINTS.get(role, [])
    if hints:
        matched = sum(1 for hint in hints if hint in text)
        context_fit = min(1.0, matched / max(2, len(hints) / 2))
    else:
        context_fit = 0.5

    inventory_bonus = 1.0 if bool(candidate.get("available_in_inventory")) else 0.0

    source_base = _norm(str(source.get("source_base") or source.get("base") or ""))
    candidate_base = _norm(str(candidate.get("candidate_base") or candidate.get("base") or ""))
    same_family_penalty = 0.12 if source_base and source_base == candidate_base else 0.0

    source_name = str(source.get("source_canonical") or source.get("canonical") or source.get("source_raw") or "")
    candidate_name = str(candidate.get("candidate_canonical") or candidate.get("canonical") or candidate.get("candidate") or "")
    name_similarity = _name_similarity(source_name, candidate_name)

    step4_score = float(candidate.get("score") or 0.0)
    if step4_score >= 0.7:
        weak_candidate_penalty = 0.0
    elif step4_score >= 0.4:
        weak_candidate_penalty = 0.06
    else:
        weak_candidate_penalty = 0.10

    hard_reject, reject_reason = apply_hard_rejects(
        source,
        candidate,
        role,
        recipe_context,
        source_meta=source_meta,
        candidate_meta=candidate_meta,
    )

    feature_scores = {
        "role_fit": round(role_fit, 4),
        "function_overlap": round(function_overlap, 4),
        "texture_similarity": round(texture_similarity, 4),
        "behavior_match": round(behavior_match, 4),
        "moisture_similarity": round(moisture_similarity, 4),
        "fat_similarity": round(fat_similarity, 4),
        "acidity_similarity": round(acidity_similarity, 4),
        "property_similarity": round(property_similarity, 4),
        "capability_match": round(capability_match, 4),
        "attribute_vector_similarity": round(attribute_vector_similarity, 4),
        "name_similarity": round(name_similarity, 4),
        "context_fit": round(context_fit, 4),
        "inventory_bonus": round(inventory_bonus, 4),
        "same_family_penalty": round(same_family_penalty, 4),
        "weak_candidate_penalty": round(weak_candidate_penalty, 4),
        "hard_reject_flag": bool(hard_reject),
    }

    return {
        "feature_scores": feature_scores,
        "source_metadata": source_meta,
        "candidate_metadata": candidate_meta,
        "metadata_completeness": round(_metadata_completeness(candidate_meta), 4),
        "reject_reason": reject_reason,
    }


def compute_rank_score(feature_scores: Dict[str, float]) -> float:
    """Compute weighted rank score in 0..1 range."""
    if feature_scores.get("hard_reject_flag"):
        return 0.0

    weighted_sum = (
        (RANK_WEIGHTS["role_fit"] * feature_scores["role_fit"])
        + (RANK_WEIGHTS["function_overlap"] * feature_scores["function_overlap"])
        + (RANK_WEIGHTS["behavior_match"] * feature_scores["behavior_match"])
        + (RANK_WEIGHTS["attribute_vector_similarity"] * feature_scores["attribute_vector_similarity"])
        + (RANK_WEIGHTS["property_similarity"] * feature_scores["property_similarity"])
        + (RANK_WEIGHTS["context_fit"] * feature_scores["context_fit"])
        + (RANK_WEIGHTS["inventory_bonus"] * feature_scores["inventory_bonus"])
    )

    penalties = (
        feature_scores["same_family_penalty"]
        + feature_scores["weak_candidate_penalty"]
        + (feature_scores.get("name_similarity", 0.0) * 0.03)
    )
    score = weighted_sum - penalties
    return max(0.0, min(0.99, round(score, 4)))


def compute_rank_confidence(
    feature_scores: Dict[str, float],
    role_confidence: float,
    metadata_completeness: float,
    warning_count: int,
    top_margin: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """Compute confidence independently from rank score."""
    role_component = max(0.0, min(1.0, float(role_confidence)))
    support_component = (
        (feature_scores["role_fit"] * 0.34)
        + (feature_scores["function_overlap"] * 0.24)
        + (feature_scores.get("behavior_match", 0.0) * 0.18)
        + (feature_scores.get("attribute_vector_similarity", 0.0) * 0.14)
        + (feature_scores["property_similarity"] * 0.10)
    )

    margin_component = 0.5 if top_margin is None else max(0.0, min(1.0, 0.5 + (top_margin * 1.5)))
    warning_penalty = min(0.35, warning_count * 0.08)

    confidence = (
        (role_component * 0.35)
        + (support_component * 0.35)
        + (metadata_completeness * 0.2)
        + (margin_component * 0.1)
        - warning_penalty
    )
    confidence = max(0.0, min(0.99, round(confidence, 4)))

    return confidence, {
        "role_component": round(role_component, 4),
        "support_component": round(support_component, 4),
        "metadata_completeness": round(metadata_completeness, 4),
        "margin_component": round(margin_component, 4),
        "warning_penalty": round(warning_penalty, 4),
    }


def _quality_band(rank_score: float, rejected: bool) -> str:
    if rejected:
        return "reject"
    if rank_score >= QUALITY_THRESHOLDS["best_match"]:
        return "best_match"
    if rank_score >= QUALITY_THRESHOLDS["good_with_adjustment"]:
        return "good_with_adjustment"
    if rank_score >= QUALITY_THRESHOLDS["workable"]:
        return "workable"
    return "weak_option"


def _recommendation_tier(quality_band: str) -> str:
    band = _norm(quality_band)
    if band == "best_match":
        return "best"
    if band in {"good_with_adjustment", "workable"}:
        return "acceptable"
    return "not_recommended"


def rank_substitute_candidates(
    step4_result: Dict[str, Any],
    recipe_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Rank candidates for one source ingredient from Step 4 output."""
    source = {
        "source_raw": str(step4_result.get("source", {}).get("raw", "")),
        "source_canonical": str(step4_result.get("source", {}).get("canonical", "")),
        "source_base": str(step4_result.get("source", {}).get("base", "")),
        "inferred_role": str(step4_result.get("inferred_role", "")),
    }
    role_confidence = float(step4_result.get("role_confidence", 0.4))

    all_candidates: List[Dict[str, Any]] = []
    for candidate in step4_result.get("candidates", []):
        item = dict(candidate)
        features_pack = extract_candidate_features(source, item, recipe_context)
        feature_scores = features_pack["feature_scores"]

        rank_score = compute_rank_score(feature_scores)

        warnings = list(item.get("warnings", []))
        reject_reason = features_pack.get("reject_reason")
        if reject_reason:
            warnings.append(reject_reason)

        all_candidates.append(
            {
                "source_raw": source["source_raw"],
                "source_canonical": source["source_canonical"],
                "source_base": source["source_base"],
                "inferred_role": source["inferred_role"],
                "candidate": str(item.get("candidate", "")),
                "candidate_canonical": str(item.get("candidate_canonical", "")),
                "candidate_base": str(item.get("candidate_base", "")),
                "available_in_inventory": bool(item.get("available_in_inventory", False)),
                "rank_score": rank_score,
                "feature_scores": feature_scores,
                "warnings": warnings,
                "evidence": list(item.get("evidence", [])),
                "step4_score": float(item.get("score", 0.0)),
                "metadata_completeness": features_pack["metadata_completeness"],
                "reject_reason": reject_reason,
            }
        )

    all_candidates.sort(key=lambda row: (-row["rank_score"], row["candidate"]))

    for idx, row in enumerate(all_candidates):
        if idx < len(all_candidates) - 1:
            margin = row["rank_score"] - all_candidates[idx + 1]["rank_score"]
        else:
            margin = row["rank_score"]

        confidence, confidence_breakdown = compute_rank_confidence(
            feature_scores=row["feature_scores"],
            role_confidence=role_confidence,
            metadata_completeness=float(row["metadata_completeness"]),
            warning_count=len(row["warnings"]),
            top_margin=margin,
        )

        rejected = bool(row["feature_scores"].get("hard_reject_flag")) or row["rank_score"] <= 0.0
        row["confidence"] = confidence
        row["confidence_breakdown"] = confidence_breakdown
        row["quality_band"] = _quality_band(row["rank_score"], rejected)
        row["recommendation_tier"] = _recommendation_tier(row["quality_band"])

    min_recommend_score = (
        MIN_RECOMMEND_SCORE_INVENTORY_ONLY
        if bool(step4_result.get("inventory_only", False))
        else MIN_RECOMMEND_SCORE
    )

    ranked_candidates = [
        row
        for row in all_candidates
        if row.get("quality_band") not in {"weak_option", "reject"}
        and float(row.get("rank_score", 0.0)) >= min_recommend_score
    ]

    return {
        "source": step4_result.get("source", {}),
        "inferred_role": step4_result.get("inferred_role", ""),
        "role_confidence": role_confidence,
        "inventory_only": bool(step4_result.get("inventory_only", False)),
        "role_resolution": step4_result.get("role_resolution", ""),
        "ranked_candidates": ranked_candidates,
        "candidate_count_before_filter": len(all_candidates),
        "candidate_count_after_filter": len(ranked_candidates),
        "not_recommended_count": len(all_candidates) - len(ranked_candidates),
    }


def rank_candidates_for_recipe(
    step4_results: List[Dict[str, Any]],
    recipe_context: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Rank candidates for a list of Step 4 source outputs."""
    return [rank_substitute_candidates(result, recipe_context=recipe_context) for result in step4_results]
