"""Step rewrite service (Step 7, shadow mode).

This service performs conservative, local edits to existing recipe steps using
Step 6 adjustment metadata as the control layer. It does not replace the
current remix flow and does not generate a recipe from scratch.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple


REWRITE_MODE_INGREDIENT_ONLY = "ingredient_name_only"
REWRITE_MODE_PLUS_METHOD = "ingredient_plus_method_note"
REWRITE_MODE_CAUTION = "caution_no_rewrite"

_ALLOWED_POLICIES = {"allowed", "allowed_with_adjustment"}
_CAUTION_POLICIES = {"caution"}
_BLOCKED_POLICIES = {"weak_option", "reject"}

_ROLE_CUES = {
    "thickener": {"whisk", "simmer", "thicken", "slurry", "boil"},
    "aerated_base": {"whip", "fold", "peaks", "beat", "aerate"},
    "sweetener": {"sweet", "dissolve", "syrup", "caramel", "stir"},
    "topping": {"top", "sprinkle", "garnish", "finish", "plate"},
    "structure": {"mix", "knead", "dough", "batter", "rise", "bake"},
    "acidity_provider": {"acid", "bright", "taste", "balance", "finish"},
}

_RISK_WARNING_MAP = {
    "flavor_shift": "This substitute may change the flavor noticeably.",
    "texture_shift": "Monitor texture closely because this substitute may behave differently.",
    "moisture_shift": "This substitute may change moisture balance; adjust liquids gradually.",
    "thickening_risk": "The mixture may thicken faster or slower than expected.",
    "whipping_risk": "Monitor texture during whipping because stability may differ.",
    "structure_risk": "This substitute may not provide the same structure as the original ingredient.",
    "over_sweetening_risk": "This substitute may be sweeter than expected; adjust to taste.",
    "acidity_balance_risk": "Acidity balance may shift; taste and adjust gradually.",
    "weak_substitute": "This substitute is a weak option for the target role.",
    "rejected_candidate": "This candidate is not recommended for reliable rewrite.",
}


def _norm(text: Any) -> str:
    return str(text or "").strip().lower()


def _clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _safe_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _word_boundary_replace(text: str, needle: str, replacement: str) -> Tuple[str, bool]:
    if not needle:
        return text, False

    pattern = re.compile(rf"\b{re.escape(needle)}\b", re.IGNORECASE)

    def _repl(match: re.Match[str]) -> str:
        matched = match.group(0)
        if matched[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    updated, count = pattern.subn(_repl, text)
    return updated, count > 0


def _contains_word(text: str, needle: str) -> bool:
    if not needle:
        return False
    return re.search(rf"\b{re.escape(needle)}\b", text, re.IGNORECASE) is not None


def _collect_adjustments(adjustment_metadata_list: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in _safe_list(adjustment_metadata_list):
        if isinstance(item, dict) and isinstance(item.get("adjustments"), list):
            for adj in item["adjustments"]:
                if isinstance(adj, dict):
                    rows.append(adj)
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _selected_pairs(selected_substitutions: Any) -> set[Tuple[str, str]]:
    pairs: set[Tuple[str, str]] = set()
    for item in _safe_list(selected_substitutions):
        if not isinstance(item, dict):
            continue
        source = _norm(item.get("source") or item.get("source_canonical") or item.get("source_base"))
        candidate = _norm(item.get("candidate") or item.get("candidate_canonical") or item.get("candidate_base"))
        if source and candidate:
            pairs.add((source, candidate))
    return pairs


def _is_adjustment_sparse(adjustment_metadata: Dict[str, Any]) -> bool:
    amount_note = _norm(adjustment_metadata.get("amount_adjustment", {}).get("note"))
    method_note = _norm(adjustment_metadata.get("method_adjustment", {}).get("note"))
    prep_note = _norm(adjustment_metadata.get("preprocessing", {}).get("note"))
    timing_note = _norm(adjustment_metadata.get("timing_adjustment", {}).get("note"))
    expected = adjustment_metadata.get("expected_changes") or {}

    expected_text = " ".join(_norm(expected.get(k)) for k in ["flavor", "texture", "moisture"])
    composite = _clean_spaces(" ".join([amount_note, method_note, prep_note, timing_note, expected_text]))
    return not composite


def _warnings_from_adjustment(adjustment_metadata: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    for flag in adjustment_metadata.get("risk_flags", []) or []:
        msg = _RISK_WARNING_MAP.get(_norm(flag))
        if msg:
            warnings.append(msg)

    expected = adjustment_metadata.get("expected_changes") or {}
    for key in ["flavor", "texture", "moisture"]:
        text = _clean_spaces(str(expected.get(key, "")))
        if text and "minimal" not in text.lower():
            warnings.append(text)

    # Preserve order while de-duplicating.
    deduped: List[str] = []
    seen = set()
    for msg in warnings:
        if msg not in seen:
            seen.add(msg)
            deduped.append(msg)
    return deduped


def should_allow_rewrite(adjustment_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Strict gate for Step 7 rewriting.

    Returns a structured decision:
    {
      "allow": bool,
      "mode": str,
      "reason": str,
    }
    """
    policy = _norm(adjustment_metadata.get("suitability_policy"))
    quality_band = _norm(adjustment_metadata.get("quality_band"))
    confidence = float(adjustment_metadata.get("confidence", 0.0) or 0.0)

    if policy in _BLOCKED_POLICIES or quality_band in {"weak_option", "reject"}:
        return {
            "allow": False,
            "mode": REWRITE_MODE_CAUTION,
            "reason": f"Rewrite blocked by quality gate ({quality_band or policy}).",
        }

    if "rejected_candidate" in {_norm(x) for x in adjustment_metadata.get("risk_flags", []) or []}:
        return {
            "allow": False,
            "mode": REWRITE_MODE_CAUTION,
            "reason": "Rewrite blocked due to rejected candidate risk flag.",
        }

    if confidence < 0.55:
        return {
            "allow": False,
            "mode": REWRITE_MODE_CAUTION,
            "reason": f"Rewrite confidence too low ({confidence:.2f}).",
        }

    if _is_adjustment_sparse(adjustment_metadata):
        return {
            "allow": False,
            "mode": REWRITE_MODE_CAUTION,
            "reason": "Adjustment metadata is too sparse for safe rewriting.",
        }

    method_needed = bool(adjustment_metadata.get("method_adjustment", {}).get("needed", False))
    prep_needed = bool(adjustment_metadata.get("preprocessing", {}).get("needed", False))
    timing_needed = bool(adjustment_metadata.get("timing_adjustment", {}).get("needed", False))

    if policy in _CAUTION_POLICIES:
        # Caution policy allows only local/minimal edits.
        if (method_needed or prep_needed or timing_needed) and confidence >= 0.68:
            return {
                "allow": True,
                "mode": REWRITE_MODE_PLUS_METHOD,
                "reason": "Caution policy: local method note only.",
            }
        return {
            "allow": True,
            "mode": REWRITE_MODE_INGREDIENT_ONLY,
            "reason": "Caution policy: ingredient rename only.",
        }

    if policy in _ALLOWED_POLICIES:
        if method_needed or prep_needed or timing_needed:
            return {
                "allow": True,
                "mode": REWRITE_MODE_PLUS_METHOD,
                "reason": "Allowed policy with adjustment metadata.",
            }
        return {
            "allow": True,
            "mode": REWRITE_MODE_INGREDIENT_ONLY,
            "reason": "Allowed policy with minimal replacement.",
        }

    # Unknown policy is treated conservatively.
    return {
        "allow": False,
        "mode": REWRITE_MODE_CAUTION,
        "reason": f"Unknown suitability policy '{policy}' blocked rewrite.",
    }


