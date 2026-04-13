from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException

from api.schemas import RemixRequest
from recipe_utils import normalize_ingredient, normalize_ingredient_list
from utils.step_text import generate_fallback_tip, normalize_original_steps


def normalize_key(text: str) -> str:
    return normalize_ingredient(text or "").strip().lower()


def _single_sentence(text: str, fallback: str) -> str:
    candidate = (text or "").strip()
    if not candidate:
        return fallback
    parts = [part.strip() for part in candidate.replace("!", ".").replace("?", ".").split(".") if part.strip()]
    if not parts:
        return fallback
    return f"{parts[0]}."


def _deterministic_main_reason(source: str, target: str, user_items_norm: List[str]) -> str:
    if normalize_key(target) in set(user_items_norm):
        return f"Selected to replace {source} with an available ingredient while preserving the main cooking role."
    return "Chosen to keep a similar cooking role with ingredients from your fridge."


def _deterministic_seasoning_reason(source: str, target: str, user_items_norm: List[str]) -> str:
    if normalize_key(target) in set(user_items_norm):
        return f"Selected to replace {source} with an available ingredient while preserving flavor compatibility."
    return "Chosen to keep a compatible flavor profile with what you have."


def _validate_main_substitutions(payload: RemixRequest, user_set: set[str]) -> None:
    for source, target in payload.selected_main_subs.items():
        normalized_target = normalize_key(target)
        if normalized_target not in user_set:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid main substitution: '{target}' is not in user ingredients",
            )


def _validate_seasoning_substitutions(payload: RemixRequest, user_set: set[str]) -> None:
    for source, target in payload.selected_seasoning_subs.items():
        normalized_target = normalize_key(target)
        if normalized_target not in user_set:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid seasoning substitution: '{target}' is not in user ingredients",
            )


def _build_fallback_pairs(
    main_pairs: List[Dict[str, str]],
    seasoning_pairs: List[Dict[str, str]],
    user_items_norm: List[str],
) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    fallback_main = [
        {
            "from": pair["from"],
            "to": pair["to"],
            "reason": _single_sentence(
                _deterministic_main_reason(pair["from"], pair["to"], user_items_norm),
                "Chosen to keep a similar cooking role with ingredients from your fridge.",
            ),
        }
        for pair in main_pairs
    ]
    fallback_seasoning = [
        {
            "from": pair["from"],
            "to": pair["to"],
            "reason": _single_sentence(
                _deterministic_seasoning_reason(pair["from"], pair["to"], user_items_norm),
                "Chosen to keep a compatible flavor profile with what you have.",
            ),
        }
        for pair in seasoning_pairs
    ]
    return fallback_main, fallback_seasoning


def _compute_changed_steps(original_steps: List[str], edited_steps: List[str]) -> List[int]:
    return [
        idx
        for idx, (original, edited) in enumerate(zip(original_steps, edited_steps))
        if str(original) != str(edited)
    ]


def _join_non_empty(parts: List[str]) -> str:
    return " ".join([p.strip() for p in parts if str(p or "").strip()]).strip()


def _v2_reason_for_selected(
    source: str,
    target: str,
    ranked_candidates: List[Dict[str, Any]],
    fallback_reason: str,
) -> str:
    target_norm = normalize_key(target)
    for row in ranked_candidates:
        cand_norm = normalize_key(
            str(
                row.get("candidate")
                or row.get("candidate_canonical")
                or row.get("candidate_base")
                or ""
            )
        )
        if cand_norm != target_norm:
            continue

        quality_band = str(row.get("quality_band") or "").strip()
        confidence = float(row.get("confidence") or 0.0)
        source_role = str(row.get("inferred_role") or "").strip()
        support = str(row.get("supporting_note") or "").strip()

        base = (
            f"Role fit: {source_role or 'compatible'}; "
            f"quality: {quality_band or 'workable'}; confidence: {confidence:.2f}."
        )
        if support:
            return _single_sentence(f"{base} {support}", fallback_reason)
        return _single_sentence(base, fallback_reason)

    return _single_sentence(fallback_reason, fallback_reason)


def _v2_note_from_adjustment(adjustment: Dict[str, Any]) -> str:
    amount_note = str((adjustment.get("amount_adjustment") or {}).get("note") or "").strip()
    method_note = str((adjustment.get("method_adjustment") or {}).get("note") or "").strip()
    prep_note = str((adjustment.get("preprocessing") or {}).get("note") or "").strip()
    timing_note = str((adjustment.get("timing_adjustment") or {}).get("note") or "").strip()
    quality_band = str(adjustment.get("quality_band") or "").strip()
    confidence = float(adjustment.get("confidence") or 0.0)

    combined = _join_non_empty([prep_note, method_note, timing_note, amount_note])
    if not combined:
        return ""

    prefix = f"[{quality_band or 'workable'}:{confidence:.2f}]"
    return _single_sentence(f"{prefix} {combined}", combined)


