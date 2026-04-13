from __future__ import annotations

from typing import Any, Dict, List, Optional

PROPERTY_LEVELS = {"low", "medium", "high"}

ALLOWED_CATEGORIES = {
    "protein",
    "vegetable",
    "fruit",
    "dairy",
    "fat",
    "starch",
    "seasoning",
    "sauce_component",
    "sweetener",
    "liquid",
    "binder",
    "garnish",
    "aromatic",
    "condiment",
    "unknown",
}

ALLOWED_FUNCTIONS = {
    "main_protein",
    "aromatic",
    "seasoning",
    "sauce_base",
    "flavor_base",
    "body_provider",
    "fat_source",
    "acid_source",
    "sweetener",
    "binder",
    "starch_base",
    "liquid_base",
    "garnish",
    "fresh_component",
    "savory_component",
    "bulk_vegetable",
    "structure",
}

ALLOWED_TEXTURES = {
    "liquid",
    "powder",
    "paste",
    "creamy",
    "solid",
    "soft",
    "crunchy",
}

ALLOWED_FLAVOR_STRENGTHS = {"mild", "medium", "strong"}

ALLOWED_SPECIAL_CAPABILITIES = {
    "emulsifier",
    "gelatinizing",
    "thickening",
    "caramelizable",
    "searable",
    "roastable",
    "grillable",
    "meltable",
    "whippable",
    "reducible",
    "marinating",
    "none",
}

ALLOWED_SOURCES = {"manual", "gemini_generated", "fallback"}

CATEGORY_ALIASES = {
    "produce": "vegetable",
    "misc": "unknown",
}

FUNCTION_ALIASES = {
    "protein_base": "main_protein",
    "acidity_provider": "acid_source",
    "moisture_provider": "liquid_base",
    "flavor_booster": "seasoning",
    "richness": "fat_source",
    "creaminess": "body_provider",
    "main_component": "main_protein",
    "serving_base": "starch_base",
    "coating": "structure",
    "emulsifier": "binder",
    "thickener": "binder",
    "texture_contrast": "garnish",
    "aerated_base": "body_provider",
    "sweetness": "sweetener",
    "acidity": "acid_source",
    "aroma": "aromatic",
    "moisture": "liquid_base",
}

CAPABILITY_ALIASES = {
    "browning": "searable",
    "fermentable": "marinating",
    "thickener": "thickening",
}


def _norm(value: str) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def normalize_category(value: Any, fallback: str = "unknown") -> str:
    candidate = _norm(str(value or ""))
    candidate = CATEGORY_ALIASES.get(candidate, candidate)
    if candidate in ALLOWED_CATEGORIES:
        return candidate
    return fallback


def normalize_function(value: Any, fallback: str = "body_provider") -> str:
    candidate = _norm(str(value or ""))
    candidate = FUNCTION_ALIASES.get(candidate, candidate)
    if candidate in ALLOWED_FUNCTIONS:
        return candidate
    return fallback


def normalize_texture(value: Any, fallback: str = "solid") -> str:
    candidate = _norm(str(value or ""))
    if candidate in ALLOWED_TEXTURES:
        return candidate
    return fallback


def normalize_flavor_strength(value: Any, fallback: str = "mild") -> str:
    candidate = _norm(str(value or ""))
    if candidate in ALLOWED_FLAVOR_STRENGTHS:
        return candidate
    return fallback


def normalize_capabilities(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    seen = set()
    for value in values:
        candidate = _norm(str(value or ""))
        candidate = CAPABILITY_ALIASES.get(candidate, candidate)
        if candidate not in ALLOWED_SPECIAL_CAPABILITIES:
            continue
        if candidate == "none":
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out


def normalize_properties(properties: Any) -> Dict[str, str]:
    safe = {
        "fat": "low",
        "moisture": "medium",
        "sweetness": "low",
        "acidity": "low",
        "saltiness": "low",
    }
    if not isinstance(properties, dict):
        return safe
    for key in ["fat", "moisture", "sweetness", "acidity", "saltiness"]:
        value = _norm(str(properties.get(key, safe[key])))
        safe[key] = value if value in PROPERTY_LEVELS else safe[key]
    return safe


def normalize_function_list(values: Any, fallback_primary: str = "body_provider") -> List[str]:
    raw_values = values if isinstance(values, list) else []
    out: List[str] = []
    seen = set()
    for value in raw_values:
        normalized = normalize_function(value, fallback=fallback_primary)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def normalize_source(value: Any, fallback: str = "fallback") -> str:
    candidate = _norm(str(value or ""))
    if candidate in ALLOWED_SOURCES:
        return candidate
    return fallback


def normalize_direct_substitutes(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    seen = set()
    for value in values:
        candidate = " ".join(str(value or "").strip().lower().split())
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out


def build_default_metadata_entry(ingredient_name: str) -> Dict[str, Any]:
    return {
        "parent": None,
        "category": "unknown",
        "primary_function": "body_provider",
        "possible_functions": ["body_provider"],
        "properties": {
            "fat": "low",
            "moisture": "medium",
            "sweetness": "low",
            "acidity": "low",
            "saltiness": "low",
        },
        "texture": "solid",
        "flavor_strength": "mild",
        "special_capabilities": [],
        "direct_substitutes": [],
        "source": "fallback",
    }
