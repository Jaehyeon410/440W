"""Adjustment metadata service (Step 6, shadow mode).

Consumes Step 5 ranked candidates and produces conservative, structured
adjustment guidance. This module does not rewrite recipe steps.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.ingredient_metadata_service import get_metadata


PROPERTY_LEVEL = {"low": 0, "medium": 1, "high": 2}

SUITABILITY_BY_QUALITY = {
    "best_match": "allowed",
    "good_with_adjustment": "allowed_with_adjustment",
    "workable": "caution",
    "weak_option": "weak_option",
    "reject": "reject",
    "not_recommended": "reject",
}


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def _meta(canonical: str, base: str) -> Dict[str, Any]:
    canonical_key = _norm(canonical)
    base_key = _norm(base)

    if canonical_key:
        m = get_metadata(canonical_key)
        if m.get("possible_functions"):
            return m
    if base_key:
        return get_metadata(base_key)
    return get_metadata(canonical_key)


def _prop_delta(src: Dict[str, Any], cand: Dict[str, Any], key: str) -> int:
    src_level = PROPERTY_LEVEL.get(_norm(str(src.get("properties", {}).get(key, "medium"))), 1)
    cand_level = PROPERTY_LEVEL.get(_norm(str(cand.get("properties", {}).get(key, "medium"))), 1)
    return cand_level - src_level


def _caps(meta: Dict[str, Any]) -> set[str]:
    return {str(item).strip().lower() for item in meta.get("special_capabilities", [])}


def _quality_band(candidate: Dict[str, Any]) -> str:
    recommendation_tier = _norm(str(candidate.get("recommendation_tier") or ""))
    if recommendation_tier == "not_recommended":
        return "reject"
    return _norm(str(candidate.get("quality_band") or "workable"))


def _recommendation_tier(candidate: Dict[str, Any]) -> str:
    tier = _norm(str(candidate.get("recommendation_tier") or ""))
    if tier:
        return tier
    band = _quality_band(candidate)
    if band == "best_match":
        return "best"
    if band in {"good_with_adjustment", "workable"}:
        return "acceptable"
    return "not_recommended"


def infer_amount_adjustment(
    source_ingredient: Dict[str, Any],
    candidate: Dict[str, Any],
    inferred_role: str,
    recipe_context: Optional[Any] = None,
) -> Dict[str, str]:
    role = _norm(inferred_role)
    band = _quality_band(candidate)

    source_meta = _meta(
        str(source_ingredient.get("source_canonical") or source_ingredient.get("canonical") or ""),
        str(source_ingredient.get("source_base") or source_ingredient.get("base") or ""),
    )
    candidate_meta = _meta(
        str(candidate.get("candidate_canonical") or candidate.get("candidate") or ""),
        str(candidate.get("candidate_base") or ""),
    )

    if band == "reject":
        return {
            "type": "not_recommended",
            "note": "Candidate is rejected for this role. Do not rely on amount substitution guidance.",
        }

    if role == "thickener":
        if "gelatinizing" in _caps(candidate_meta):
            return {
                "type": "start_with_less",
                "note": "Start with less than the source amount, then increase gradually to avoid over-thickening.",
            }
        return {
            "type": "may_need_more",
            "note": "Candidate may thicken less efficiently. Start near the same amount and reduce longer if needed.",
        }

    if role == "aerated_base":
        if "whippable" in _caps(candidate_meta):
            return {
                "type": "similar_amount",
                "note": "Start with roughly the same amount and adjust slightly based on whipped volume and stability.",
            }
        return {
            "type": "reduced_confidence",
            "note": "Use a conservative amount first because aeration performance may be weaker than the source.",
        }

    if role == "structure":
        return {
            "type": "ratio_sensitive",
            "note": "Keep amount close to the source and adjust hydration gradually if dough/batter feels too dry or wet.",
        }

    if role == "sweetener":
        sweet_delta = _prop_delta(source_meta, candidate_meta, "sweetness")
        moisture_delta = _prop_delta(source_meta, candidate_meta, "moisture")
        if sweet_delta > 0:
            return {
                "type": "start_with_less",
                "note": "Candidate is sweeter; start with less and taste-adjust.",
            }
        if moisture_delta > 0:
            return {
                "type": "start_with_less",
                "note": "Candidate adds more moisture (often liquid sweeteners); start with less and adjust gradually.",
            }
        if sweet_delta < 0:
            return {
                "type": "may_need_more",
                "note": "Candidate is less sweet; you may need slightly more to reach target sweetness.",
            }
        return {
            "type": "similar_amount",
            "note": "Start with a similar amount and adjust to taste.",
        }

    if role == "acidity_provider":
        return {
            "type": "start_with_less",
            "note": "Start with less, taste, then increase to avoid overshooting acidity.",
        }

    if role == "topping":
        if band in {"best_match", "good_with_adjustment"}:
            return {
                "type": "similar_amount",
                "note": "Use a similar topping amount; adjust by desired crunch and visual coverage.",
            }
        return {
            "type": "cautious",
            "note": "Use a smaller trial amount first and confirm flavor/texture fit.",
        }

    return {
        "type": "similar_amount",
        "note": "Begin near the source amount and adjust after tasting/texture check.",
    }


def infer_method_adjustment(
    source_ingredient: Dict[str, Any],
    candidate: Dict[str, Any],
    inferred_role: str,
    recipe_context: Optional[Any] = None,
) -> Dict[str, Any]:
    role = _norm(inferred_role)
    band = _quality_band(candidate)

    source_meta = _meta(
        str(source_ingredient.get("source_canonical") or source_ingredient.get("canonical") or ""),
        str(source_ingredient.get("source_base") or source_ingredient.get("base") or ""),
    )
    candidate_meta = _meta(
        str(candidate.get("candidate_canonical") or candidate.get("candidate") or ""),
        str(candidate.get("candidate_base") or ""),
    )

    if band == "reject":
        return {
            "needed": False,
            "note": "No method adjustment guidance because candidate is rejected.",
        }

    if role == "thickener":
        return {
            "needed": True,
            "note": "Whisk into a small amount of cold liquid first (slurry), then add gradually to avoid clumping.",
        }

    if role == "aerated_base":
        if "whippable" in _caps(candidate_meta):
            return {
                "needed": True,
                "note": "Whip separately before folding/serving, and avoid overmixing after aeration.",
            }
        return {
            "needed": True,
            "note": "Candidate may not aerate well. Fold gently and expect lower lift/stability.",
        }

    if role == "structure":
        return {
            "needed": True,
            "note": "Mix until structure forms, then stop early to avoid overworking. Adjust hydration progressively.",
        }

    if role == "topping":
        cand_base = _norm(str(candidate.get("candidate_base") or ""))
        if cand_base in {"almond", "walnut", "pecans", "seeds", "pumpkin seeds"}:
            return {
                "needed": True,
                "note": "Optional: lightly toast/chop for better aroma and texture.",
            }
        return {
            "needed": False,
            "note": "Usually no major method change needed for topping substitutions.",
        }

    if role == "sweetener":
        moisture_delta = _prop_delta(source_meta, candidate_meta, "moisture")
        if moisture_delta > 0:
            return {
                "needed": True,
                "note": "Liquid sweetener may loosen the mixture; reduce other liquids slightly if needed.",
            }
        return {
            "needed": False,
            "note": "No major method change expected; dissolve and taste-adjust.",
        }

    return {
        "needed": False,
        "note": "No major method adjustment expected.",
    }


def infer_risk_flags(
    source_ingredient: Dict[str, Any],
    candidate: Dict[str, Any],
    inferred_role: str,
    quality_band: str,
    recipe_context: Optional[Any] = None,
) -> List[str]:
    flags: List[str] = []

    role = _norm(inferred_role)
    band = _norm(quality_band)
    source_meta = _meta(
        str(source_ingredient.get("source_canonical") or source_ingredient.get("canonical") or ""),
        str(source_ingredient.get("source_base") or source_ingredient.get("base") or ""),
    )
    candidate_meta = _meta(
        str(candidate.get("candidate_canonical") or candidate.get("candidate") or ""),
        str(candidate.get("candidate_base") or ""),
    )

    if band == "reject":
        flags.extend(["rejected_candidate", "weak_substitute"])
        return sorted(set(flags))
    if band == "weak_option":
        flags.append("weak_substitute")

    moisture_delta = _prop_delta(source_meta, candidate_meta, "moisture")
    sweet_delta = _prop_delta(source_meta, candidate_meta, "sweetness")
    acidity_delta = _prop_delta(source_meta, candidate_meta, "acidity")

    src_texture = _norm(str(source_meta.get("texture", "")))
    cand_texture = _norm(str(candidate_meta.get("texture", "")))
    if src_texture and cand_texture and src_texture != cand_texture:
        flags.append("texture_shift")

    src_flavor = _norm(str(source_meta.get("flavor_strength", "")))
    cand_flavor = _norm(str(candidate_meta.get("flavor_strength", "")))
    if src_flavor and cand_flavor and src_flavor != cand_flavor:
        flags.append("flavor_shift")

    if moisture_delta != 0:
        flags.append("moisture_shift")
    if sweet_delta > 0:
        flags.append("over_sweetening_risk")
    if acidity_delta > 0:
        flags.append("acidity_balance_risk")

    caps = _caps(candidate_meta)
    if role == "aerated_base" and "whippable" not in caps:
        flags.append("whipping_risk")
    if role == "thickener":
        flags.append("thickening_risk")
    if role == "structure" and (cand_texture not in {"powder", "soft"}):
        flags.append("structure_risk")

    return sorted(set(flags))


def _infer_preprocessing(
    source_ingredient: Dict[str, Any],
    candidate: Dict[str, Any],
    inferred_role: str,
) -> Dict[str, Any]:
    role = _norm(inferred_role)
    band = _quality_band(candidate)
    cand_base = _norm(str(candidate.get("candidate_base") or ""))

    if band == "reject":
        return {"needed": False, "note": ""}

    if role == "aerated_base":
        return {"needed": True, "note": "Chill thoroughly before whipping for better stability."}

    if role == "topping" and cand_base in {"almond", "walnut", "pecans", "seed", "seeds", "pumpkin seeds"}:
        return {"needed": True, "note": "Optional: toast briefly to enhance aroma and crunch."}

    if role == "thickener":
        return {"needed": True, "note": "Mix with a little cold liquid first to make a smooth slurry."}

    return {"needed": False, "note": ""}


def _infer_timing_adjustment(
    source_ingredient: Dict[str, Any],
    candidate: Dict[str, Any],
    inferred_role: str,
) -> Dict[str, Any]:
    role = _norm(inferred_role)
    band = _quality_band(candidate)

    if band == "reject":
        return {"needed": False, "note": ""}

    if role == "thickener":
        return {
            "needed": True,
            "note": "Add gradually and simmer briefly between additions to control final thickness.",
        }
    if role == "aerated_base":
        return {
            "needed": True,
            "note": "Whip close to serving time to reduce collapse risk.",
        }
    if role == "sweetener":
        return {
            "needed": True,
            "note": "Add in stages and taste as you go, especially with liquid sweeteners.",
        }

    return {"needed": False, "note": ""}


def _expected_changes(
    source_ingredient: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, str]:
    source_meta = _meta(
        str(source_ingredient.get("source_canonical") or source_ingredient.get("canonical") or ""),
        str(source_ingredient.get("source_base") or source_ingredient.get("base") or ""),
    )
    candidate_meta = _meta(
        str(candidate.get("candidate_canonical") or candidate.get("candidate") or ""),
        str(candidate.get("candidate_base") or ""),
    )

    moisture_delta = _prop_delta(source_meta, candidate_meta, "moisture")

    src_texture = _norm(str(source_meta.get("texture", "")))
    cand_texture = _norm(str(candidate_meta.get("texture", "")))
    if src_texture == cand_texture:
        texture_note = "Minimal texture change expected."
    else:
        texture_note = f"Texture may shift from {src_texture or 'current'} to {cand_texture or 'new'} behavior."

    src_flavor = _norm(str(source_meta.get("flavor_strength", "")))
    cand_flavor = _norm(str(candidate_meta.get("flavor_strength", "")))
    if src_flavor == cand_flavor:
        flavor_note = "Flavor intensity is expected to stay similar."
    else:
        flavor_note = "Flavor intensity may shift; taste and rebalance seasoning as needed."

    if moisture_delta > 0:
        moisture_note = "Candidate may add more moisture; monitor consistency and reduce liquids if needed."
    elif moisture_delta < 0:
        moisture_note = "Candidate may reduce moisture; add liquid gradually if mixture feels dry."
    else:
        moisture_note = "Minimal moisture change expected."

    return {
        "flavor": flavor_note,
        "texture": texture_note,
        "moisture": moisture_note,
    }


def _policy_for_quality(quality_band: str) -> str:
    return SUITABILITY_BY_QUALITY.get(_norm(quality_band), "caution")


def build_adjustment_metadata(
    source_ingredient: Dict[str, Any],
    ranked_candidate: Dict[str, Any],
    recipe_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build structured adjustment metadata for one ranked candidate."""
    inferred_role = _norm(str(ranked_candidate.get("inferred_role") or source_ingredient.get("inferred_role") or ""))
    quality_band = _quality_band(ranked_candidate)
    recommendation_tier = _recommendation_tier(ranked_candidate)
    suitability_policy = _policy_for_quality(quality_band)

    if quality_band == "reject":
        risk_flags = infer_risk_flags(source_ingredient, ranked_candidate, inferred_role, quality_band, recipe_context)
        return {
            "source_raw": str(ranked_candidate.get("source_raw") or source_ingredient.get("source_raw") or ""),
            "source_canonical": str(ranked_candidate.get("source_canonical") or source_ingredient.get("source_canonical") or ""),
            "source_base": str(ranked_candidate.get("source_base") or source_ingredient.get("source_base") or ""),
            "candidate": str(ranked_candidate.get("candidate", "")),
            "candidate_canonical": str(ranked_candidate.get("candidate_canonical", "")),
            "candidate_base": str(ranked_candidate.get("candidate_base", "")),
            "inferred_role": inferred_role,
            "quality_band": quality_band,
            "recommendation_tier": recommendation_tier,
            "rank_score": float(ranked_candidate.get("rank_score", 0.0)),
            "confidence": float(ranked_candidate.get("confidence", 0.0)),
            "amount_adjustment": {
                "type": "not_recommended",
                "note": "Candidate is rejected; no reliable adjustment plan available.",
            },
            "preprocessing": {"needed": False, "note": ""},
            "method_adjustment": {"needed": False, "note": ""},
            "timing_adjustment": {"needed": False, "note": ""},
            "expected_changes": {
                "flavor": "Unreliable substitution; flavor outcome is high risk.",
                "texture": "Unreliable substitution; texture outcome is high risk.",
                "moisture": "Unreliable substitution; moisture outcome is high risk.",
            },
            "risk_flags": risk_flags,
            "suitability_policy": suitability_policy,
            "explanation": [
                "Candidate was classified as reject by ranking layer.",
                "Only warning-level metadata is returned for safety.",
            ],
        }

    amount_adjustment = infer_amount_adjustment(source_ingredient, ranked_candidate, inferred_role, recipe_context)
    preprocessing = _infer_preprocessing(source_ingredient, ranked_candidate, inferred_role)
    method_adjustment = infer_method_adjustment(source_ingredient, ranked_candidate, inferred_role, recipe_context)
    timing_adjustment = _infer_timing_adjustment(source_ingredient, ranked_candidate, inferred_role)
    expected_changes = _expected_changes(source_ingredient, ranked_candidate)
    risk_flags = infer_risk_flags(source_ingredient, ranked_candidate, inferred_role, quality_band, recipe_context)

    explanation = [
        f"Candidate ranked as {quality_band} for role '{inferred_role}'.",
        f"Rank score {float(ranked_candidate.get('rank_score', 0.0)):.2f} with confidence {float(ranked_candidate.get('confidence', 0.0)):.2f}.",
    ]

    feature_scores = ranked_candidate.get("feature_scores", {})
    if isinstance(feature_scores, dict):
        if float(feature_scores.get("role_fit", 0.0)) >= 0.8:
            explanation.append("Candidate strongly supports the inferred role.")
        if float(feature_scores.get("capability_match", 0.0)) >= 0.8:
            explanation.append("Role-critical capability match is strong.")

    if quality_band == "workable":
        explanation.append("Use cautious adjustments and verify taste/texture during cooking.")
    if quality_band == "weak_option":
        explanation.append("This is a weak option; prefer higher-ranked alternatives when available.")

    # Keep weak_option conservative: do not over-specify method guidance.
    if quality_band == "weak_option":
        method_adjustment = {
            "needed": bool(method_adjustment.get("needed", False)),
            "note": "Use minimal adjustments and validate in small increments.",
        }

    return {
        "source_raw": str(ranked_candidate.get("source_raw") or source_ingredient.get("source_raw") or ""),
        "source_canonical": str(ranked_candidate.get("source_canonical") or source_ingredient.get("source_canonical") or ""),
        "source_base": str(ranked_candidate.get("source_base") or source_ingredient.get("source_base") or ""),
        "candidate": str(ranked_candidate.get("candidate", "")),
        "candidate_canonical": str(ranked_candidate.get("candidate_canonical", "")),
        "candidate_base": str(ranked_candidate.get("candidate_base", "")),
        "inferred_role": inferred_role,
        "quality_band": quality_band,
        "recommendation_tier": recommendation_tier,
        "rank_score": float(ranked_candidate.get("rank_score", 0.0)),
        "confidence": float(ranked_candidate.get("confidence", 0.0)),
        "amount_adjustment": amount_adjustment,
        "preprocessing": preprocessing,
        "method_adjustment": method_adjustment,
        "timing_adjustment": timing_adjustment,
        "expected_changes": expected_changes,
        "risk_flags": risk_flags,
        "suitability_policy": suitability_policy,
        "explanation": explanation,
    }


def build_adjustments_for_candidates(
    ranked_candidates_result: Dict[str, Any],
    recipe_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build adjustment metadata for all ranked candidates of a source ingredient."""
    source = {
        "source_raw": str(ranked_candidates_result.get("source", {}).get("raw", "")),
        "source_canonical": str(ranked_candidates_result.get("source", {}).get("canonical", "")),
        "source_base": str(ranked_candidates_result.get("source", {}).get("base", "")),
        "inferred_role": str(ranked_candidates_result.get("inferred_role", "")),
    }

    adjustments = [
        build_adjustment_metadata(source, candidate, recipe_context=recipe_context)
        for candidate in ranked_candidates_result.get("ranked_candidates", [])
    ]

    return {
        "source": ranked_candidates_result.get("source", {}),
        "inferred_role": ranked_candidates_result.get("inferred_role", ""),
        "role_confidence": ranked_candidates_result.get("role_confidence", 0.0),
        "inventory_only": bool(ranked_candidates_result.get("inventory_only", False)),
        "adjustments": adjustments,
    }
