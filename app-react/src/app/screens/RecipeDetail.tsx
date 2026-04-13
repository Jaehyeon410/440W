import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ArrowLeft, Check, X } from "lucide-react";
import { Badge } from "../components/Badge";
import * as Dialog from "@radix-ui/react-dialog";
import { toast } from "sonner";
import {
  getRecipeDetail,
  getSubstitutions,
  remixRecipe,
  type OtherOptionsEntry,
  type RecipeDetailResponse,
  type SubstitutionOption,
  type SubstitutionsResponse,
} from "../../api/client";
import { InventoryInlineEditor } from "../components/InventoryInlineEditor";
import { addIngredientToInventory, getStoredInventory, saveStoredInventory } from "../lib/inventory";

function getStoredPreferences() {
  try {
    return JSON.parse(localStorage.getItem("preferencesPayload") || "null");
  } catch {
    return null;
  }
}

function getStoredDietary() {
  try {
    return JSON.parse(localStorage.getItem("dietaryPayload") || "null");
  } catch {
    return null;
  }
}

function getStoredAllergies(): string[] {
  try {
    const parsed = JSON.parse(localStorage.getItem("allergies") || "[]") as string[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function normalizeLookupKey(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function getMainOptionsByMissingItem(substitutions: SubstitutionsResponse | null, item: string): SubstitutionOption[] {
  if (!substitutions) {
    return [];
  }
  const exact = substitutions.main_options[item];
  if (exact) {
    return exact;
  }
  const target = normalizeLookupKey(item);
  const matchedKey = Object.keys(substitutions.main_options).find(
    (key) => normalizeLookupKey(key) === target
  );
  return matchedKey ? substitutions.main_options[matchedKey] || [] : [];
}

function getSeasoningOptionsByMissingItem(
  substitutions: SubstitutionsResponse | null,
  item: string
): { similar: SubstitutionOption[]; different: SubstitutionOption[] } {
  if (!substitutions) {
    return { similar: [], different: [] };
  }

  const exact = substitutions.seasoning_options[item];
  if (exact) {
    return exact;
  }

  const target = normalizeLookupKey(item);
  const matchedKey = Object.keys(substitutions.seasoning_options).find(
    (key) => normalizeLookupKey(key) === target
  );
  return matchedKey
    ? substitutions.seasoning_options[matchedKey] || { similar: [], different: [] }
    : { similar: [], different: [] };
}

export default function RecipeDetail() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [activeTab, setActiveTab] = useState<"overview" | "remix" | "notes">("overview");
  const [recipe, setRecipe] = useState<RecipeDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubLoading, setIsSubLoading] = useState(false);
  const [isFinalLoading, setIsFinalLoading] = useState(false);
  const [isInventoryUpdating, setIsInventoryUpdating] = useState(false);
  const [substitutions, setSubstitutions] = useState<SubstitutionsResponse | null>(null);

  const [selectedMainSub, setSelectedMainSub] = useState<Record<string, string>>({});
  const [selectedSeasoningSub, setSelectedSeasoningSub] = useState<Record<string, string>>({});
  const [showSubModal, setShowSubModal] = useState<string | null>(null);

  const [userIngredients, setUserIngredients] = useState<string[]>(getStoredInventory());

  useEffect(() => {
    if (!id) {
      setIsLoading(false);
      return;
    }

    const loadRecipe = async () => {
      setIsLoading(true);
      try {
        const detail = await getRecipeDetail(id, userIngredients);
        setRecipe(detail);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load recipe detail");
      } finally {
        setIsLoading(false);
      }
    };

    loadRecipe();
  }, [id]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-600">Loading recipe...</p>
      </div>
    );
  }

  if (!recipe || !id) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Recipe not found</h2>
          <button
            onClick={() => navigate("/results")}
            className="text-orange-600 hover:text-orange-700"
          >
            Back to results
          </button>
        </div>
      </div>
    );
  }

  const openSubstitutions = async () => {
    setIsSubLoading(true);
    try {
      const preferences = getStoredPreferences();
      const dietary = getStoredDietary();
      const allergies = getStoredAllergies();

      const response = await getSubstitutions({
        recipe_id: recipe.id,
        user_ingredients: userIngredients,
        missing_main: recipe.missing_main,
        missing_seasoning: recipe.missing_seasoning,
        missing_other: recipe.missing_other,
        preferences: preferences || undefined,
        dietary: dietary || undefined,
        allergies,
      });
      setSubstitutions(response);
      toast.success("Substitutions loaded");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load substitutions");
    } finally {
      setIsSubLoading(false);
    }
  };

  const applyInventoryUpdate = async (nextIngredients: string[]) => {
    if (!id || !recipe) {
      return;
    }

    setIsInventoryUpdating(true);
    try {
      const normalizedInventory = saveStoredInventory(nextIngredients);
      setUserIngredients(normalizedInventory);

      const refreshedDetail = await getRecipeDetail(id, normalizedInventory);
      setRecipe(refreshedDetail);
      setSelectedMainSub({});
      setSelectedSeasoningSub({});

      const preferences = getStoredPreferences();
      const dietary = getStoredDietary();
      const allergies = getStoredAllergies();

      const refreshedSubstitutions = await getSubstitutions({
        recipe_id: refreshedDetail.id,
        user_ingredients: normalizedInventory,
        missing_main: refreshedDetail.missing_main,
        missing_seasoning: refreshedDetail.missing_seasoning,
        missing_other: refreshedDetail.missing_other,
        preferences: preferences || undefined,
        dietary: dietary || undefined,
        allergies,
      });

      setSubstitutions(refreshedSubstitutions);
      toast.success("Inventory updated and substitutions recalculated");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update inventory");
    } finally {
      setIsInventoryUpdating(false);
    }
  };

  const missingCandidates = [
    ...recipe.missing_main,
    ...recipe.missing_seasoning,
    ...recipe.missing_other,
  ];

  const handleGenerateFinal = async () => {
    setIsFinalLoading(true);
    try {
      const preferences = JSON.parse(localStorage.getItem("preferencesPayload") || "null") || {
        time_limit: 30,
        spicy: false,
        lighter: false,
        cuisine: "Any",
      };

      const response = await remixRecipe({
        recipe_id: recipe.id,
        user_ingredients: userIngredients,
        selected_main_subs: selectedMainSub,
        selected_seasoning_subs: selectedSeasoningSub,
        preferences,
      });

      sessionStorage.setItem("finalRemix", JSON.stringify(response));
      sessionStorage.setItem("recipeDetail", JSON.stringify(recipe));
      localStorage.setItem("finalRemix", JSON.stringify(response));
      localStorage.setItem("recipeDetail", JSON.stringify(recipe));
      navigate(`/final/${recipe.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to generate final recipe");
    } finally {
      setIsFinalLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-20">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/results")}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="size-5 text-gray-700" />
            </button>
            <h1 className="text-xl font-semibold text-gray-900 truncate">{recipe.title}</h1>
          </div>
        </div>
      </header>

      {/* Summary */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-6 py-6">
          <div className="flex items-center gap-4 mb-3">
            <span className="text-sm text-gray-600">From recommendation</span>
            <span className="text-sm text-gray-600">•</span>
            <span className="text-sm text-gray-600">Real API data</span>
            <span className="text-sm text-gray-600">•</span>
            <span className="text-sm text-gray-600">Dynamic</span>
          </div>
          <div>
            {recipe.missing_main.length + recipe.missing_seasoning.length + recipe.missing_other.length <= 1 ? (
              <Badge variant="cook-now">✓ Cook-now</Badge>
            ) : (
              <Badge variant="needs-sub">⚠ Needs substitutions</Badge>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-6">
          <div className="flex gap-8">
            {["overview", "remix", "notes"].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as typeof activeTab)}
                className={`py-4 border-b-2 font-medium text-sm capitalize transition-colors ${
                  activeTab === tab
                    ? "border-orange-600 text-orange-600"
                    : "border-transparent text-gray-600 hover:text-gray-900"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab Content */}
      <main className="max-w-4xl mx-auto px-6 py-8">
        <InventoryInlineEditor
          ingredients={userIngredients}
          missingCandidates={missingCandidates}
          isSaving={isInventoryUpdating}
          onApply={applyInventoryUpdate}
        />

        {activeTab === "overview" && (
          <div>
            {/* Ingredients */}
            <section className="mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Ingredients</h2>
              <div className="bg-white rounded-lg border p-4">
                {recipe.ingredients.map((ing, idx) => (
                  <div key={idx} className="flex items-center gap-3 py-2">
                    {ing.status === "available" ? (
                      <Check className="size-5 text-green-600 flex-shrink-0" />
                    ) : ing.status === "missing" ? (
                      <X className="size-5 text-red-600 flex-shrink-0" />
                    ) : (
                      <span className="size-5 text-gray-400 flex-shrink-0">?</span>
                    )}
                    <span className={ing.status === "missing" ? "text-gray-400" : "text-gray-900"}>
                      {ing.name}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            {/* Steps Preview */}
            <section className="mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Steps (Preview)</h2>
              <div className="bg-white rounded-lg border p-4">
                {recipe.steps.slice(0, 3).map((step, idx) => (
                  <div key={idx} className="flex gap-3 mb-3 last:mb-0">
                    <span className="flex-shrink-0 w-6 h-6 bg-orange-100 text-orange-700 rounded-full flex items-center justify-center text-sm font-medium">
                      {idx + 1}
                    </span>
                    <p className="text-gray-700 pt-0.5">{step}</p>
                  </div>
                ))}
                <p className="text-sm text-gray-500 mt-4">+ {Math.max(recipe.steps.length - 3, 0)} more steps</p>
              </div>
            </section>

            <button
              onClick={() => setActiveTab("remix")}
              className="w-full py-3 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors"
            >
              Open Remix
            </button>
          </div>
        )}

        {activeTab === "remix" && (
          <div>
            {/* Missing Check Summary */}
            {(recipe.missing_main.length > 0 || recipe.missing_seasoning.length > 0 || recipe.missing_other.length > 0) && (
              <section className="mb-8 p-6 bg-orange-50 border border-orange-200 rounded-lg">
                <h2 className="font-semibold text-gray-900 mb-3">
                  You can cook this with substitutions.
                </h2>
                {recipe.missing_main.length > 0 && (
                  <p className="text-sm text-gray-700 mb-2">
                    <span className="font-medium">Missing Main Ingredients:</span> {recipe.missing_main.join(", ")}
                  </p>
                )}
                {recipe.missing_seasoning.length > 0 && (
                  <p className="text-sm text-gray-700 mb-2">
                    <span className="font-medium">Missing Seasonings:</span> {recipe.missing_seasoning.join(", ")}
                  </p>
                )}
                {recipe.missing_other.length > 0 && (
                  <p className="text-sm text-gray-700">
                    <span className="font-medium">Missing Others:</span> {recipe.missing_other.join(", ")}
                  </p>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  {missingCandidates.slice(0, 8).map((item) => (
                    <button
                      key={`missing-quick-${item}`}
                      onClick={() => void applyInventoryUpdate(addIngredientToInventory(userIngredients, item))}
                      className="px-2.5 py-1.5 rounded-full text-xs border border-orange-300 text-orange-700 bg-orange-50 hover:bg-orange-100"
                    >
                      I have this: {item}
                    </button>
                  ))}
                </div>
              </section>
            )}

            <section className="mb-8">
              <button
                onClick={openSubstitutions}
                disabled={isSubLoading}
                className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:bg-gray-300"
              >
                {isSubLoading ? "Finding substitutes..." : "Find substitutes"}
              </button>
            </section>

            {/* Main Ingredient Replacement */}
            {recipe.missing_main.length > 0 && (
              <section className="mb-8">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  Main Ingredient Replacement
                </h2>
                {recipe.missing_main.map((item) => (
                  <div key={item} className="mb-4">
                    <div className="bg-white rounded-lg border p-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-medium text-gray-900">Missing: {item}</span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => void applyInventoryUpdate(addIngredientToInventory(userIngredients, item))}
                            className="px-3 py-2 bg-green-100 text-green-700 rounded-lg text-sm font-medium hover:bg-green-200 transition-colors"
                          >
                            I have this
                          </button>
                          <button
                            onClick={() => setShowSubModal(item)}
                            className="px-4 py-2 bg-orange-100 text-orange-700 rounded-lg text-sm font-medium hover:bg-orange-200 transition-colors"
                          >
                            Choose replacement
                          </button>
                        </div>
                      </div>

                      {selectedMainSub[item] && (
                        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                          <p className="font-medium text-green-900 mb-2">
                            Selected: {selectedMainSub[item]}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Modal for Main Substitution */}
                    <Dialog.Root open={showSubModal === item} onOpenChange={(open) => !open && setShowSubModal(null)}>
                      <Dialog.Portal>
                        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40" />
                        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[80vh] overflow-y-auto z-50 p-6">
                          <Dialog.Title className="text-xl font-semibold text-gray-900 mb-2">
                            Replace {item}
                          </Dialog.Title>
                          <Dialog.Description className="text-sm text-gray-600 mb-6">
                            Pick one option (Top 3)
                          </Dialog.Description>

                          <div className="space-y-4">
                            {getMainOptionsByMissingItem(substitutions, item).map((option) => (
                              <div key={option.to} className="border rounded-lg p-4 hover:border-orange-500 transition-colors">
                                <h3 className="font-semibold text-gray-900 mb-2">{option.to}</h3>
                                <p className="text-sm text-gray-700 mb-1">
                                  <span className="font-medium">Impact:</span> {option.reason}
                                </p>
                                <button
                                  onClick={() => {
                                    setSelectedMainSub({ ...selectedMainSub, [item]: option.to });
                                    setShowSubModal(null);
                                  }}
                                  className="w-full py-2 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors"
                                >
                                  Select
                                </button>
                              </div>
                            ))}
                            {getMainOptionsByMissingItem(substitutions, item).length === 0 && (
                              <div className="border rounded-lg p-4 bg-gray-50">
                                <p className="text-sm text-gray-700">
                                  No replacement candidates were returned for this ingredient yet.
                                </p>
                              </div>
                            )}
                          </div>

                          <button
                            onClick={() => setShowSubModal(null)}
                            className="w-full mt-4 py-2 text-gray-600 hover:text-gray-900 font-medium"
                          >
                            Skip replacement
                          </button>
                        </Dialog.Content>
                      </Dialog.Portal>
                    </Dialog.Root>
                  </div>
                ))}
              </section>
            )}

            {/* Seasoning Options */}
            {recipe.missing_seasoning.length > 0 && (
              <section className="mb-8">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Seasoning Options</h2>
                {recipe.missing_seasoning.map((item) => {
                  const seasoningOptions = getSeasoningOptionsByMissingItem(substitutions, item);
                  const similar = seasoningOptions.similar || [];
                  const different = seasoningOptions.different || [];

                  return (
                    <div key={item} className="mb-6">
                      <h3 className="font-medium text-gray-900 mb-4">Missing: {item}</h3>
                      <button
                        onClick={() => void applyInventoryUpdate(addIngredientToInventory(userIngredients, item))}
                        className="mb-3 px-3 py-2 bg-green-100 text-green-700 rounded-lg text-sm font-medium hover:bg-green-200 transition-colors"
                      >
                        I have this seasoning
                      </button>

                      {/* Similar taste */}
                      {similar.length > 0 && (
                        <div className="mb-4">
                          <h4 className="text-sm font-medium text-gray-700 mb-3">Similar taste (Top 2)</h4>
                          <div className="grid gap-3">
                            {similar.slice(0, 2).map((option) => (
                              <SeasoningOptionCard
                                key={option.to}
                                option={option}
                                selected={selectedSeasoningSub[item] === option.to}
                                onSelect={() => setSelectedSeasoningSub({ ...selectedSeasoningSub, [item]: option.to })}
                              />
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Different but works */}
                      {different.length > 0 && (
                        <div>
                          <h4 className="text-sm font-medium text-gray-700 mb-3">Different but works (Top 2)</h4>
                          <div className="grid gap-3">
                            {different.slice(0, 2).map((option) => (
                              <SeasoningOptionCard
                                key={option.to}
                                option={option}
                                selected={selectedSeasoningSub[item] === option.to}
                                onSelect={() => setSelectedSeasoningSub({ ...selectedSeasoningSub, [item]: option.to })}
                              />
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </section>
            )}

            {/* Generate Final Recipe */}
            <div className="flex gap-3">
              <button
                onClick={() => navigate("/results")}
                className="flex-1 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
              >
                Back to list
              </button>
              <button
                onClick={handleGenerateFinal}
                disabled={isFinalLoading}
                className="flex-1 py-3 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors"
              >
                {isFinalLoading ? "Generating..." : "Generate Final Steps"}
              </button>
            </div>

            {substitutions && Object.keys(substitutions.other_options || {}).length > 0 && (
              <section className="mt-6 bg-white border rounded-lg p-4">
                <h3 className="font-semibold text-gray-900 mb-3">Other ingredient options</h3>
                <div className="space-y-3">
                  {Object.entries(substitutions.other_options).map(([missingItem, entry]) => (
                    <OtherOptionCard key={missingItem} missingItem={missingItem} entry={entry} />
                  ))}
                </div>
              </section>
            )}

            {substitutions && Object.keys(substitutions.other_notes).length > 0 && (
              <section className="mt-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <h3 className="font-semibold text-gray-900 mb-2">Other missing notes</h3>
                {Object.entries(substitutions.other_notes).map(([key, note]) => (
                  <p key={key} className="text-sm text-gray-700">
                    <span className="font-medium">{key}:</span> {note}
                  </p>
                ))}
              </section>
            )}
          </div>
        )}

        {activeTab === "notes" && (
          <div>
            <section className="bg-white rounded-lg border p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Substitution Disclaimer</h2>
              <p className="text-gray-700 mb-4">
                The substitutions suggested are based on common culinary practices and may alter the final taste, texture,
                and appearance of the dish. Results may vary based on ingredient quality and cooking technique.
              </p>
              <p className="text-gray-700 mb-4">
                Always taste and adjust seasonings as needed during cooking.
              </p>

              <h3 className="font-semibold text-gray-900 mb-2 mt-6">Important Note</h3>
              <p className="text-sm text-gray-600">
                If you have food allergies or dietary restrictions, always verify that substitutions are safe for your needs.
                When in doubt, consult with a healthcare professional.
              </p>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

interface SeasoningOptionCardProps {
  option: SubstitutionOption;
  selected: boolean;
  onSelect: () => void;
}

function SeasoningOptionCard({ option, selected, onSelect }: SeasoningOptionCardProps) {
  return (
    <div
      className={`border rounded-lg p-4 cursor-pointer transition-all ${
        selected ? "border-orange-500 bg-orange-50" : "border-gray-200 hover:border-orange-300"
      }`}
      onClick={onSelect}
    >
      <div className="flex items-start justify-between mb-3">
        <h4 className="font-semibold text-gray-900">{option.to}</h4>
      </div>
      <p className="text-sm text-gray-700 mb-2">
        <span className="font-medium">Reason:</span> {option.reason}
      </p>
      <button
        className={`w-full py-2 rounded-lg font-medium transition-colors ${
          selected
            ? "bg-orange-600 text-white"
            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
        }`}
      >
        {selected ? "Selected" : "Use this"}
      </button>
    </div>
  );
}

function OtherOptionCard({ missingItem, entry }: { missingItem: string; entry: OtherOptionsEntry }) {
  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-semibold text-gray-900">{missingItem}</h4>
        <span className="text-xs font-medium uppercase tracking-wide px-2 py-1 rounded bg-gray-100 text-gray-700">
          {entry.category}
        </span>
      </div>

      {entry.suggested.length > 0 ? (
        <div className="space-y-2">
          {entry.suggested.map((option) => (
            <div key={option.to} className="p-3 border border-gray-200 rounded-md">
              <p className="text-sm font-medium text-gray-900">{option.to}</p>
              <p className="text-xs text-gray-700">{option.reason}</p>
              <p className="text-xs text-gray-500 mt-1">Confidence: {Math.round(option.confidence * 100)}%</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-3 bg-gray-50 border border-gray-200 rounded-md">
          <p className="text-sm text-gray-700 mb-1">No pantry substitute found.</p>
          <p className="text-xs text-gray-500">Fallback: {entry.fallback_actions.join(", ")}</p>
        </div>
      )}
    </div>
  );
}