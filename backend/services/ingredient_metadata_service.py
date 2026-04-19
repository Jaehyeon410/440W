"""Ingredient metadata service with strict schema + Gemini expansion.

This service is the single metadata entry point used by role inference,
candidate generation, and ranking.

Fallback order is explicit and stable:
1) exact lookup
2) normalized lookup
3) parent/canonical fallback
4) Gemini generation (strict enums only)
5) validated fallback object
"""

from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from gemini_client import generate_json_with_retry
from ingredient_normalizer_v2 import normalize_ingredient_v2
from services.metadata_schema import (
    ALLOWED_CATEGORIES,
    ALLOWED_FLAVOR_STRENGTHS,
    ALLOWED_FUNCTIONS,
    ALLOWED_SPECIAL_CAPABILITIES,
    ALLOWED_TEXTURES,
    build_default_metadata_entry,
    normalize_capabilities,
    normalize_category,
    normalize_direct_substitutes,
    normalize_flavor_strength,
    normalize_function,
    normalize_function_list,
    normalize_properties,
    normalize_source,
    normalize_texture,
)


METADATA_FILE = Path(__file__).resolve().parents[1] / "ingredient_metadata.json"
GENERATED_METADATA_FILE = Path(__file__).resolve().parents[1] / "ingredient_metadata.generated.json"
_generated_lock = Lock()