def find_relevant_steps(
    original_steps: Sequence[str],
    source_ingredients: Sequence[str],
    substitute_candidates: Sequence[str],
    role: str = "",
) -> List[int]:
    """Detect likely relevant step indices conservatively.

    A step is considered relevant only when textual evidence is strong.
    """
    source_terms = [_norm(s) for s in source_ingredients if _norm(s)]
    candidate_terms = [_norm(s) for s in substitute_candidates if _norm(s)]
    cues = _ROLE_CUES.get(_norm(role), set())

    indices: List[int] = []
    for idx, raw_step in enumerate(original_steps):
        step = _norm(raw_step)
        score = 0

        for term in source_terms:
            if _contains_word(step, term):
                score += 3

        for term in candidate_terms:
            if _contains_word(step, term):
                score += 2

        for cue in cues:
            if cue in step:
                score += 1

        if score >= 3:
            indices.append(idx)

    # Fallback: if no confident match, try source terms only.
    if not indices:
        for idx, raw_step in enumerate(original_steps):
            step = _norm(raw_step)
            if any(_contains_word(step, term) for term in source_terms):
                indices.append(idx)

    return sorted(set(indices))


def _build_method_note(adjustment_metadata: Dict[str, Any]) -> str:
    chunks: List[str] = []

    prep = adjustment_metadata.get("preprocessing") or {}
    method = adjustment_metadata.get("method_adjustment") or {}
    timing = adjustment_metadata.get("timing_adjustment") or {}
    amount = adjustment_metadata.get("amount_adjustment") or {}

    if prep.get("needed"):
        chunks.append(_clean_spaces(str(prep.get("note", ""))))
    if method.get("needed"):
        chunks.append(_clean_spaces(str(method.get("note", ""))))
    if timing.get("needed"):
        chunks.append(_clean_spaces(str(timing.get("note", ""))))

    amount_type = _norm(amount.get("type"))
    if amount_type == "start_with_less":
        chunks.append("Start with a smaller amount and increase gradually.")
    elif amount_type == "may_need_more":
        chunks.append("You may need slightly more than the original amount.")

    chunks = [c for c in chunks if c]
    if not chunks:
        return ""

    # Keep local edits short: include at most two short notes.
    selected = chunks[:2]
    return " ".join(selected)


