"""Substitute pool management service.

Provides loading, saving, and automatic synchronisation of
substitute_pools.json based on ingredient metadata.

When ingredient metadata is created or updated, the pool service can
automatically register the ingredient into the correct role-based pools
by mapping metadata schema functions back to pool role keys.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set

from services.metadata_schema import FUNCTION_ALIASES


POOLS_FILE = Path(__file__).resolve().parents[1] / "substitute_pools.json"
_pools_lock = Lock()

# ---------------------------------------------------------------------------
# Reverse mapping: schema function name  →  pool role key(s)
#
# substitute_pools.json keys use "role vocabulary" names (e.g. acidity_provider)
# while metadata possible_functions use "schema function" names (e.g. acid_source).
# FUNCTION_ALIASES maps  role_vocab → schema_func.  We invert that here, and
# also include direct matches where pool key == schema function name.
# ---------------------------------------------------------------------------

# Pool keys that exist in substitute_pools.json and are valid role names.
_KNOWN_POOL_KEYS: Set[str] = {
    "thickener",
    "structure",
    "aerated_base",
    "topping",
    "garnish",
    "texture_contrast",
    "flavor_base",
    "sauce_base",
    "body_provider",
    "protein_base",
    "main_component",
    "sweetener",
    "acidity_provider",
    "moisture_provider",
}

# Pools that require special capabilities before an ingredient can be added.
_POOL_REQUIRED_CAPABILITIES: Dict[str, Set[str]] = {
    "thickener": {"gelatinizing", "thickening"},
    "aerated_base": {"whippable"},
}

# Pools where auto-addition should only happen when the function is the
# ingredient's *primary* function.  This prevents overly generic roles
# like body_provider from pulling in every ingredient.
_PRIMARY_ONLY_POOLS: Set[str] = {
    "body_provider",
}


def _build_schema_to_pool_map() -> Dict[str, List[str]]:
    """Build mapping from schema function names to pool role keys.

    This inverts FUNCTION_ALIASES and also includes direct matches.
    """
    mapping: Dict[str, List[str]] = {}

    # Invert FUNCTION_ALIASES: role_vocab -> schema_func  ⟹  schema_func -> [role_vocabs]
    for role_vocab, schema_func in FUNCTION_ALIASES.items():
        if role_vocab in _KNOWN_POOL_KEYS:
            mapping.setdefault(schema_func, [])
            if role_vocab not in mapping[schema_func]:
                mapping[schema_func].append(role_vocab)

    # Direct matches: pool key names that are also valid schema function names.
    for pool_key in _KNOWN_POOL_KEYS:
        mapping.setdefault(pool_key, [])
        if pool_key not in mapping[pool_key]:
            mapping[pool_key].append(pool_key)

    return mapping


SCHEMA_FUNC_TO_POOL_ROLES = _build_schema_to_pool_map()


# ---------------------------------------------------------------------------
# Pool I/O
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_pools() -> Dict[str, List[str]]:
    """Load substitute pools from JSON (cached)."""
    try:
        with POOLS_FILE.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[substitute_pool_service] failed to load pools: {exc}")
        return {}

    pools: Dict[str, List[str]] = {}
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if isinstance(value, list):
            pools[key] = [str(item).strip() for item in value if str(item).strip()]
    return pools


def _save_pools(pools: Dict[str, List[str]]) -> None:
    """Atomically write pools back to JSON, preserving schema comment keys."""
    try:
        with POOLS_FILE.open("r", encoding="utf-8") as fh:
            original = json.load(fh)
    except (OSError, json.JSONDecodeError):
        original = {}

    # Preserve top-level comment keys like _schema_version, _schema_note.
    output: Dict[str, Any] = {}
    for key, value in original.items():
        if key.startswith("_"):
            output[key] = value

    for key in pools:
        output[key] = pools[key]

    temp_path = POOLS_FILE.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    temp_path.replace(POOLS_FILE)
    load_pools.cache_clear()

    # Clear the generation service's separate pool cache so it picks up changes.
    try:
        from services.substitute_generation_service import load_substitute_pools
        load_substitute_pools.cache_clear()
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Pool role classification for a single ingredient
# ---------------------------------------------------------------------------

def classify_pool_roles(
    ingredient_name: str,
    metadata: Dict[str, Any],
) -> List[str]:
    """Determine which pool roles an ingredient belongs to based on metadata.

    Returns a list of pool role keys (e.g. ["acidity_provider", "garnish"]).
    """
    possible_functions: List[str] = [
        str(fn).strip().lower()
        for fn in metadata.get("possible_functions", [])
    ]
    primary_function: str = str(metadata.get("primary_function", "")).strip().lower()
    capabilities: Set[str] = {
        str(cap).strip().lower()
        for cap in metadata.get("special_capabilities", [])
    }

    matched_roles: List[str] = []
    seen: Set[str] = set()

    for func in possible_functions:
        pool_roles = SCHEMA_FUNC_TO_POOL_ROLES.get(func, [])
        for role in pool_roles:
            if role in seen:
                continue
            # Check capability requirements.
            required = _POOL_REQUIRED_CAPABILITIES.get(role)
            if required and not required.intersection(capabilities):
                continue
            # For primary-only pools, only add if this function is the
            # ingredient's primary function (avoids noise from generic roles).
            if role in _PRIMARY_ONLY_POOLS and func != primary_function:
                continue
            seen.add(role)
            matched_roles.append(role)

    return matched_roles


# ---------------------------------------------------------------------------
# Pool auto-update
# ---------------------------------------------------------------------------

def add_ingredient_to_pools(
    ingredient_name: str,
    metadata: Dict[str, Any],
) -> List[str]:
    """Classify an ingredient and add it to the appropriate pools.

    Returns the list of pool roles the ingredient was added to (new only).
    """
    name = ingredient_name.strip().lower()
    if not name:
        return []

    roles = classify_pool_roles(name, metadata)
    if not roles:
        return []

    added_to: List[str] = []
    with _pools_lock:
        pools = dict(load_pools())
        changed = False
        for role in roles:
            pool_list = pools.setdefault(role, [])
            if name not in pool_list:
                pool_list.append(name)
                added_to.append(role)
                changed = True
        if changed:
            _save_pools(pools)

    return added_to


def sync_pools_from_metadata(all_metadata: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """Bulk-sync all pools from a full metadata dictionary.

    Iterates every ingredient in the metadata dict and ensures it appears
    in the correct pools.  Returns a summary of {role: [newly_added_ingredients]}.
    """
    summary: Dict[str, List[str]] = {}

    with _pools_lock:
        pools = dict(load_pools())
        changed = False

        for ingredient_name, meta in all_metadata.items():
            if not isinstance(meta, dict):
                continue
            name = ingredient_name.strip().lower()
            if not name:
                continue

            roles = classify_pool_roles(name, meta)
            for role in roles:
                pool_list = pools.setdefault(role, [])
                if name not in pool_list:
                    pool_list.append(name)
                    summary.setdefault(role, []).append(name)
                    changed = True

        if changed:
            _save_pools(pools)

    return summary
