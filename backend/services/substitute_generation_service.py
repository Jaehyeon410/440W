"""Candidate-first substitute generation service (refactored).

Retrieval is now candidate-first, importance-aware.  Three candidate sources:
1. direct_substitutes from metadata
2. Inventory items with compatible metadata (category/parent/function match)
3. Pool candidates from ALL matching function pools (not just one role)

Role inference is NOT called here.  The old role-first cascade is removed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ingredient_normalizer_v2 import normalize_ingredient_v2, normalize_ingredient_list_v2
from services.ingredient_metadata_service import get_metadata
from services.role_inference_service import RecipeContext, FUNCTION_TO_ROLE


POOLS_FILE = Path(__file__).resolve().parents[1] / "substitute_pools.json"

# Block category-incompatible substitutes early so obviously invalid options
# do not reach ranking.  E.g. vegetable -> protein (arugula -> shrimp) is always wrong.
# Categories come from ingredient_metadata.json: vegetable, protein, starch,
# dairy, fat, fruit, seasoning, aromatic, condiment, liquid, sweetener,
# binder, sauce_component, unknown.
CATEGORY_COMPATIBILITY: Dict[str, Set[str]] = {
    "vegetable":       {"vegetable", "aromatic"},
    "protein":         {"protein"},
    "starch":          {"starch", "binder"},
    "dairy":           {"dairy", "fat"},            # butter <-> cream
    "fat":             {"fat", "dairy"},            # oil <-> butter
    "fruit":           {"fruit", "sweetener"},
    "seasoning":       {"seasoning", "aromatic", "condiment"},
    "aromatic":        {"aromatic", "seasoning", "vegetable"},
    "garnish":         {"garnish", "vegetable", "aromatic", "seasoning"},
    "condiment":       {"condiment", "seasoning", "aromatic"},
    "liquid":          {"liquid", "condiment"},
    "sweetener":       {"sweetener", "liquid", "fruit"},
    "binder":          {"binder", "starch", "dairy"},
    "sauce_component": {"sauce_component", "condiment", "liquid"},
}


def _is_fat_dairy_compatible(source_meta: Dict[str, Any], candidate_meta: Dict[str, Any]) -> bool:
    """When source is fat (oil) and candidate is dairy, only allow fat-like dairy.

    Blocks cheese as a substitute for oil/lard while keeping butter/cream.
    """
    src_cat = _norm(str(source_meta.get("category") or ""))
    cand_cat = _norm(str(candidate_meta.get("category") or ""))
    if src_cat != "fat" or cand_cat != "dairy":
        return True  # rule doesn't apply
    # Dairy items whose primary role is fat are OK (e.g. butter)
    if _norm(str(candidate_meta.get("primary_function") or "")) == "fat_source":
        return True
    # Liquid / creamy dairy is compatible with fat/oil uses (e.g. cream)
    cand_texture = _norm(str(candidate_meta.get("texture") or ""))
    if cand_texture in ("liquid", "creamy"):
        return True
    return False


# Functions too generic to serve as meaningful overlap signals when filtering
# within the seasoning / aromatic / condiment cluster.
_GENERIC_SEASONING_FUNCTIONS = frozenset({"seasoning", "savory_component"})


def _is_specific_function_compatible(
    source_meta: Dict[str, Any],
    candidate_meta: Dict[str, Any],
    retrieval_source: str,
) -> bool:
    """Light filter for two narrow situations.

    1. Acid-source specificity: if the source's primary function is acid_source,
       require the candidate to also have acid_source.
    2. Seasoning-cluster salt guard: within the seasoning/aromatic/condiment
       cluster, block powder candidates whose functions are *only* generic
       (e.g. plain salt) when the source is non-powder (herb-like).

    Direct substitutes are never blocked.
    """
    if retrieval_source == "direct_substitute":
        return True

    src_primary = _norm(str(source_meta.get("primary_function") or ""))

    # Sub-rule 1 — acid-source specificity
    if src_primary == "acid_source":
        cand_fns = {_norm(str(f)) for f in candidate_meta.get("possible_functions", [])}
        if "acid_source" not in cand_fns:
            return False

    # Sub-rule 2 — block plain-salt-like candidates for herb-like sources
    src_cat = _norm(str(source_meta.get("category") or ""))
    cand_cat = _norm(str(candidate_meta.get("category") or ""))
    if (src_cat in ("seasoning", "aromatic", "condiment")
            and cand_cat in ("seasoning", "aromatic", "condiment")):
        src_texture = _norm(str(source_meta.get("texture") or ""))
        if src_texture != "powder":  # source is herb-like (solid / soft)
            cand_texture = _norm(str(candidate_meta.get("texture") or ""))
            cand_fns = {_norm(str(f)) for f in candidate_meta.get("possible_functions", [])}
            if (cand_texture == "powder"
                    and cand_fns
                    and cand_fns.issubset(_GENERIC_SEASONING_FUNCTIONS)):
                return False

    return True


def is_category_compatible(source_meta: Dict[str, Any], candidate_meta: Dict[str, Any]) -> bool:
    """Return False when source and candidate categories are clearly incompatible.

    Conservative: returns True when either category is missing so that sparse
    metadata does not cause over-blocking.
    """
    src_cat = (str(source_meta.get("category") or "")).strip().lower()
    cand_cat = (str(candidate_meta.get("category") or "")).strip().lower()
    if not src_cat or not cand_cat:
        return True
    allowed = CATEGORY_COMPATIBILITY.get(src_cat)
    if allowed is None:
        # Unknown category: only allow same-category candidates
        return src_cat == cand_cat
    return cand_cat in allowed


# After category filtering, cap the number of candidates sent to ranking.
# direct_substitutes and inventory matches are always kept; the cap mainly
# trims noisy pool candidates.
MAX_PREFILTER_CANDIDATES = 25


def _has_prefilter_similarity(source_meta: Dict[str, Any], candidate_meta: Dict[str, Any]) -> bool:
    """Return True if the candidate shares at least one concrete metadata signal with the source.

    This is a lightweight gate — NOT a scoring model.  It exists only to drop
    pool candidates that survived category matching but have no real similarity.
    """
    # Same parent (e.g. both "leafy green")
    src_parent = (str(source_meta.get("parent") or "")).strip().lower()
    cand_parent = (str(candidate_meta.get("parent") or "")).strip().lower()
    if src_parent and cand_parent and src_parent == cand_parent:
        return True

    # Overlapping possible_functions
    src_fns = {str(f).strip().lower() for f in source_meta.get("possible_functions", [])}
    cand_fns = {str(f).strip().lower() for f in candidate_meta.get("possible_functions", [])}
    if src_fns and cand_fns and src_fns & cand_fns:
        return True

    # Same texture
    src_tex = (str(source_meta.get("texture") or "")).strip().lower()
    cand_tex = (str(candidate_meta.get("texture") or "")).strip().lower()
    if src_tex and cand_tex and src_tex == cand_tex:
        return True

    return False


def _prefilter_priority(retrieval_source: str, available: bool,
                        source_meta: Dict[str, Any],
                        candidate_meta: Dict[str, Any]) -> Tuple[int, ...]:
    """Return a sort key (lower = higher priority) for deterministic cap trimming."""
    # 0 = direct_substitute, 1 = inventory, 2 = parent match,
    # 3 = function overlap, 4 = texture match, 5 = everything else
    if retrieval_source == "direct_substitute":
        return (0,)
    if available:
        return (1,)

    src_parent = (str(source_meta.get("parent") or "")).strip().lower()
    cand_parent = (str(candidate_meta.get("parent") or "")).strip().lower()
    if src_parent and cand_parent and src_parent == cand_parent:
        return (2,)

    src_fns = {str(f).strip().lower() for f in source_meta.get("possible_functions", [])}
    cand_fns = {str(f).strip().lower() for f in candidate_meta.get("possible_functions", [])}
    if src_fns and cand_fns and src_fns & cand_fns:
        return (3,)

    src_tex = (str(source_meta.get("texture") or "")).strip().lower()
    cand_tex = (str(candidate_meta.get("texture") or "")).strip().lower()
    if src_tex and cand_tex and src_tex == cand_tex:
        return (4,)

    return (5,)


ROLE_FUNCTION_ALIASES: Dict[str, str] = {
    "acidity_provider": "acid_source",
    "flavor_booster": "seasoning",
    "richness": "fat_source",
    "moisture_provider": "liquid_base",
    "main_component": "main_protein",
    "protein_base": "main_protein",
}


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
        for key in [item.get("canonical"), item.get("normalized_text")]:
            value = _norm(str(key or ""))
            if value:
                keys.add(value)
        base = _norm(str(item.get("base") or ""))
        canonical = _norm(str(item.get("canonical") or ""))
        if base and base == canonical:
            keys.add(base)
    return keys


def _metadata_for_normalized(normalized: Dict[str, Any], *, allow_generation: bool = False) -> Dict[str, Any]:
    canonical = _norm(str(normalized.get("canonical") or ""))
    base = _norm(str(normalized.get("base") or ""))
    meta = get_metadata(canonical, allow_generation=allow_generation) if canonical else {}
    if meta.get("possible_functions"):
        return meta
    if base:
        return get_metadata(base, allow_generation=allow_generation)
    return get_metadata(canonical, allow_generation=allow_generation)


def _candidate_available(candidate_norm: Dict[str, Any], inventory_keys: Set[str]) -> bool:
    if not inventory_keys:
        return False
    canonical = _norm(str(candidate_norm.get("canonical") or ""))
    normalized_text = _norm(str(candidate_norm.get("normalized_text") or ""))
    base = _norm(str(candidate_norm.get("base") or ""))
    if canonical and canonical in inventory_keys:
        return True
    if normalized_text and normalized_text in inventory_keys:
        return True
    if base and base == canonical and base in inventory_keys:
        return True
    return False


# ---------------------------------------------------------------------------
# Candidate retrieval: candidate-first, no single-role dependency
# ---------------------------------------------------------------------------

def _collect_pool_candidates(source_meta: Dict[str, Any]) -> List[str]:
    """Gather candidates from ALL pools matching the source's possible_functions."""
    pools = load_substitute_pools()
    seen: Set[str] = set()
    result: List[str] = []

    source_functions = {_norm(str(f)) for f in source_meta.get("possible_functions", [])}
    # Map functions to roles, then collect from all matching pools
    roles_to_check: Set[str] = set()
    for fn in source_functions:
        mapped_role = FUNCTION_TO_ROLE.get(fn)
        if mapped_role:
            roles_to_check.add(mapped_role)
        # Also check the function name directly as a pool key
        roles_to_check.add(fn)

    # Add aliases
    expanded: Set[str] = set(roles_to_check)
    alias_map = {
        "protein_base": ["main_component", "body_provider"],
        "main_component": ["protein_base", "body_provider"],
        "flavor_booster": ["flavor_base", "acidity_provider"],
    }
    for role in roles_to_check:
        for alias in alias_map.get(role, []):
            expanded.add(alias)

    for pool_key in expanded:
        for name in pools.get(pool_key, []):
            name_norm = name.strip()
            if name_norm and name_norm not in seen:
                seen.add(name_norm)
                result.append(name_norm)

    return result