def apply_local_adjustment_to_step(
    step_text: str,
    adjustment_metadata: Dict[str, Any],
    recipe_context: Optional[Any] = None,
    rewrite_mode: str = REWRITE_MODE_INGREDIENT_ONLY,
) -> Dict[str, Any]:
    """Apply a minimal local edit to one step.

    Returns:
    {
      "updated_step": str,
      "changed": bool,
      "applied_fields": [ ... ],
    }
    """
    updated = step_text
    changed = False
    applied_fields: List[str] = []

    source_canonical = _clean_spaces(str(adjustment_metadata.get("source_canonical", "")))
    source_base = _clean_spaces(str(adjustment_metadata.get("source_base", "")))
    candidate = _clean_spaces(
        str(
            adjustment_metadata.get("candidate")
            or adjustment_metadata.get("candidate_canonical")
            or adjustment_metadata.get("candidate_base")
            or ""
        )
    )

    if candidate:
        for source_term in [source_canonical, source_base]:
            updated2, replaced = _word_boundary_replace(updated, source_term, candidate)
            if replaced:
                updated = updated2
                changed = True
                if "ingredient_name" not in applied_fields:
                    applied_fields.append("ingredient_name")
                # Stop after first match: prevents double-replacement when
                # source_canonical and source_base share a common token (e.g.
                # canonical="cream", base="cream") and the candidate text
                # already contains that token (e.g. "sour cream").
                break

    if rewrite_mode == REWRITE_MODE_PLUS_METHOD:
        note = _build_method_note(adjustment_metadata)
        if note:
            existing = _norm(updated)
            # Add a short local sentence only if the same guidance is not already present.
            if _norm(note[:30]) not in existing:
                separator = " " if updated.endswith((".", "!", "?")) else ". "
                updated = f"{_clean_spaces(updated)}{separator}{note}"
                changed = True

                if bool(adjustment_metadata.get("preprocessing", {}).get("needed")):
                    applied_fields.append("preprocessing")
                if bool(adjustment_metadata.get("method_adjustment", {}).get("needed")):
                    applied_fields.append("method_adjustment")
                if bool(adjustment_metadata.get("timing_adjustment", {}).get("needed")):
                    applied_fields.append("timing_adjustment")
                if _norm(adjustment_metadata.get("amount_adjustment", {}).get("type")) in {
                    "start_with_less",
                    "may_need_more",
                }:
                    applied_fields.append("amount_adjustment")

    return {
        "updated_step": _clean_spaces(updated),
        "changed": changed,
        "applied_fields": sorted(set(applied_fields)),
    }


