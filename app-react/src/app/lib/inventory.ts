export const INVENTORY_UPDATED_EVENT = "fridge-remix:inventory-updated";

function normalizeIngredientName(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

export function normalizeIngredientList(values: string[]): string[] {
  const unique = new Set<string>();
  values.forEach((value) => {
    const normalized = normalizeIngredientName(value);
    if (normalized) {
      unique.add(normalized);
    }
  });
  return [...unique];
}

export function getStoredInventory(): string[] {
  try {
    const raw =
      localStorage.getItem("user_ingredients") ||
      localStorage.getItem("userIngredients") ||
      localStorage.getItem("fridgeIngredients") ||
      "[]";
    const parsed = JSON.parse(raw) as string[];
    return normalizeIngredientList(Array.isArray(parsed) ? parsed : []);
  } catch {
    return [];
  }
}

export function saveStoredInventory(values: string[]): string[] {
  const normalized = normalizeIngredientList(values);
  const serialized = JSON.stringify(normalized);

  localStorage.setItem("user_ingredients", serialized);
  localStorage.setItem("userIngredients", serialized);
  localStorage.setItem("fridgeIngredients", serialized);

  window.dispatchEvent(
    new CustomEvent(INVENTORY_UPDATED_EVENT, {
      detail: { ingredients: normalized },
    })
  );

  return normalized;
}

export function addIngredientToInventory(current: string[], ingredient: string): string[] {
  return normalizeIngredientList([...current, ingredient]);
}