def _collect_inventory_candidates(
    source_meta: Dict[str, Any],
    user_inventory: Optional[List[str]],
) -> List[str]:
    """Gather compatible inventory items by category/parent/function overlap."""
    if not user_inventory:
        return []

    source_category = _norm(str(source_meta.get("category") or ""))
    source_parent = _norm(str(source_meta.get("parent") or ""))
    source_functions = {_norm(str(f)) for f in source_meta.get("possible_functions", [])}
    # Expand with aliases
    expanded_fns = set(source_functions)
    for fn in source_functions:
        alias = ROLE_FUNCTION_ALIASES.get(fn)
        if alias:
            expanded_fns.add(alias)

    result: List[str] = []
    for item in normalize_ingredient_list_v2(user_inventory):
        meta = _metadata_for_normalized(item)
        canonical = str(item.get("canonical") or item.get("base") or "").strip()
        if not canonical:
            continue

        cand_category = _norm(str(meta.get("category") or ""))
        cand_parent = _norm(str(meta.get("parent") or ""))
        cand_functions = {_norm(str(f)) for f in meta.get("possible_functions", [])}

        matched = False
        if source_category and cand_category == source_category:
            matched = True
        elif source_parent and cand_parent and cand_parent == source_parent:
            matched = True
        elif expanded_fns & cand_functions:
            matched = True

        if matched:
            result.append(canonical)

    return result


