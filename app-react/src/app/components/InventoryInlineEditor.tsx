import { useEffect, useMemo, useState } from "react";

interface InventoryInlineEditorProps {
  ingredients: string[];
  missingCandidates?: string[];
  isSaving?: boolean;
  onApply: (ingredients: string[]) => Promise<void> | void;
}

export function InventoryInlineEditor({
  ingredients,
  missingCandidates = [],
  isSaving = false,
  onApply,
}: InventoryInlineEditorProps) {
  const [draft, setDraft] = useState("");
  const [localIngredients, setLocalIngredients] = useState<string[]>(ingredients);

  useEffect(() => {
    setLocalIngredients(ingredients);
  }, [ingredients]);

  const normalizedCandidates = useMemo(() => {
    const seen = new Set(localIngredients);
    return missingCandidates.filter((item) => !seen.has(item));
  }, [localIngredients, missingCandidates]);

  const addIngredient = (value: string) => {
    const normalized = value.trim().toLowerCase();
    if (!normalized || localIngredients.includes(normalized)) {
      return;
    }
    setLocalIngredients((prev) => [...prev, normalized]);
    setDraft("");
  };

  const removeIngredient = (value: string) => {
    setLocalIngredients((prev) => prev.filter((item) => item !== value));
  };

  const resetToCurrent = () => {
    setLocalIngredients(ingredients);
    setDraft("");
  };

  const hasChanges = useMemo(() => {
    if (ingredients.length !== localIngredients.length) {
      return true;
    }
    return ingredients.some((item, index) => item !== localIngredients[index]);
  }, [ingredients, localIngredients]);

  return (
    <section className="bg-white rounded-lg border p-4 mb-6">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h3 className="font-semibold text-gray-900">Edit inventory here</h3>
        <span className="text-xs text-gray-500">{localIngredients.length} items</span>
      </div>

      <div className="flex gap-2 mb-3">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              addIngredient(draft);
            }
          }}
          placeholder="Add missing ingredient"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
        />
        <button
          onClick={() => addIngredient(draft)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          Add
        </button>
      </div>

      {normalizedCandidates.length > 0 && (
        <div className="mb-3">
          <p className="text-xs text-gray-600 mb-2">Missing right now</p>
          <div className="flex flex-wrap gap-2">
            {normalizedCandidates.slice(0, 8).map((item) => (
              <button
                key={item}
                onClick={() => addIngredient(item)}
                className="px-2.5 py-1.5 rounded-full text-xs border border-orange-300 text-orange-700 bg-orange-50 hover:bg-orange-100"
              >
                I have this: {item}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        {localIngredients.map((item) => (
          <span
            key={item}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm border border-gray-300 bg-gray-50"
          >
            {item}
            <button onClick={() => removeIngredient(item)} className="text-gray-500 hover:text-gray-800">
              x
            </button>
          </span>
        ))}
        {localIngredients.length === 0 && <p className="text-sm text-gray-500">No ingredients yet.</p>}
      </div>

      <div className="flex gap-2">
        <button
          onClick={resetToCurrent}
          disabled={!hasChanges || isSaving}
          className="px-3 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm disabled:opacity-40"
        >
          Reset
        </button>
        <button
          onClick={() => onApply(localIngredients)}
          disabled={!hasChanges || isSaving}
          className="px-4 py-2 bg-orange-600 text-white rounded-lg text-sm font-medium hover:bg-orange-700 disabled:opacity-40"
        >
          {isSaving ? "Updating..." : "Apply and recalculate"}
        </button>
      </div>
    </section>
  );
}