def _v2_flavor_summary(selected_adjustments: List[Dict[str, Any]], rewrite_mode: str) -> str:
    if rewrite_mode == "caution_no_rewrite":
        return "Substitutions applied conservatively. Original steps were preserved due to safety gating."

    counts: Dict[str, int] = {}
    for adj in selected_adjustments:
        band = str(adj.get("quality_band") or "workable").strip().lower()
        counts[band] = counts.get(band, 0) + 1

    if counts.get("best_match"):
        return "Substitutions applied with high compatibility and minimal flavor disruption."
    if counts.get("good_with_adjustment"):
        return "Substitutions applied with minor method adjustments to preserve flavor and texture."
    if counts.get("workable"):
        return "Substitutions applied with conservative adjustments; expect slight flavor or texture differences."
    if counts.get("weak_option") or counts.get("reject"):
        return "Substitutions were safety-limited due to low compatibility."
    return "Substitutions applied."


def _build_v2_failure_response(
    payload: RemixRequest,
    original_steps: List[str],
    fallback_main: List[Dict[str, str]],
    fallback_seasoning: List[Dict[str, str]],
) -> Dict[str, Any]:
    substitution_explanations = {
        f"{item['from']} -> {item['to']}": item["reason"]
        for item in (fallback_main + fallback_seasoning)
    }

    return {
        "recipe_id": payload.recipe_id,
        "substitutions": {
            "main": fallback_main,
            "seasoning": fallback_seasoning,
        },
        "flavor_change_summary": "Unable to apply v2 rewrite safely. Original steps were preserved.",
        "edited_steps": original_steps,
        "changed_steps": [],
        "substitution_explanations": substitution_explanations,
        "method_adjustment_notes": {},
        "step_tips": [generate_fallback_tip(s) for s in original_steps],
        "missing_remaining": [],
    }


