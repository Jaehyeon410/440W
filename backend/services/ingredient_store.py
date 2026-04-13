import json
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock
import time
from typing import Dict, List, Optional
import uuid

from models.ingredient_attributes import IngredientAttributes
from recipe_utils import normalize_ingredient
from services.ingredient_classifier import classify_ingredient_attributes, fallback_ingredient_attributes


BACKEND_DIR = Path(__file__).resolve().parents[1]
MANUAL_ROLES_FILE = BACKEND_DIR / "ingredient_roles.json"
GENERATED_ROLES_FILE = BACKEND_DIR / "ingredient_roles.generated.json"

LIQUID_HINTS = {"broth", "cream", "juice", "liquid", "milk", "oil", "sauce", "stock", "vinegar", "water", "wine"}
FAT_HINTS = {"butter", "cream", "creamy", "fat", "mayo", "mayonnaise", "oil"}
PROTEIN_HINTS = {"protein_base"}
DAIRY_HINTS = {"creaminess"}
STARCH_HINTS = {"structure"}
PRODUCE_HINTS = {"moisture"}
SEASONING_HINTS = {"acidity", "aroma"}

LEGACY_PROPERTY_MAP = {
    "acid": "acidic",
    "aroma": "aromatic",
    "creamy": "creamy",
    "fat": "rich",
    "fresh": "aromatic",
    "heat": "spicy",
    "mild": "mild",
    "meaty": "savory",
    "salty": "savory",
    "smoky": "savory",
    "sweet": "sweet",
    "umami": "savory",
}

LEGACY_FUNCTION_MAP = {
    "acid": "acidity",
    "aroma": "aroma",
    "carb": "bulk",
    "creamy": "creaminess",
    "dairy": "creaminess",
    "fat": "fat_source",
    "fresh": "moisture",
    "grain": "structure",
    "meaty": "protein_base",
    "protein": "protein_base",
    "seafood": "protein_base",
    "starchy": "structure",
    "sweet": "sweetness",
}

EXACT_PRODUCE_ITEMS = {"bell pepper", "broccoli", "carrot", "celery", "cucumber", "lettuce", "mushroom", "mushrooms", "onion", "spinach", "tomato", "zucchini"}
EXACT_STARCH_ITEMS = {"pasta", "potato", "rice"}
EXACT_DAIRY_ITEMS = {"cheese", "cream", "milk", "yogurt"}
EXACT_FAT_ITEMS = {"butter", "mayo", "mayonnaise", "oil", "olive oil"}
EXACT_LIQUID_ITEMS = {"broth", "stock", "water", "wine"}
EXACT_SEASONING_ITEMS = {"garlic", "lemon", "mustard", "pepper", "salt", "soy sauce", "vinegar"}
EXACT_PROTEIN_ITEMS = {"beef", "chicken", "fish", "pork", "shrimp", "tofu", "turkey"}

_generated_cache_lock = Lock()
_generated_cache: Optional[Dict[str, IngredientAttributes]] = None


