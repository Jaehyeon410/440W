"""Dataset preprocessing script.

Reads the recipe dataset (data/western_5000.json), parses and normalizes
ingredients for each recipe, then writes a `parsed_ingredients` field back into
the JSON.

`parsed_ingredients` stores cleaned ingredient names (not raw lines), so runtime
matching can use stable canonical tokens directly.

Usage (from the repo root):
    .venv/Scripts/python.exe backend/scripts/preprocess_dataset.py
    .venv/Scripts/python.exe backend/scripts/preprocess_dataset.py --dataset data/western_5000.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow imports from the backend package when run from the repo root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from ingredient_parser import parse_ingredient_list  # noqa: E402
from recipe_utils import normalize_ingredient  # noqa: E402


DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "data" / "western_5000.json"


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def preprocess_dataset(dataset_path: Path) -> None:
    print(f"Loading dataset: {dataset_path}")
    with dataset_path.open("r", encoding="utf-8") as fh:
        recipes = json.load(fh)

    if not isinstance(recipes, list):
        print("ERROR: expected a JSON array at the top level.", file=sys.stderr)
        sys.exit(1)

    updated = 0
    skipped = 0
    for recipe in recipes:
        if not isinstance(recipe, dict):
            skipped += 1
            continue

        raw_ingredients = recipe.get("ingredients") or []
        if not isinstance(raw_ingredients, list):
            skipped += 1
            continue

        raw_clean = [item for item in raw_ingredients if isinstance(item, str) and item.strip()]
        parsed_lines = parse_ingredient_list(raw_clean)
        normalized_names = [normalize_ingredient(item) for item in parsed_lines]
        recipe["parsed_ingredients"] = _unique_preserve_order([name for name in normalized_names if name])
        updated += 1

    print(f"Processed {updated} recipes ({skipped} skipped).")

    with dataset_path.open("w", encoding="utf-8") as fh:
        json.dump(recipes, fh, ensure_ascii=False, indent=2)

    print(f"Written: {dataset_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add parsed_ingredients to the recipe dataset.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to the recipe JSON dataset (default: data/western_5000.json)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    preprocess_dataset(args.dataset)
