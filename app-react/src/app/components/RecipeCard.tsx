import { Clock, ChefHat } from "lucide-react";

interface RecipeCardProps {
  id: string;
  title: string;
  time: string;
  style: string;
  difficulty: string;
  feasibility: "cook-now" | "needs-sub";
  coverageRatio: string;
  missingPreview: string[];
  onClick: () => void;
  onMarkHave?: (ingredient: string) => void;
}

export function RecipeCard({
  title,
  time,
  style,
  difficulty,
  feasibility,
  coverageRatio,
  missingPreview,
  onClick,
  onMarkHave,
}: RecipeCardProps) {
  return (
    <div
      onClick={onClick}
      className="bg-white border border-gray-200 rounded-xl p-6 hover:shadow-lg transition-shadow cursor-pointer"
    >
      {/* Title */}
      <h3 className="text-xl font-semibold text-gray-900 mb-3">{title}</h3>

      {/* Tags Row */}
      <div className="flex flex-wrap gap-2 mb-4">
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm">
          <Clock className="size-3" />
          {time}
        </span>
        <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm">
          {style}
        </span>
        <span className="px-3 py-1 bg-green-50 text-green-700 rounded-full text-sm">
          {difficulty}
        </span>
      </div>

      {/* Feasibility Badge */}
      <div className="mb-3">
        {feasibility === "cook-now" ? (
          <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-green-100 text-green-800 border border-green-300 rounded-full text-sm font-medium">
            ✓ Cook-now
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-3 py-1.5 bg-orange-100 text-orange-800 border border-orange-300 rounded-full text-sm font-medium">
            ⚠ Needs substitutions
          </span>
        )}
      </div>

      {/* Coverage Bar */}
      <div className="mb-2">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-gray-600">Ingredient coverage</span>
          <span className="font-medium text-gray-900">{coverageRatio}</span>
        </div>
        <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 rounded-full"
            style={{
              width: `${(parseInt(coverageRatio.split("/")[0]) / parseInt(coverageRatio.split("/")[1])) * 100}%`,
            }}
          />
        </div>
      </div>

      {/* Missing Preview */}
      {missingPreview.length > 0 && (
        <div className="text-sm text-gray-600 mb-4">
          <p className="mb-2">
            <span className="font-medium">Missing:</span> {missingPreview.join(", ")}
          </p>
          {onMarkHave && (
            <div className="flex flex-wrap gap-2">
              {missingPreview.map((ingredient) => (
                <button
                  key={`${title}-${ingredient}`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onMarkHave(ingredient);
                  }}
                  className="px-2 py-1 text-xs rounded-full border border-orange-300 text-orange-700 bg-orange-50 hover:bg-orange-100"
                >
                  I have this: {ingredient}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* CTA */}
      <button className="w-full py-2.5 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors">
        View & Remix
      </button>
    </div>
  );
}