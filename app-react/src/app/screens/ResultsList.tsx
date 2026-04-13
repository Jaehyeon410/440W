import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { ArrowLeft, Filter } from "lucide-react";
import { RecipeCard } from "../components/RecipeCard";
import { toast } from "sonner";
import { InventoryInlineEditor } from "../components/InventoryInlineEditor";
import {
  recommend,
  type DietaryPayload,
  type PreferencesPayload,
  type RecommendRecipe,
} from "../../api/client";
import {
  addIngredientToInventory,
  getStoredInventory,
  saveStoredInventory,
} from "../lib/inventory";

function getStoredPreferences(): PreferencesPayload {
  try {
    const parsed = JSON.parse(localStorage.getItem("preferencesPayload") || "null") as
      | PreferencesPayload
      | null;
    if (parsed && typeof parsed.time_limit === "number") {
      return parsed;
    }
  } catch {
    // ignore and fallback
  }

  return {
    time_limit: 30,
    spicy: false,
    lighter: false,
    cuisine: "Any",
  };
}

function getStoredDietary(): DietaryPayload | undefined {
  try {
    const parsed = JSON.parse(localStorage.getItem("dietaryPayload") || "null") as
      | DietaryPayload
      | null;
    if (parsed && (typeof parsed.dairy_free === "boolean" || typeof parsed.gluten_free === "boolean")) {
      return {
        dairy_free: Boolean(parsed.dairy_free),
        gluten_free: Boolean(parsed.gluten_free),
      };
    }
  } catch {
    // ignore
  }
  return undefined;
}

function getStoredAllergies(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem("allergies") || "[]") as string[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export default function ResultsList() {
  const navigate = useNavigate();
  const [cookNowOnly, setCookNowOnly] = useState(false);
  const [sortBy, setSortBy] = useState("best-match");
  const [isUpdatingInventory, setIsUpdatingInventory] = useState(false);
  const [inventory, setInventory] = useState<string[]>(getStoredInventory());

  const [recipes, setRecipes] = useState<RecommendRecipe[]>(() => {
    const raw = sessionStorage.getItem("recommendedRecipes");
    if (!raw) {
      return [];
    }
    try {
      return JSON.parse(raw) as RecommendRecipe[];
    } catch {
      return [];
    }
  });

  const allMissingCandidates = useMemo(() => {
    const allMissing = recipes.flatMap((recipe) => [
      ...recipe.missing_main,
      ...recipe.missing_seasoning,
      ...(recipe.missing_other || []),
    ]);
    return [...new Set(allMissing)];
  }, [recipes]);

  const refreshRecommendations = async (nextInventory: string[]) => {
    setIsUpdatingInventory(true);
    try {
      const preferences = getStoredPreferences();
      const dietary = getStoredDietary();
      const allergies = getStoredAllergies();

      const response = await recommend({
        ingredients: nextInventory,
        preferences,
        dietary,
        allergies,
      });

      saveStoredInventory(nextInventory);
      sessionStorage.setItem("recommendedRecipes", JSON.stringify(response.recipes));
      setInventory(nextInventory);
      setRecipes(response.recipes);
      toast.success("Inventory updated and recommendations refreshed");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to refresh recommendations");
    } finally {
      setIsUpdatingInventory(false);
    }
  };

  const filteredRecipes = recipes.filter((recipe) => {
    if (cookNowOnly) {
      return recipe.cook_now;
    }
    return true;
  });

  const sortedRecipes = [...filteredRecipes].sort((a, b) => {
    if (sortBy === "time") {
      return a.time_minutes - b.time_minutes;
    }
    if (sortBy === "coverage") {
      return b.match_percent - a.match_percent;
    }
    return b.match_percent - a.match_percent;
  });

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/")}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="size-5 text-gray-700" />
            </button>
            <h1 className="text-xl font-semibold text-gray-900">Recipe Ideas</h1>
          </div>
        </div>
      </header>

      {/* Filter Row */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={cookNowOnly}
                onChange={(e) => setCookNowOnly(e.target.checked)}
                className="w-4 h-4 text-orange-600 border-gray-300 rounded focus:ring-orange-500"
              />
              <span className="text-sm font-medium text-gray-700">Cook-now only</span>
            </label>

            <div className="flex items-center gap-2">
              <Filter className="size-4 text-gray-500" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="text-sm border-none bg-transparent font-medium text-gray-700 focus:outline-none cursor-pointer"
              >
                <option value="best-match">Sort: Best match</option>
                <option value="time">Sort: Shortest time</option>
                <option value="coverage">Sort: Best coverage</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Results */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        <InventoryInlineEditor
          ingredients={inventory}
          missingCandidates={allMissingCandidates}
          isSaving={isUpdatingInventory}
          onApply={refreshRecommendations}
        />

        {filteredRecipes.length > 0 ? (
          <>
            <p className="text-sm text-gray-600 mb-6">
              Found {filteredRecipes.length} recipe{filteredRecipes.length !== 1 ? "s" : ""}
            </p>
            <div className="grid gap-6">
              {sortedRecipes.map((recipe) => (
                <RecipeCard
                  key={recipe.id}
                  id={recipe.id}
                  title={recipe.title}
                  time={`${recipe.time_minutes || 0} min`}
                  style={JSON.parse(localStorage.getItem("preferencesPayload") || "{}").cuisine || "Custom"}
                  difficulty="Easy"
                  feasibility={recipe.cook_now ? "cook-now" : "needs-sub"}
                  coverageRatio={`${recipe.match_percent}/100`}
                  missingPreview={[
                    ...recipe.missing_main,
                    ...recipe.missing_seasoning,
                    ...(recipe.missing_other || []),
                  ].slice(0, 3)}
                  onMarkHave={(ingredient) => {
                    void refreshRecommendations(addIngredientToInventory(inventory, ingredient));
                  }}
                  onClick={() => navigate(`/recipe/${recipe.id}`)}
                />
              ))}
            </div>
          </>
        ) : (
          <div className="text-center py-16">
            <div className="inline-flex items-center justify-center w-24 h-24 bg-gray-100 rounded-full mb-4">
              <Filter className="size-12 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              No recipes found
            </h3>
            <p className="text-gray-600 mb-6">
              Try removing one preference or adding more ingredients.
            </p>
            <button
              onClick={() => navigate("/")}
              className="px-6 py-2.5 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors"
            >
              Back to search
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