def _use_gemini_metadata_generation() -> bool:
    value = os.getenv("ENABLE_GEMINI_METADATA", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _normalized_key(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


import re as _re

_SENTENCE_PATTERN = _re.compile(r"\b(is|are|was|were|available|optional|stores?|can be|should)\b", _re.IGNORECASE)


def is_valid_metadata_key(key: str) -> bool:
    """Reject keys that look like descriptive phrases rather than ingredient names."""
    normalized = _normalized_key(key)
    if not normalized:
        return False
    if len(normalized) > 60:
        return False
    word_count = len(normalized.split())
    if word_count > 6:
        return False
    if _SENTENCE_PATTERN.search(normalized):
        return False
    return True


def build_fallback_metadata(ingredient_name: str) -> Dict[str, Any]:
    entry = build_default_metadata_entry(_normalized_key(ingredient_name))
    entry["source"] = "fallback"
    return entry


def validate_metadata_entry(entry: Dict[str, Any], ingredient_name: str) -> Dict[str, Any]:
    fallback = build_fallback_metadata(ingredient_name)
    normalized_key = _normalized_key(ingredient_name)

    parent_raw = entry.get("parent")
    parent = _normalized_key(str(parent_raw or "")) if parent_raw else None
    if parent == normalized_key:
        parent = None

    category = normalize_category(entry.get("category"), fallback=fallback["category"])
    primary_function = normalize_function(entry.get("primary_function"), fallback=fallback["primary_function"])
    possible_functions = normalize_function_list(entry.get("possible_functions"), fallback_primary=primary_function)
    if primary_function not in possible_functions:
        possible_functions.insert(0, primary_function)
    possible_functions = list(dict.fromkeys(possible_functions))

    properties = normalize_properties(entry.get("properties"))
    texture = normalize_texture(entry.get("texture"), fallback=fallback["texture"])
    flavor_strength = normalize_flavor_strength(entry.get("flavor_strength"), fallback=fallback["flavor_strength"])
    special_capabilities = normalize_capabilities(entry.get("special_capabilities"))
    direct_substitutes = normalize_direct_substitutes(entry.get("direct_substitutes"))
    source = normalize_source(entry.get("source"), fallback="fallback")

    return {
        "parent": parent,
        "category": category,
        "primary_function": primary_function,
        "possible_functions": possible_functions,
        "properties": properties,
        "texture": texture,
        "flavor_strength": flavor_strength,
        "special_capabilities": special_capabilities,
        "direct_substitutes": direct_substitutes,
        "source": source,
    }


def _build_gemini_prompt_payload(ingredient_name: str, parent_hint: Optional[str]) -> Dict[str, Any]:
    return {
        "task": "Generate strict ingredient metadata using only allowed enums.",
        "ingredient": ingredient_name,
        "parent_hint": parent_hint,
        "rules": {
            "return_json_only": True,
            "use_allowed_enum_values_only": True,
            "be_conservative": True,
            "prefer_parent_when_reasonable": True,
            "no_free_form_values": True,
        },
        "allowed": {
            "category": sorted(ALLOWED_CATEGORIES),
            "functions": sorted(ALLOWED_FUNCTIONS),
            "texture": sorted(ALLOWED_TEXTURES),
            "flavor_strength": sorted(ALLOWED_FLAVOR_STRENGTHS),
            "special_capabilities": sorted(ALLOWED_SPECIAL_CAPABILITIES),
            "property_levels": ["low", "medium", "high"],
            "source": ["gemini_generated"],
        },
        "required_schema": {
            "parent": "string|null",
            "category": "allowed_category",
            "primary_function": "allowed_function",
            "possible_functions": ["allowed_function"],
            "properties": {
                "fat": "low|medium|high",
                "moisture": "low|medium|high",
                "sweetness": "low|medium|high",
                "acidity": "low|medium|high",
                "saltiness": "low|medium|high",
            },
            "texture": "allowed_texture",
            "flavor_strength": "mild|medium|strong",
            "special_capabilities": ["allowed_capability"],
            "direct_substitutes": ["string"],
            "source": "gemini_generated",
        },
    }


def generate_metadata_with_gemini(ingredient_name: str, parent_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    payload = _build_gemini_prompt_payload(ingredient_name, parent_hint)
    base_prompt = (
        "You are a strict ingredient metadata generator for a cooking substitution engine. "
        "Return exactly one JSON object that matches the required schema and only uses allowed enum values. "
        "Do not output markdown. Do not output explanations."
        f"\nINPUT_JSON:\n{json.dumps(payload, ensure_ascii=True)}"
    )
    strict_prompt = (
        "Return JSON only. Any value outside allowed enums is forbidden. "
        "If uncertain, use category='unknown', primary_function='body_provider', possible_functions=['body_provider'], "
        "special_capabilities=[], direct_substitutes=[]. "
        "source must be 'gemini_generated'."
        f"\nINPUT_JSON:\n{json.dumps(payload, ensure_ascii=True)}"
    )
    out = generate_json_with_retry(base_prompt, strict_prompt)
    if not isinstance(out, dict):
        return None
    out["source"] = "gemini_generated"
    return out


@lru_cache(maxsize=1)
def load_generated_metadata() -> Dict[str, Any]:
    if not GENERATED_METADATA_FILE.exists():
        return {}
    try:
        with GENERATED_METADATA_FILE.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            return {}
        return {
            _normalized_key(key): value
            for key, value in raw.items()
            if isinstance(value, dict) and is_valid_metadata_key(key)
        }
    except (OSError, json.JSONDecodeError):
        return {}


def save_generated_metadata(ingredient_name: str, entry: Dict[str, Any]) -> None:
    key = _normalized_key(ingredient_name)
    if not key or not is_valid_metadata_key(key):
        return
    validated = validate_metadata_entry(entry, key)
    with _generated_lock:
        current = dict(load_generated_metadata())
        current[key] = validated

        temp_path = GENERATED_METADATA_FILE.with_suffix(".generated.tmp")
        with temp_path.open("w", encoding="utf-8") as fh:
            json.dump(current, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
        temp_path.replace(GENERATED_METADATA_FILE)
        load_generated_metadata.cache_clear()

    # Auto-register into substitute pools based on possible_functions.
    from services.substitute_pool_service import add_ingredient_to_pools
    added = add_ingredient_to_pools(key, validated)
    if added:
        print(f"[metadata→pools] '{key}' added to pools: {added}")


def _lookup_manual(key: str) -> Optional[Dict[str, Any]]:
    all_metadata = load_metadata()
    value = all_metadata.get(key)
    return copy.deepcopy(value) if isinstance(value, dict) else None


def _lookup_generated(key: str) -> Optional[Dict[str, Any]]:
    value = load_generated_metadata().get(key)
    return copy.deepcopy(value) if isinstance(value, dict) else None


def _lookup_exact(key: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    manual = _lookup_manual(key)
    if manual is not None:
        manual["source"] = normalize_source(manual.get("source"), fallback="manual")
        return manual, key
    generated = _lookup_generated(key)
    if generated is not None:
        generated["source"] = normalize_source(generated.get("source"), fallback="gemini_generated")
        return generated, key
    return None, None


def _parent_or_canonical_candidates(raw_name: str) -> List[str]:
    candidates: List[str] = []
    v2 = normalize_ingredient_v2(raw_name)
    for item in [v2.canonical, v2.base]:
        key = _normalized_key(item)
        if key and key not in candidates:
            candidates.append(key)
    normalized = _normalized_key(v2.canonical or raw_name)
    if normalized and normalized not in candidates:
        candidates.append(normalized)
    tokens = normalized.split()
    if len(tokens) >= 2:
        parent_candidate = _normalized_key(tokens[-1])
        if parent_candidate and parent_candidate not in candidates:
            candidates.append(parent_candidate)
    return candidates


def get_metadata_with_fallback(ingredient_name: str, *, allow_generation: bool = True) -> Dict[str, Any]:
    raw = _normalized_key(ingredient_name)
    if not raw:
        return build_fallback_metadata(ingredient_name)

    # 1) exact lookup
    entry, _ = _lookup_exact(raw)
    if entry is not None:
        validated = validate_metadata_entry(entry, raw)
        validated["source"] = normalize_source(entry.get("source"), fallback=validated["source"])
        return validated

    # 2) normalized lookup + 3) parent/canonical fallback
    parent_hint: Optional[str] = None
    for candidate in _parent_or_canonical_candidates(raw):
        found, found_key = _lookup_exact(candidate)
        if found is None:
            continue
        validated = validate_metadata_entry(found, candidate)
        if found_key and found_key != raw:
            parent_hint = found_key
        if found_key == raw:
            return validated

        # parent fallback clone
        cloned = dict(validated)
        cloned["parent"] = found_key
        cloned["source"] = normalize_source(found.get("source"), fallback=cloned["source"])
        return cloned

    # 4) Optional Gemini generation (disabled by default for low-latency requests)
    if allow_generation and _use_gemini_metadata_generation():
        generated = generate_metadata_with_gemini(raw, parent_hint=parent_hint)
        if isinstance(generated, dict):
            validated_generated = validate_metadata_entry(generated, raw)
            validated_generated["source"] = "gemini_generated"
            save_generated_metadata(raw, validated_generated)
            return validated_generated

    # 5) validated fallback metadata
    return build_fallback_metadata(raw)


@lru_cache(maxsize=1)
def load_metadata() -> Dict[str, Any]:
    """Load and cache metadata from JSON.

    Schema comment keys (prefixed with '_') are stripped so callers only see
    ingredient entries.  Returns an empty dict on failure so the rest of the
    app keeps running even when the file is missing or corrupt.
    """
    try:
        with METADATA_FILE.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return {
            _normalized_key(key): validate_metadata_entry(value, _normalized_key(key))
            for key, value in raw.items()
            if not key.startswith("_") and isinstance(value, dict)
        }
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[ingredient_metadata_service] failed to load {METADATA_FILE.name}: {exc}")
        return {}


def get_metadata(ingredient_key: str, *, allow_generation: bool = True) -> Dict[str, Any]:
    """Public metadata lookup with strict fallback chain and persistence.

    Set *allow_generation=False* in hot scoring paths so that candidates
    and inventory items do not trigger slow Gemini API calls.
    """
    return copy.deepcopy(get_metadata_with_fallback(ingredient_key, allow_generation=allow_generation))


def sync_pools_from_all_metadata() -> Dict[str, list]:
    """Sync substitute pools from both manual and generated metadata.

    Call at startup or after bulk metadata changes.  Returns a summary
    of {pool_role: [newly_added_ingredients]}.
    """
    from services.substitute_pool_service import sync_pools_from_metadata

    combined: Dict[str, Dict[str, Any]] = {}
    combined.update(load_metadata())
    combined.update(load_generated_metadata())

    summary = sync_pools_from_metadata(combined)
    if summary:
        total = sum(len(v) for v in summary.values())
        print(f"[pool_sync] {total} ingredient(s) added across {len(summary)} pool(s)")
        for role, items in summary.items():
            print(f"  {role}: +{items}")
    return summary

