import { useNavigate, useParams } from "react-router";
import { ArrowLeft, ChevronRight } from "lucide-react";
import type { RecipeDetailResponse, RemixResponse } from "../../api/client";
import { StartFromHomeFallback } from "../components/StartFromHomeFallback";
import { normalizeStepList, getFallbackTip } from "../lib/steps";

export default function RecipeStepDetail() {
  const navigate = useNavigate();
  const { id, stepIndex } = useParams<{ id: string; stepIndex: string }>();

  let recipe: RecipeDetailResponse | null = null;
  let remix: RemixResponse | null = null;

  try {
    recipe = JSON.parse(
      sessionStorage.getItem("recipeDetail") || localStorage.getItem("recipeDetail") || "null"
    ) as RecipeDetailResponse | null;
    remix = JSON.parse(
      sessionStorage.getItem("finalRemix") || localStorage.getItem("finalRemix") || "null"
    ) as RemixResponse | null;
  } catch {
    recipe = null;
    remix = null;
  }

  const stepIdx = parseInt(stepIndex || "0");
  const steps = normalizeStepList(remix?.edited_steps, recipe?.steps || []);
  const step = steps[stepIdx];
  const rawTip = (remix?.step_tips?.[stepIdx] ?? "").trim();
  const tip = rawTip || getFallbackTip(step);

  if (!recipe || !remix || recipe.id !== id || (remix.recipe_id && remix.recipe_id !== id) || !step) {
    return <StartFromHomeFallback title="Step not found" />;
  }

  const totalSteps = steps.length;
  const hasNext = stepIdx < totalSteps - 1;
  const hasPrev = stepIdx > 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/final/${recipe.id}`)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="size-5 text-gray-700" />
            </button>
            <div className="flex-1">
              <h1 className="text-xl font-semibold text-gray-900">{recipe.title}</h1>
              <p className="text-sm text-gray-600">
                Step {stepIdx + 1} of {totalSteps}
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {/* Step Progress */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-2">
            {steps.map((_, idx) => (
              <div
                key={idx}
                className={`h-2 flex-1 rounded-full transition-colors ${
                  idx === stepIdx
                    ? "bg-orange-600"
                    : idx < stepIdx
                    ? "bg-green-600"
                    : "bg-gray-200"
                }`}
              />
            ))}
          </div>
        </div>

        {/* Step Title */}
        <section className="mb-8">
          <div className="flex items-center justify-center mb-4">
            <span className="w-16 h-16 bg-orange-600 text-white rounded-full flex items-center justify-center font-bold text-2xl">
              {stepIdx + 1}
            </span>
          </div>
          <h2 className="text-3xl font-bold text-gray-900 text-center mb-2">
            Step {stepIdx + 1}
          </h2>
          <p className="text-lg text-gray-600 text-center">{step}</p>
        </section>

        {/* Chef Tips */}
        {tip && (
          <section className="bg-green-50 border border-green-200 rounded-lg p-6 mb-6">
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <span className="text-green-600">💡</span>
              Chef Tips
            </h3>
            <p className="text-gray-700 leading-relaxed">{tip}</p>
          </section>
        )}

        {/* Navigation Buttons */}
        <div className="flex gap-3">
          {hasPrev && (
            <button
              onClick={() => navigate(`/recipe/${recipe.id}/step/${stepIdx - 1}`)}
              className="flex-1 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
            >
              ← Previous Step
            </button>
          )}
          {hasNext ? (
            <button
              onClick={() => navigate(`/recipe/${recipe.id}/step/${stepIdx + 1}`)}
              className="flex-1 py-3 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors flex items-center justify-center gap-2"
            >
              Next Step
              <ChevronRight className="size-4" />
            </button>
          ) : (
            <button
              onClick={() => navigate(`/final/${recipe.id}`)}
              className="flex-1 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
            >
              Back to Recipe
            </button>
          )}
        </div>

        {/* Quick Navigation to All Steps */}
        <div className="mt-8 border-t pt-6">
          <h3 className="font-semibold text-gray-900 mb-4">All Steps</h3>
          <div className="grid gap-2">
            {steps.map((s, idx) => (
              <button
                key={idx}
                onClick={() => navigate(`/recipe/${recipe.id}/step/${idx}`)}
                className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                  idx === stepIdx
                    ? "bg-orange-50 border-orange-300"
                    : "bg-white border-gray-200 hover:border-gray-300"
                }`}
              >
                <span
                  className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center font-semibold ${
                    idx === stepIdx
                      ? "bg-orange-600 text-white"
                      : idx < stepIdx
                      ? "bg-green-600 text-white"
                      : "bg-gray-200 text-gray-600"
                  }`}
                >
                  {idx + 1}
                </span>
                <span className="text-left text-gray-700 flex-1">Step {idx + 1}</span>
                {idx === stepIdx && (
                  <span className="text-xs text-orange-600 font-medium">Current</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}