def generate_substitute_candidates(
    missing_ingredient: Dict[str, Any],
    recipe_context: RecipeContext,
    user_inventory: Optional[List[str]] = None,
    inventory_only: bool = False,
) -> Dict[str, Any]:
    """Generate candidate substitutes for one missing ingredient (candidate-first)."""
    source_norm = dict(missing_ingredient)
    if not source_norm.get("canonical"):
        source_norm = normalize_ingredient_v2(str(source_norm.get("raw", ""))).to_dict()

    source_meta = _metadata_for_normalized(source_norm, allow_generation=True)
    inventory_keys = _inventory_lookup_keys(user_inventory)

    # ---- Collect candidate names from three sources ----
    seen_names: Set[str] = set()
    candidate_names: List[Tuple[str, str]] = []  # (name, source_tag)

    # Source 1: direct_substitutes from metadata
    for name in source_meta.get("direct_substitutes", []) or []:
        name_s = str(name).strip()
        if name_s and name_s not in seen_names:
            seen_names.add(name_s)
            candidate_names.append((name_s, "direct_substitute"))

    # Source 2: inventory candidates with compatible metadata
    for name in _collect_inventory_candidates(source_meta, user_inventory):
        if name not in seen_names:
            seen_names.add(name)
            candidate_names.append((name, "inventory_match"))

    # Source 3: pool candidates from ALL matching function pools
    for name in _collect_pool_candidates(source_meta):
        if name not in seen_names:
            seen_names.add(name)
            candidate_names.append((name, "pool_candidate"))

    # ---- Filter and collect candidates ----
    source_key = _norm(str(source_norm.get("canonical") or source_norm.get("base") or ""))
    # Intermediate list: (row_dict, priority_tuple) for deterministic cap
    accepted: List[Tuple[Dict[str, Any], Tuple[int, ...]]] = []

    for candidate_name, retrieval_source in candidate_names:
        candidate_norm = normalize_ingredient_v2(candidate_name).to_dict()
        candidate_key = _norm(str(candidate_norm.get("canonical") or candidate_norm.get("base") or ""))

        # Skip self-substitution
        if source_key and candidate_key and source_key == candidate_key:
            continue

        # Hard category filter — drop obviously incompatible candidates early
        candidate_meta = _metadata_for_normalized(candidate_norm)
        if not is_category_compatible(source_meta, candidate_meta):
            continue

        # Light compatibility refinements (fat/dairy, acid-source, salt guard)
        if not _is_fat_dairy_compatible(source_meta, candidate_meta):
            continue
        if not _is_specific_function_compatible(source_meta, candidate_meta, retrieval_source):
            continue

        available = _candidate_available(candidate_norm, inventory_keys)
        if inventory_only and user_inventory is not None and not available:
            continue

        # Prefilter: direct_substitutes and inventory items always pass.
        # Pool candidates must show at least one concrete similarity signal.
        if retrieval_source == "pool_candidate" and not available:
            if not _has_prefilter_similarity(source_meta, candidate_meta):
                continue

        priority = _prefilter_priority(
            retrieval_source, available, source_meta, candidate_meta,
        )

        accepted.append((
            {
                "source_raw": str(source_norm.get("raw", "")),
                "source_canonical": str(source_norm.get("canonical", "")),
                "source_base": str(source_norm.get("base", "")),
                "candidate": candidate_name,
                "candidate_canonical": str(candidate_norm.get("canonical", "")),
                "candidate_base": str(candidate_norm.get("base", "")),
                "available_in_inventory": available,
                "retrieval_source": retrieval_source,
            },
            priority,
        ))

    # Deterministic cap: keep highest-priority candidates up to the limit.
    accepted.sort(key=lambda pair: pair[1])
    candidate_rows = [row for row, _pri in accepted[:MAX_PREFILTER_CANDIDATES]]

    return {
        "source": source_norm,
        "source_meta": source_meta,
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
                source, recipe_context,
                user_inventory=user_inventory,
                inventory_only=inventory_only,
            )
        )
    return results