def rewrite_step(
    step_text: str,
    relevant_adjustments: Sequence[Dict[str, Any]],
    recipe_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Rewrite one step with one or more relevant adjustments.

    Edits remain local and conservative by honoring per-adjustment gates.
    """
    current = step_text
    applied_fields: List[str] = []
    local_warnings: List[str] = []

    for adjustment in relevant_adjustments:
        decision = should_allow_rewrite(adjustment)
        local_warnings.extend(_warnings_from_adjustment(adjustment)[:2])

        if not decision["allow"]:
            continue

        patch = apply_local_adjustment_to_step(
            current,
            adjustment,
            recipe_context=recipe_context,
            rewrite_mode=decision["mode"],
        )

        if patch["changed"]:
            current = patch["updated_step"]
            applied_fields.extend(patch["applied_fields"])

    deduped_warnings: List[str] = []
    seen = set()
    for item in local_warnings:
        if item not in seen:
            seen.add(item)
            deduped_warnings.append(item)

    return {
        "rewritten_step": current,
        "changed": _clean_spaces(current) != _clean_spaces(step_text),
        "applied_fields": sorted(set(applied_fields)),
        "warnings": deduped_warnings,
    }


def rewrite_recipe_steps(
    original_steps: Sequence[str],
    selected_substitutions: Any,
    adjustment_metadata_list: Any,
    recipe_context: Optional[Any] = None,
) -> Dict[str, Any]:
    """Rewrite recipe steps conservatively using Step 6 adjustment metadata.

    Hard safety guarantees:
    - Preserve step count and order.
    - Only modify relevant steps.
    - Block or limit weak/reject candidates.
    - Fallback to original steps when confidence/signal is low.
    """
    steps = [str(s) for s in (original_steps or [])]
    rewritten = list(steps)

    selected_pairs = _selected_pairs(selected_substitutions)
    all_adjustments = _collect_adjustments(adjustment_metadata_list)

    # Filter to selected substitutions when provided.
    adjustments: List[Dict[str, Any]] = []
    for adj in all_adjustments:
        src_key = _norm(adj.get("source_canonical") or adj.get("source_base"))
        cand_key = _norm(adj.get("candidate") or adj.get("candidate_canonical") or adj.get("candidate_base"))

        if selected_pairs:
            if (src_key, cand_key) in selected_pairs:
                adjustments.append(adj)
        else:
            adjustments.append(adj)

    rewrite_warnings: List[str] = []
    applied_adjustments: List[Dict[str, Any]] = []
    changed_step_indices: List[int] = []
    fallback_reasons: List[str] = []
    applied_modes: List[str] = []

    if not adjustments:
        return {
            "original_steps": steps,
            "rewritten_steps": rewritten,
            "changed_step_indices": [],
            "applied_adjustments": [],
            "rewrite_warnings": ["No matching adjustment metadata was provided for selected substitutions."],
            "fallback_reason": "No adjustment metadata matched selected substitutions.",
            "rewrite_mode": REWRITE_MODE_CAUTION,
        }

    for adj in adjustments:
        decision = should_allow_rewrite(adj)
        applied_modes.append(decision["mode"])
        rewrite_warnings.extend(_warnings_from_adjustment(adj)[:3])

        source_terms = [
            str(adj.get("source_canonical") or ""),
            str(adj.get("source_base") or ""),
        ]
        candidate_terms = [
            str(adj.get("candidate") or ""),
            str(adj.get("candidate_canonical") or ""),
            str(adj.get("candidate_base") or ""),
        ]
        role = str(adj.get("inferred_role") or "")

        relevant = find_relevant_steps(steps, source_terms, candidate_terms, role=role)
        if not relevant:
            fallback_reasons.append(
                f"No confidently relevant step found for source '{adj.get('source_canonical') or adj.get('source_base')}'."
            )
            continue

        if not decision["allow"]:
            fallback_reasons.append(decision["reason"])
            continue

        for idx in relevant:
            out = apply_local_adjustment_to_step(
                rewritten[idx],
                adj,
                recipe_context=recipe_context,
                rewrite_mode=decision["mode"],
            )
            if not out["changed"]:
                continue

            rewritten[idx] = out["updated_step"]
            if idx not in changed_step_indices:
                changed_step_indices.append(idx)

            applied_adjustments.append(
                {
                    "step_index": idx,
                    "source": str(adj.get("source_canonical") or adj.get("source_base") or ""),
                    "candidate": str(adj.get("candidate") or adj.get("candidate_canonical") or ""),
                    "applied_fields": out["applied_fields"],
                }
            )

    changed_step_indices = sorted(changed_step_indices)

    # Invariant: rewritten is always the same length as steps because we only
    # perform index-based in-place assignments.  Raise a hard error here so
    # callers catch any future regression rather than silently returning a
    # malformed result.
    if len(rewritten) != len(steps):
        raise ValueError(
            f"Step rewrite invariant violated: rewritten length {len(rewritten)} "
            f"!= original length {len(steps)}"
        )

    overall_mode = REWRITE_MODE_CAUTION
    if changed_step_indices:
        if REWRITE_MODE_PLUS_METHOD in applied_modes:
            overall_mode = REWRITE_MODE_PLUS_METHOD
        elif REWRITE_MODE_INGREDIENT_ONLY in applied_modes:
            overall_mode = REWRITE_MODE_INGREDIENT_ONLY

    if not changed_step_indices:
        reason = " ".join(dict.fromkeys(fallback_reasons)) if fallback_reasons else "Rewrite not applied due to conservative gating."
        return {
            "original_steps": steps,
            "rewritten_steps": steps,
            "changed_step_indices": [],
            "applied_adjustments": [],
            "rewrite_warnings": sorted(set(rewrite_warnings))[:8],
            "fallback_reason": reason,
            "rewrite_mode": REWRITE_MODE_CAUTION,
        }

    return {
        "original_steps": steps,
        "rewritten_steps": rewritten,
        "changed_step_indices": changed_step_indices,
        "applied_adjustments": applied_adjustments,
        "rewrite_warnings": sorted(set(rewrite_warnings))[:8],
        "fallback_reason": "",
        "rewrite_mode": overall_mode,
    }
