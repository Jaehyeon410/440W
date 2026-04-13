"""Shadow pipeline orchestrator (debug integration, shadow mode).

This module is the single entry point for attaching v2 shadow pipeline output
to the remix endpoint.  It is invoked only when RemixRequest.debug_v2 is True
and MUST NOT modify the normal remix result in any way.

Pipeline stages consumed in order:
  Step 1+  normalize_ingredient_v2   (ingredient_normalizer_v2)
  Step 3   infer_role_for_ingredient (role_inference_service)
  Step 4   generate_substitute_candidates
  Step 5   rank_substitute_candidates
  Step 6   build_adjustments_for_candidates
  Step 7   rewrite_recipe_steps
"""

from __future__ import annotations

import os
from typing import Any, Dict, List


_SHADOW_PIPELINE_VERSION = "v2"

# Limit ranked candidates shown per source to keep debug payload compact.
_MAX_RANKED_SHOWN = 3


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def is_shadow_debug_enabled(request_debug: bool) -> bool:
    """Require both an explicit request flag and a server-side env flag.

    This dual gate prevents accidental exposure of debug payloads in normal use.
    """
    env_enabled = os.getenv("ENABLE_SHADOW_PIPELINE_DEBUG", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return bool(request_debug) and env_enabled


def _normalized_substitution_lookup(all_subs: Dict[str, str]) -> Dict[str, str]:
    return {
        _safe_str(source).lower(): _safe_str(target)
        for source, target in (all_subs or {}).items()
        if _safe_str(source) and _safe_str(target)
    }


def build_shadow_rewrite_preview(
    payload: Any,
    recipe: Dict[str, Any],
) -> Dict[str, Any]:
    """Run v2 shadow pipeline stages and return a compact debug payload.

    Any failure inside the pipeline is caught here.  The calling endpoint
    always receives a valid dict; exceptions never propagate to the response.
    """
    # error_stage is updated before each stage so the except block can report
    # the exact stage that failed.
    error_stage = "initialization"
    try:
        # ----- lazy imports keep these modules out of the hot path -----
        from ingredient_normalizer_v2 import normalize_ingredient_v2
        from services.adjustment_metadata_service import build_adjustments_for_candidates
        from services.role_inference_service import (
            build_recipe_context_from_recipe,
            infer_role_for_ingredient,
        )
        from services.substitute_generation_service import generate_substitute_candidates
        from services.substitute_ranking_service import rank_substitute_candidates
        from services.step_rewrite_service import rewrite_recipe_steps
        from utils.step_text import normalize_original_steps

        original_steps = normalize_original_steps(recipe.get("directions", []))

        error_stage = "recipe_context"
        recipe_context = build_recipe_context_from_recipe(recipe)

        # Merge main and seasoning substitutions into one map {source: target}.
        all_subs: Dict[str, str] = {
            **payload.selected_main_subs,
            **payload.selected_seasoning_subs,
        }

        selected_candidates: List[Dict[str, str]] = []
        all_ranked_debug: List[Dict[str, Any]] = []
        all_step6_bundles: List[Dict[str, Any]] = []

        for source, target in all_subs.items():
            # -- Stage 1+3: normalise source, infer role ----------------
            error_stage = f"role_inference[{source}]"
            norm = normalize_ingredient_v2(source)
            source_dict = norm.to_dict()  # includes raw, canonical, base, descriptors, …

            role_result = infer_role_for_ingredient(source_dict, recipe_context)
            source_dict["inferred_role"] = _safe_str(role_result.get("inferred_role"))
            source_dict["role_confidence"] = float(role_result.get("confidence") or 0.0)

            # -- Stage 4: generate candidates ---------------------------
            error_stage = f"substitute_generation[{source}]"
            step4 = generate_substitute_candidates(
                source_dict,
                recipe_context,
                user_inventory=list(payload.user_ingredients),
                inventory_only=False,
            )

            # -- Stage 5: rank candidates --------------------------------
            error_stage = f"substitute_ranking[{source}]"
            step5 = rank_substitute_candidates(step4, recipe_context=recipe_context)

            # -- Stage 6: adjustment metadata ----------------------------
            error_stage = f"adjustment_metadata[{source}]"
            step6 = build_adjustments_for_candidates(step5, recipe_context=recipe_context)

            selected_candidates.append({"source_canonical": source, "candidate": target})
            all_ranked_debug.append(
                {
                    "source": source,
                    "selected_target": target,
                    "inferred_role": source_dict["inferred_role"],
                    "role_confidence": source_dict["role_confidence"],
                    # Only include the top few candidates to keep payload manageable.
                    "top_candidates": step5.get("ranked_candidates", [])[:_MAX_RANKED_SHOWN],
                }
            )
            all_step6_bundles.append(step6)

        # -- Stage 6 (post): extract adjustments for selected candidates -
        adjustment_metadata_v2 = _extract_selected_adjustments(all_step6_bundles, all_subs)

        # -- Stage 7: step rewrite preview -------------------------------
        error_stage = "step_rewrite"
        step7 = rewrite_recipe_steps(
            original_steps=original_steps,
            selected_substitutions=selected_candidates,
            adjustment_metadata_list=all_step6_bundles,
        )

        return {
            "debug_v2_enabled": True,
            "shadow_pipeline_version": _SHADOW_PIPELINE_VERSION,
            "rewrite_debug_v2": {
                "selected_candidates": selected_candidates,
                "ranked_substitute_candidates_v2": all_ranked_debug,
                "adjustment_metadata_v2": adjustment_metadata_v2,
                "step_rewrite_preview": step7,
            },
        }

    except Exception as exc:  # noqa: BLE001
        # Return a safe error shape; do not expose a raw traceback.
        return {
            "debug_v2_enabled": True,
            "shadow_pipeline_version": _SHADOW_PIPELINE_VERSION,
            "rewrite_debug_v2": {
                "error": "Shadow pipeline preview generation failed.",
                "error_stage": error_stage,
                "error_detail": _safe_str(exc),
            },
        }


def _extract_selected_adjustments(
    all_step6_bundles: List[Dict[str, Any]],
    all_subs: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Return the adjustment entry that matches each user-selected candidate.

    If the selected target is not in the ranked list (e.g. user chose an
    off-pool ingredient), return an explicit no-preview placeholder instead of
    a misleading top-ranked adjustment for a different candidate.
    """
    out: List[Dict[str, Any]] = []
    selected_lookup = _normalized_substitution_lookup(all_subs)
    for bundle in all_step6_bundles:
        source_key = _safe_str(
            bundle.get("source", {}).get("canonical")
            or bundle.get("source", {}).get("base")
        ).lower()
        selected_target = _safe_str(selected_lookup.get(source_key)).lower()

        matched: Dict[str, Any] | None = None
        for adj in bundle.get("adjustments", []):
            cand = _safe_str(
                adj.get("candidate")
                or adj.get("candidate_canonical")
                or adj.get("candidate_base")
            ).lower()
            if selected_target and cand == selected_target:
                matched = adj
                break

        if matched is not None:
            out.append(matched)
        else:
            out.append(
                {
                    "source_canonical": _safe_str(bundle.get("source", {}).get("canonical")),
                    "source_base": _safe_str(bundle.get("source", {}).get("base")),
                    "candidate": _safe_str(selected_target),
                    "matched_selected_candidate": False,
                    "preview_available": False,
                    "fallback_reason": (
                        "Selected candidate was not found in ranked adjustment metadata; "
                        "no Step 6 adjustment preview is available for this source."
                    ),
                }
            )

    return out
