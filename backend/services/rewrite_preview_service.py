"""Rewrite preview analysis service (read-only shadow pipeline analysis).

Provides structured analysis of the shadow pipeline without breaking or
modifying any production remix behavior.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_rewrite_preview_analysis(
    payload: Any,
    recipe: Dict[str, Any],
) -> Dict[str, Any]:
    """Run shadow pipeline and return structured analysis response.

    This function performs read-only analysis of the shadow pipeline.
    It does not modify any production state and can be safely called in parallel.

    Returns a structured analysis dict with detailed sections for each pipeline
    stage, or a safe error dict if the pipeline fails.
    """
    error_stage = "initialization"
    try:
        # --------- lazy imports for read-only analysis -----
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

        # Build recipe context
        error_stage = "recipe_context"
        recipe_context = build_recipe_context_from_recipe(recipe)
        original_steps = normalize_original_steps(recipe.get("directions", []))

        # Prepare substitutions (selected or empty if not provided)
        selected_subs = {
            **(payload.selected_main_subs or {}),
            **(payload.selected_seasoning_subs or {}),
        }

        # Analysis structures
        ingredients_analysis: List[Dict[str, Any]] = []
        candidate_generation_details: List[Dict[str, Any]] = []
        ranked_candidates_summary: List[Dict[str, Any]] = []
        selected_candidates_list: List[Dict[str, str]] = []
        adjustment_metadata_output: List[Dict[str, Any]] = []

        quality_band_counts: Dict[str, int] = {}
        confidence_values: List[float] = []

        # Analyze each selected substitution
        for source, target in selected_subs.items():
            error_stage = f"role_inference[{source}]"

            # Step 1+3: Normalize and infer role
            norm = normalize_ingredient_v2(source)
            source_dict = norm.to_dict()
            role_result = infer_role_for_ingredient(source_dict, recipe_context)

            source_dict["inferred_role"] = str(role_result.get("inferred_role") or "")
            source_dict["role_confidence"] = float(role_result.get("confidence") or 0.0)

            ingredients_analysis.append(
                {
                    "source": source,
                    "source_normalized": source_dict,
                    "inferred_role": source_dict["inferred_role"],
                    "role_confidence": source_dict["role_confidence"],
                    "role_evidence": role_result.get("evidence", [])[:5],
                }
            )

            # Step 4: Generate candidates
            error_stage = f"substitute_generation[{source}]"
            step4 = generate_substitute_candidates(
                source_dict,
                recipe_context,
                user_inventory=list(payload.user_ingredients or []),
                inventory_only=False,
            )

            candidate_generation_details.append(
                {
                    "source": source,
                    "inferred_role": source_dict["inferred_role"],
                    "candidates_generated": len(step4.get("candidates", [])),
                    "candidates_sample": step4.get("candidates", [])[:3],
                }
            )

            # Step 5: Rank candidates
            error_stage = f"substitute_ranking[{source}]"
            step5 = rank_substitute_candidates(step4, recipe_context=recipe_context)

            ranked = step5.get("ranked_candidates", [])
            ranked_candidates_summary.append(
                {
                    "source": source,
                    "total_ranked": len(ranked),
                    "top_3_ranked": ranked[:3],
                }
            )

            selected_candidates_list.append(
                {
                    "source": source,
                    "selected_target": target,
                }
            )

            # Step 6: Build adjustments for selected candidate
            error_stage = f"adjustment_metadata[{source}]"
            step6 = build_adjustments_for_candidates(step5, recipe_context=recipe_context)

            # Find the selected target in adjustments
            matched_adj = None
            for adj in step6.get("adjustments", []):
                cand = str(
                    adj.get("candidate")
                    or adj.get("candidate_canonical")
                    or adj.get("candidate_base")
                    or ""
                ).lower()
                if cand == target.lower():
                    matched_adj = adj
                    break

            if matched_adj:
                adjustment_metadata_output.append(matched_adj)
                qb = str(matched_adj.get("quality_band") or "").lower()
                quality_band_counts[qb] = quality_band_counts.get(qb, 0) + 1
                conf = float(matched_adj.get("confidence") or 0.0)
                confidence_values.append(conf)
            else:
                # Selected candidate not found in ranked list
                adjustment_metadata_output.append(
                    {
                        "source": source,
                        "candidate": target,
                        "matched": False,
                        "note": "Selected candidate not found in ranked results; no Step 6 adjustment available.",
                    }
                )

        # Step 7: Step rewrite preview
        error_stage = "step_rewrite"
        step7 = rewrite_recipe_steps(
            original_steps=original_steps,
            selected_substitutions=selected_candidates_list,
            adjustment_metadata_list=[
                {
                    "source": {"canonical": src, "base": src},
                    "adjustments": [adj],
                }
                for src, adj in zip(selected_subs.keys(), adjustment_metadata_output)
                if "matched" not in adj or adj.get("matched") is not False
            ],
        )

        # Compute quality summary
        avg_confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else 0.0
        )

        return {
            "recipe_id": payload.recipe_id,
            "shadow_pipeline_version": "v2",
            "ingredients_analysis": ingredients_analysis,
            "candidate_generation": candidate_generation_details,
            "ranked_candidates": ranked_candidates_summary,
            "selected_candidates": selected_candidates_list,
            "adjustment_metadata": adjustment_metadata_output,
            "step_rewrite_preview": step7,
            "quality_summary": {
                "quality_band_counts": quality_band_counts,
                "confidence_stats": {
                    "average": round(avg_confidence, 3),
                    "count": len(confidence_values),
                    "min": round(min(confidence_values), 3) if confidence_values else None,
                    "max": round(max(confidence_values), 3) if confidence_values else None,
                },
                "total_substitutions_analyzed": len(selected_subs),
            },
        }

    except Exception as exc:  # noqa: BLE001
        return {
            "recipe_id": getattr(payload, "recipe_id", ""),
            "shadow_pipeline_version": "v2",
            "error": "Shadow pipeline analysis failed",
            "error_stage": error_stage,
            "error_detail": str(exc or "Unknown error"),
        }
