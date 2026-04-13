import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ArrowLeft, Copy, Save, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
  getRecipeDetail,
  getSubstitutions,
  type RecipeDetailResponse,
  type RemixResponse,
} from "../../api/client";
import { StartFromHomeFallback } from "../components/StartFromHomeFallback";
import { InventoryInlineEditor } from "../components/InventoryInlineEditor";
import { addIngredientToInventory, getStoredInventory, saveStoredInventory } from "../lib/inventory";
import { normalizeStepList } from "../lib/steps";

function readStoredRecipeAndRemix(): { recipe: RecipeDetailResponse | null; remix: RemixResponse | null } {
  try {
    const remix = JSON.parse(
      sessionStorage.getItem("finalRemix") || localStorage.getItem("finalRemix") || "null"
    ) as RemixResponse | null;
    const recipe = JSON.parse(
      sessionStorage.getItem("recipeDetail") || localStorage.getItem("recipeDetail") || "null"
    ) as RecipeDetailResponse | null;
    return { recipe, remix };
  } catch {
    return { recipe: null, remix: null };
  }
}

export default function FinalRecipe() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [{ recipe, remix }, setRecipeAndRemix] = useState(readStoredRecipeAndRemix);
  const [inventory, setInventory] = useState<string[]>(getStoredInventory());
  const [isInventoryUpdating, setIsInventoryUpdating] = useState(false);

  if (!recipe || !remix || recipe.id !== id || (remix.recipe_id && remix.recipe_id !== id)) {
    return <StartFromHomeFallback title="Final recipe not ready" />;
  }

  const renderedSteps = useMemo(() => {
    return normalizeStepList(remix.edited_steps, recipe.steps);
  }, [remix.edited_steps, recipe.steps]);

  const missingCandidates = [
    ...recipe.missing_main,
    ...recipe.missing_seasoning,
    ...recipe.missing_other,
  ];

  const applyInventoryUpdate = async (nextInventory: string[]) => {
    if (!id) {
      return;
    }

    setIsInventoryUpdating(true);
    try {
      const normalizedInventory = saveStoredInventory(nextInventory);
      setInventory(normalizedInventory);

      const refreshedRecipe = await getRecipeDetail(id, normalizedInventory);
      sessionStorage.setItem("recipeDetail", JSON.stringify(refreshedRecipe));
      localStorage.setItem("recipeDetail", JSON.stringify(refreshedRecipe));

      await getSubstitutions({
        recipe_id: refreshedRecipe.id,
        user_ingredients: normalizedInventory,
        missing_main: refreshedRecipe.missing_main,
        missing_seasoning: refreshedRecipe.missing_seasoning,
        missing_other: refreshedRecipe.missing_other,
      });

      setRecipeAndRemix((prev) => ({ ...prev, recipe: refreshedRecipe }));
      toast.success("Inventory updated and missing/substitute options recalculated");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update inventory");
    } finally {
      setIsInventoryUpdating(false);
    }
  };

  const handleCopy = () => {
    const text = generateRecipeText();
    navigator.clipboard.writeText(text);
    toast.success("Recipe copied to clipboard!");
  };

  const handleSave = () => {
    toast.success("Recipe saved!");
  };

  const generateRecipeText = () => {
    let text = `${recipe.title}\n\n`;
    text += `ID: ${recipe.id}\n\n`;
    text += `INGREDIENTS:\n`;
    recipe.ingredients.forEach((ing) => {
      text += `- ${ing.name} (${ing.status})\n`;
    });
    if (remix.substitutions.main.length > 0 || remix.substitutions.seasoning.length > 0) {
      text += `\nSUBSTITUTIONS:\n`;
      remix.substitutions.main.forEach((item) => {
        text += `- ${item.from} -> ${item.to} (${item.reason})\n`;
      });
      remix.substitutions.seasoning.forEach((item) => {
        text += `- ${item.from} -> ${item.to} (${item.reason})\n`;
      });
    }
    text += `\nSTEPS:\n`;
    renderedSteps.forEach((step, idx) => {
      text += `${idx + 1}. ${step}\n`;
    });
    return text;
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/recipe/${recipe.id}`)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="size-5 text-gray-700" />
            </button>
            <h1 className="text-xl font-semibold text-gray-900">Your Remixed Recipe</h1>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <InventoryInlineEditor
          ingredients={inventory}
          missingCandidates={missingCandidates}
          isSaving={isInventoryUpdating}
          onApply={applyInventoryUpdate}
        />

        {/* Summary Block */}
        <section className="bg-gradient-to-br from-orange-50 to-green-50 rounded-xl p-6 mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">{recipe.title}</h2>
          <div className="flex items-center gap-4 text-sm text-gray-700 mb-4">
            <span>•</span>
            <span>{renderedSteps.length} steps</span>
            <span>•</span>
            <span>{recipe.ingredients.length} ingredients</span>
          </div>
          <p className="text-gray-700">{remix.flavor_change_summary}</p>
        </section>

        {/* Used Ingredients */}
        <section className="bg-white rounded-lg border p-6 mb-6">
          <h3 className="font-semibold text-gray-900 mb-4">Ingredients You're Using</h3>
          <div className="grid sm:grid-cols-2 gap-2">
            {recipe.ingredients
              .filter((ing) => ing.status === "available")
              .map((ing, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <span className="text-green-600">✓</span>
                  <span className="text-gray-700">{ing.name}</span>
                </div>
              ))}
          </div>
        </section>

        {/* Substitution Summary */}
        {(remix.substitutions.main.length > 0 || remix.substitutions.seasoning.length > 0) && (
          <section className="bg-white rounded-lg border p-6 mb-6">
            <h3 className="font-semibold text-gray-900 mb-4">Substitutions Made</h3>

            {remix.substitutions.main.map((item) => (
              <div key={`${item.from}-${item.to}`} className="mb-3 p-3 bg-blue-50 rounded-lg">
                <p className="text-sm">
                  <span className="font-medium text-gray-900">{item.from}</span>
                  <span className="text-gray-600"> → </span>
                  <span className="font-medium text-blue-700">{item.to}</span>
                </p>
              </div>
            ))}

            {remix.substitutions.seasoning.map((item) => (
              <div key={`${item.from}-${item.to}`} className="mb-3 p-3 bg-green-50 rounded-lg">
                <p className="text-sm">
                  <span className="font-medium text-gray-900">{item.from}</span>
                  <span className="text-gray-600"> → </span>
                  <span className="font-medium text-green-700">{item.to}</span>
                </p>
              </div>
            ))}
          </section>
        )}

        {/* Flavor Change Summary */}
        {(remix.substitutions.main.length > 0 || remix.substitutions.seasoning.length > 0) && (
          <section className="bg-orange-50 border border-orange-200 rounded-lg p-6 mb-6">
            <h3 className="font-semibold text-gray-900 mb-2">Expected Flavor Changes</h3>
            <p className="text-gray-700">{remix.flavor_change_summary}</p>
          </section>
        )}

        {/* Cooking Steps - Summary View */}
        <section className="bg-white rounded-lg border p-6 mb-8">
          <h3 className="font-semibold text-gray-900 mb-4">Cooking Steps Summary</h3>
          <p className="text-sm text-gray-600 mb-4">
            Click on any step to see detailed instructions, tips, and warnings
          </p>
          <div className="space-y-3">
            {renderedSteps.map((step, idx) => (
              <button
                key={idx}
                onClick={() => navigate(`/recipe/${recipe.id}/step/${idx}`)}
                className="w-full flex items-center gap-4 p-4 border border-gray-200 rounded-lg hover:border-orange-300 hover:bg-orange-50 transition-colors text-left group"
              >
                <span className="flex-shrink-0 w-10 h-10 bg-orange-600 text-white rounded-full flex items-center justify-center font-semibold group-hover:bg-orange-700">
                  {idx + 1}
                </span>
                <div className="flex-1">
                  <p className="font-medium text-gray-900 mb-1">Step {idx + 1}</p>
                  <p className="text-sm text-gray-600">{step}</p>
                </div>
                <span className="text-orange-600 opacity-0 group-hover:opacity-100 transition-opacity">
                  →
                </span>
              </button>
            ))}
          </div>
        </section>

        {/* Still Missing */}
        {recipe.ingredients.filter((ing) => ing.status === "missing").length > 0 &&
          remix.substitutions.main.length === 0 &&
          remix.substitutions.seasoning.length === 0 && (
            <section className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 mb-8">
              <h3 className="font-semibold text-gray-900 mb-2">⚠ Shopping Needed</h3>
              <p className="text-gray-700 mb-3">You're still missing some ingredients:</p>
              <ul className="list-disc list-inside space-y-1">
                {recipe.ingredients
                  .filter((ing) => ing.status === "missing")
                  .map((ing, idx) => (
                    <li key={idx} className="text-gray-700 flex items-center justify-between gap-2">
                      <span>{ing.name}</span>
                      <button
                        onClick={() => void applyInventoryUpdate(addIngredientToInventory(inventory, ing.name))}
                        className="px-2.5 py-1 rounded text-xs bg-green-100 text-green-700 hover:bg-green-200"
                      >
                        I have this
                      </button>
                    </li>
                  ))}
              </ul>
            </section>
          )}

        {/* Action Buttons */}
        <div className="grid sm:grid-cols-3 gap-3">
          <button
            onClick={handleCopy}
            className="flex items-center justify-center gap-2 py-3 bg-white border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
          >
            <Copy className="size-4" />
            Copy recipe
          </button>
          <button
            onClick={handleSave}
            className="flex items-center justify-center gap-2 py-3 bg-white border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
          >
            <Save className="size-4" />
            Save
          </button>
          <button
            onClick={() => navigate("/results")}
            className="flex items-center justify-center gap-2 py-3 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors"
          >
            <RefreshCw className="size-4" />
            Try another
          </button>
        </div>
      </main>
    </div>
  );
}