def _dedupe_strings(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        normalized = str(value).strip().lower().replace("-", " ")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _category_from_roles_and_name(ingredient: str, roles: List[str]) -> str:
    role_set = set(roles)
    tokens = set(ingredient.split())

    if ingredient in EXACT_PROTEIN_ITEMS or role_set.intersection(PROTEIN_HINTS) or tokens.intersection({"beef", "chicken", "fish", "pork", "protein", "shrimp", "tofu", "turkey"}):
        return "protein"
    if ingredient in EXACT_FAT_ITEMS or role_set.intersection({"fat_source"}) or tokens.intersection({"butter", "mayo", "mayonnaise", "oil"}):
        return "fat"
    if ingredient in EXACT_LIQUID_ITEMS or tokens.intersection({"broth", "stock", "water", "wine"}):
        return "liquid"
    if ingredient in EXACT_DAIRY_ITEMS or role_set.intersection(DAIRY_HINTS) or tokens.intersection({"cheese", "cream", "dairy", "milk", "yogurt"}):
        return "dairy"
    if ingredient in EXACT_STARCH_ITEMS or role_set.intersection(STARCH_HINTS) or tokens.intersection({"bread", "grain", "noodle", "pasta", "potato", "rice", "starch"}):
        return "starch"
    if ingredient in EXACT_PRODUCE_ITEMS or role_set.intersection(PRODUCE_HINTS) or tokens.intersection({"broccoli", "carrot", "celery", "cucumber", "greens", "lettuce", "mushroom", "spinach", "tomato", "vegetable", "zucchini"}):
        return "produce"
    if ingredient in EXACT_SEASONING_ITEMS or role_set.intersection(SEASONING_HINTS) or tokens.intersection({"garlic", "mustard", "pepper", "salt", "sauce", "soy", "spice", "vinegar"}):
        return "seasoning"
    return "misc"


def _attributes_from_roles(
    ingredient: str,
    roles: List[str],
    source: str,
    confidence: float,
) -> IngredientAttributes:
    normalized = normalize_ingredient(ingredient or "")
    normalized_roles = _dedupe_strings([str(role) for role in roles])
    properties = _dedupe_strings([LEGACY_PROPERTY_MAP[role] for role in normalized_roles if role in LEGACY_PROPERTY_MAP])
    functions = _dedupe_strings([LEGACY_FUNCTION_MAP[role] for role in normalized_roles if role in LEGACY_FUNCTION_MAP])
    category = _category_from_roles_and_name(normalized, functions + properties)
    role_set = set(functions + properties)

    if not functions:
        default_functions = {
            "protein": ["protein_base", "bulk"],
            "produce": ["moisture", "bulk"],
            "starch": ["structure", "bulk"],
            "dairy": ["creaminess", "moisture"],
            "seasoning": ["aroma"],
            "fat": ["fat_source"],
            "liquid": ["moisture"],
            "misc": [],
        }
        functions = default_functions.get(category, [])

    if not properties:
        default_properties = {
            "protein": ["savory", "mild"],
            "produce": ["mild", "soft"],
            "starch": ["mild", "soft"],
            "dairy": ["creamy"],
            "seasoning": ["aromatic"],
            "fat": ["rich"],
            "liquid": ["savory"],
            "misc": [],
        }
        properties = default_properties.get(category, [])

    return IngredientAttributes(
        ingredient=normalized,
        category=category,
        properties=properties,
        functions=functions,
        is_liquid=bool(role_set.intersection(LIQUID_HINTS) or set(normalized.split()).intersection(LIQUID_HINTS)),
        is_fat_based=bool(role_set.intersection(FAT_HINTS) or set(normalized.split()).intersection(FAT_HINTS)),
        confidence=confidence,
        source=source,
    )


@lru_cache(maxsize=1)
def load_manual_roles() -> Dict[str, List[str]]:
    with MANUAL_ROLES_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return {
        normalize_ingredient(key): _dedupe_strings([str(item) for item in value])
        for key, value in data.items()
        if isinstance(value, list) and normalize_ingredient(key)
    }


def _load_generated_cache_from_disk() -> Dict[str, IngredientAttributes]:
    if not GENERATED_ROLES_FILE.exists():
        GENERATED_ROLES_FILE.write_text("{}\n", encoding="utf-8")

    try:
        with GENERATED_ROLES_FILE.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except (OSError, json.JSONDecodeError):
        raw_data = {}

    if not isinstance(raw_data, dict):
        raw_data = {}

    cache: Dict[str, IngredientAttributes] = {}
    rewrite_required = False
    for key, value in raw_data.items():
        raw_key = str(key or "")
        normalized_key = normalize_ingredient(key or "")
        if not normalized_key:
            continue

        try:
            if isinstance(value, dict):
                repaired_value = {**value, "ingredient": normalized_key}
                cache[normalized_key] = IngredientAttributes.model_validate(repaired_value)
                if raw_key != normalized_key or str(value.get("ingredient") or "") != normalized_key:
                    rewrite_required = True
            elif isinstance(value, list):
                cache[normalized_key] = _attributes_from_roles(
                    normalized_key,
                    [str(item) for item in value],
                    source="generated_cache",
                    confidence=0.9,
                )
                rewrite_required = True
        except Exception:
            continue

    if rewrite_required:
        try:
            _write_generated_cache(cache)
        except OSError:
            pass

    return cache


def _get_generated_cache() -> Dict[str, IngredientAttributes]:
    global _generated_cache
    with _generated_cache_lock:
        if _generated_cache is None:
            _generated_cache = _load_generated_cache_from_disk()
        return _generated_cache


def _should_refresh_cached_attributes(ingredient: str, cached: IngredientAttributes) -> bool:
    refreshed_fallback = fallback_ingredient_attributes(ingredient)
    if cached.source != "fallback":
        return False
    if cached.category != refreshed_fallback.category:
        return True
    if cached.properties != refreshed_fallback.properties:
        return True
    if cached.functions != refreshed_fallback.functions:
        return True
    if cached.is_liquid != refreshed_fallback.is_liquid:
        return True
    if cached.is_fat_based != refreshed_fallback.is_fat_based:
        return True
    return False


def _write_generated_cache(cache: Dict[str, IngredientAttributes]) -> None:
    payload = {key: value.model_dump() for key, value in sorted(cache.items())}
    # Use a unique temp file per write to avoid collisions across processes (reload worker, etc.).
    temp_path = GENERATED_ROLES_FILE.with_name(f"{GENERATED_ROLES_FILE.name}.{uuid.uuid4().hex}.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=True, indent=2, sort_keys=True)
        file.write("\n")

    last_error: Optional[OSError] = None
    for _ in range(3):
        try:
            os.replace(temp_path, GENERATED_ROLES_FILE)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)

    try:
        if temp_path.exists():
            temp_path.unlink()
    except OSError:
        pass

    if last_error is not None:
        raise last_error


def get_ingredient_attributes(
    ingredient_name: str,
    original_ingredient_text: Optional[str] = None,
    recipe_title: Optional[str] = None,
    nearby_ingredients: Optional[List[str]] = None,
) -> IngredientAttributes:
    global _generated_cache

    normalized = normalize_ingredient(ingredient_name or "")
    if not normalized:
        return fallback_ingredient_attributes(ingredient_name)

    manual_roles = load_manual_roles().get(normalized)
    if manual_roles is not None:
        return _attributes_from_roles(normalized, manual_roles, source="manual", confidence=1.0)

    cache = _get_generated_cache()
    cached = cache.get(normalized)
    if cached is not None and not _should_refresh_cached_attributes(normalized, cached):
        return cached

    classified = classify_ingredient_attributes(
        normalized,
        original_ingredient_text=original_ingredient_text,
        recipe_title=recipe_title,
        nearby_ingredients=nearby_ingredients,
    )
    if classified.ingredient != normalized:
        classified = classified.model_copy(update={"ingredient": normalized})

    with _generated_cache_lock:
        if _generated_cache is None:
            _generated_cache = _load_generated_cache_from_disk()
        _generated_cache[normalized] = classified
        try:
            _write_generated_cache(_generated_cache)
        except OSError as exc:
            # Cache persistence failure should never fail substitution/recommendation requests.
            print(f"[ingredient_store] cache write skipped ({type(exc).__name__})")

    return classified