def build_remix_response(payload: RemixRequest, recipe: Dict[str, Any]) -> Dict[str, Any]:
    """Build /api/remix response using v2 pipeline only.

    Flow:
    - validate selected substitutions against current rules
    - run Step 3-7 services
    - map results into the existing frontend response contract

    There is no legacy engine branch in this function.
    """
    user_items_norm = normalize_ingredient_list(payload.user_ingredients)
    user_set = set(user_items_norm)

    _validate_main_substitutions(payload, user_set)
    _validate_seasoning_substitutions(payload, user_set)

    main_pairs = [{"from": source, "to": target} for source, target in payload.selected_main_subs.items()]
    seasoning_pairs = [{"from": source, "to": target} for source, target in payload.selected_seasoning_subs.items()]
    fallback_main, fallback_seasoning = _build_fallback_pairs(main_pairs, seasoning_pairs, user_items_norm)

    original_steps = normalize_original_steps(recipe.get("directions", []))

    try:
        from ingredient_normalizer_v2 import normalize_ingredient_v2
        from services.adjustment_metadata_service import build_adjustments_for_candidates
        from services.role_inference_service import build_recipe_context_from_recipe, infer_role_for_ingredient
        from services.step_rewrite_service import rewrite_recipe_steps
        from services.substitute_generation_service import generate_substitute_candidates
        from services.substitute_ranking_service import rank_substitute_candidates

        recipe_context = build_recipe_context_from_recipe(recipe)

        selected_candidates: List[Dict[str, str]] = []
        selected_adjustments: List[Dict[str, Any]] = []
        adjustment_bundles: List[Dict[str, Any]] = []
        reason_by_pair: Dict[str, str] = {}

        all_pairs = main_pairs + seasoning_pairs
        for pair in all_pairs:
            source = pair["from"]
            target = pair["to"]

            norm = normalize_ingredient_v2(source).to_dict()
            role_result = infer_role_for_ingredient(norm, recipe_context)
            norm["inferred_role"] = str(role_result.get("inferred_role") or "")
            norm["role_confidence"] = float(role_result.get("confidence") or 0.0)

            step4 = generate_substitute_candidates(
                norm,
                recipe_context,
                user_inventory=list(payload.user_ingredients),
                inventory_only=False,
            )
            step5 = rank_substitute_candidates(step4, recipe_context=recipe_context)
            step6 = build_adjustments_for_candidates(step5, recipe_context=recipe_context)

            ranked_candidates = step5.get("ranked_candidates", [])
            selected_adj = None
            target_norm = normalize_key(target)
            for adj in step6.get("adjustments", []):
                cand_norm = normalize_key(
                    str(
                        adj.get("candidate")
                        or adj.get("candidate_canonical")
                        or adj.get("candidate_base")
                        or ""
                    )
                )
                if cand_norm == target_norm:
                    selected_adj = adj
                    break

            if selected_adj is None:
                selected_adj = {
                    "source_canonical": source,
                    "source_base": source,
                    "candidate": target,
                    "inferred_role": str(norm.get("inferred_role") or ""),
                    "quality_band": "weak_option",
                    "confidence": 0.0,
                    "suitability_policy": "weak_option",
                    "risk_flags": ["weak_substitute"],
                    "amount_adjustment": {"type": "cautious", "note": "Selected candidate not found in ranked pool."},
                    "method_adjustment": {"needed": False, "note": ""},
                    "preprocessing": {"needed": False, "note": ""},
                    "timing_adjustment": {"needed": False, "note": ""},
                    "expected_changes": {
                        "flavor": "Potential flavor mismatch.",
                        "texture": "Potential texture mismatch.",
                        "moisture": "Potential moisture mismatch.",
                    },
                }

            selected_candidates.append({"source_canonical": source, "candidate": target})
            selected_adjustments.append(selected_adj)
            adjustment_bundles.append(
                {
                    "source": {"canonical": source, "base": source},
                    "adjustments": [selected_adj],
                }
            )

            pair_key = f"{source} -> {target}"
            fallback_pair_reason = next(
                (
                    item["reason"]
                    for item in (fallback_main + fallback_seasoning)
                    if item["from"] == source and item["to"] == target
                ),
                "Chosen to keep a compatible cooking role.",
            )
            reason_by_pair[pair_key] = _v2_reason_for_selected(source, target, ranked_candidates, fallback_pair_reason)

        step7 = rewrite_recipe_steps(
            original_steps=original_steps,
            selected_substitutions=selected_candidates,
            adjustment_metadata_list=adjustment_bundles,
        )

        edited_steps = list(step7.get("rewritten_steps") or original_steps)
        if len(edited_steps) != len(original_steps):
            return _build_v2_failure_response(payload, original_steps, fallback_main, fallback_seasoning)

        changed_steps = _compute_changed_steps(original_steps, edited_steps)

        substitution_explanations = dict(reason_by_pair)
        method_adjustment_notes: Dict[str, str] = {}
        for pair, adj in zip(all_pairs, selected_adjustments):
            key = f"{pair['from']} -> {pair['to']}"
            note = _v2_note_from_adjustment(adj)
            if note:
                method_adjustment_notes[key] = note

        raw_warnings = [str(w).strip() for w in step7.get("rewrite_warnings", []) if str(w).strip()]
        step_tips = [generate_fallback_tip(step) for step in edited_steps]
        if raw_warnings:
            for idx in changed_steps[:2]:
                if 0 <= idx < len(step_tips):
                    step_tips[idx] = _single_sentence(raw_warnings[0], step_tips[idx])

        flavor_change_summary = _v2_flavor_summary(selected_adjustments, str(step7.get("rewrite_mode") or ""))
        fallback_reason = str(step7.get("fallback_reason") or "").strip()
        if fallback_reason:
            flavor_change_summary = _single_sentence(
                f"{flavor_change_summary} {fallback_reason}",
                flavor_change_summary,
            )

        if payload.allergies:
            lowered = flavor_change_summary.lower()
            if "allerg" not in lowered and "caution" not in lowered:
                flavor_change_summary = f"{flavor_change_summary} Caution: check labels against your listed allergies."

        safe_main = []
        for item in fallback_main:
            key = f"{item['from']} -> {item['to']}"
            safe_main.append({
                "from": item["from"],
                "to": item["to"],
                "reason": substitution_explanations.get(key, item["reason"]),
            })

        safe_seasoning = []
        for item in fallback_seasoning:
            key = f"{item['from']} -> {item['to']}"
            safe_seasoning.append({
                "from": item["from"],
                "to": item["to"],
                "reason": substitution_explanations.get(key, item["reason"]),
            })

        return {
            "recipe_id": payload.recipe_id,
            "substitutions": {
                "main": safe_main,
                "seasoning": safe_seasoning,
            },
            "flavor_change_summary": flavor_change_summary,
            "edited_steps": edited_steps,
            "changed_steps": changed_steps,
            "substitution_explanations": substitution_explanations,
            "method_adjustment_notes": method_adjustment_notes,
            "step_tips": step_tips,
            "missing_remaining": [],
        }

    except Exception:
        # Conservative v2-only failure handling: preserve original steps and contract.
        return _build_v2_failure_response(payload, original_steps, fallback_main, fallback_seasoning)
