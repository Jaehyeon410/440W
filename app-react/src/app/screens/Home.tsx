import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { ChefHat, Refrigerator, Settings } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "../components/ui/dialog";
import { Chip } from "../components/Chip";
import { toast } from "sonner";
import { recommend, type DietaryPayload, type PreferencesPayload } from "../../api/client";
import { groupIngredients } from "../lib/displayGroups";

const quickIngredients = [
  "chicken", "beef", "pork", "eggs", "milk", "butter", "olive oil",
  "garlic", "onion", "tomato", "pasta", "rice", "cheese", "lemon",
  "soy sauce", "salt", "pepper", "basil", "spinach"
];

interface Preferences {
  time: string;
  style: string;
  taste: string[];
  dietary: string[];
}

function mapTimeLimit(timeLabel: string): number {
  if (timeLabel === "Under 15 min") {
    return 15;
  }
  if (timeLabel === "Under 30 min") {
    return 30;
  }
  return 60;
}

function buildPreferencesPayload(preferences: Preferences): PreferencesPayload {
  return {
    time_limit: mapTimeLimit(preferences.time),
    spicy: preferences.taste.includes("Spicy"),
    lighter: preferences.taste.includes("Lighter"),
    cuisine: preferences.style || "Any",
  };
}

function buildDietaryPayload(preferences: Preferences): DietaryPayload {
  return {
    dairy_free: preferences.dietary.includes("Dairy-free"),
    gluten_free: preferences.dietary.includes("Gluten-free"),
  };
}

export default function Home() {
  const navigate = useNavigate();
  const [fridgeIngredients, setFridgeIngredients] = useState<string[]>([]);
  const [showIngredientsModal, setShowIngredientsModal] = useState(false);
  const [showPreferencesModal, setShowPreferencesModal] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  // Load ingredients from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("fridgeIngredients");
    if (saved) {
      setFridgeIngredients(JSON.parse(saved));
    }
  }, []);

  // Save ingredients to localStorage
  const saveIngredients = (ingredients: string[]) => {
    setFridgeIngredients(ingredients);
    localStorage.setItem("fridgeIngredients", JSON.stringify(ingredients));
  };

  const handleStartCooking = () => {
    if (fridgeIngredients.length >= 3) {
      setShowPreferencesModal(true);
    }
  };

  const categorizedIngredients = groupIngredients(fridgeIngredients);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-orange-50">
      {/* Header */}
      <header className="bg-white border-b shadow-sm">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-500 rounded-lg">
                <ChefHat className="size-6 text-white" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900">Fridge Remix</h1>
            </div>
            <button
              onClick={() => setShowIngredientsModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              <Settings className="size-4" />
              My Inventory
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-6 py-12">
        {/* Fridge Visualization */}
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-6">
            <Refrigerator className="size-8 text-blue-600" />
            <h2 className="text-2xl font-bold text-gray-900">My Fridge</h2>
          </div>

          <div className="bg-gradient-to-b from-blue-100 to-blue-50 rounded-2xl border-4 border-blue-300 p-8 min-h-[400px]">
            {fridgeIngredients.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-12">
                <Refrigerator className="size-24 text-blue-300 mb-4" />
                <p className="text-gray-600 text-lg mb-4">Your fridge is empty</p>
                <button
                  onClick={() => setShowIngredientsModal(true)}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
                >
                  Add Ingredients
                </button>
              </div>
            ) : (
              <div className="space-y-6">
                {categorizedIngredients.map(({ group, items }) => (
                  <div key={group}>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-bold text-gray-800 uppercase tracking-wide">
                        {group} ({items.length})
                      </h3>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                      {items.map((ingredient, idx) => (
                        <div
                          key={idx}
                          className="bg-white rounded-lg p-2.5 border-2 border-blue-200 shadow-sm hover:shadow-md transition-shadow"
                        >
                          <p className="text-gray-800 text-center text-sm font-medium">{ingredient}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Start Cooking Button */}
        {fridgeIngredients.length > 0 && (
          <div className="text-center">
            <button
              onClick={handleStartCooking}
              disabled={fridgeIngredients.length < 3 || isLoading}
              className="px-12 py-4 bg-orange-600 text-white rounded-xl font-bold text-xl hover:bg-orange-700 transition-colors shadow-lg hover:shadow-xl disabled:bg-gray-300 disabled:cursor-not-allowed disabled:hover:bg-gray-300"
            >
              {isLoading ? "Loading..." : "Get Recipe Ideas"}
            </button>
            {fridgeIngredients.length < 3 && (
              <p className="mt-4 text-gray-600">
                Need at least 3 ingredients to start
              </p>
            )}
          </div>
        )}
      </main>

      {/* Ingredients Management Modal */}
      <IngredientsModal
        open={showIngredientsModal}
        onClose={() => setShowIngredientsModal(false)}
        ingredients={fridgeIngredients}
        onSave={saveIngredients}
      />

      {/* Preferences Modal */}
      <PreferencesModal
        open={showPreferencesModal}
        onClose={() => setShowPreferencesModal(false)}
        ingredients={fridgeIngredients}
        isLoading={isLoading}
        onStart={async (preferences) => {
          setIsLoading(true);
          try {
            const preferencesPayload = buildPreferencesPayload(preferences);
            const dietaryPayload = buildDietaryPayload(preferences);
            const allergies: string[] = [];

            const response = await recommend({
              ingredients: fridgeIngredients,
              preferences: preferencesPayload,
              dietary: dietaryPayload,
              allergies,
            });

            localStorage.setItem("userIngredients", JSON.stringify(fridgeIngredients));
            localStorage.setItem("user_ingredients", JSON.stringify(fridgeIngredients));
            localStorage.setItem("preferencesPayload", JSON.stringify(preferencesPayload));
            localStorage.setItem("dietaryPayload", JSON.stringify(dietaryPayload));
            localStorage.setItem("allergies", JSON.stringify(allergies));
            sessionStorage.setItem("recommendedRecipes", JSON.stringify(response.recipes));

            setShowPreferencesModal(false);
            navigate("/results");
          } catch (error) {
            toast.error(error instanceof Error ? error.message : "Failed to fetch recipe ideas");
          } finally {
            setIsLoading(false);
          }
        }}
      />
    </div>
  );
}

// Ingredients Management Modal Component
interface IngredientsModalProps {
  open: boolean;
  onClose: () => void;
  ingredients: string[];
  onSave: (ingredients: string[]) => void;
}

function IngredientsModal({ open, onClose, ingredients, onSave }: IngredientsModalProps) {
  const [localIngredients, setLocalIngredients] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    if (open) {
      setLocalIngredients([...ingredients]);
      setInputValue("");
      setSearchQuery("");
    }
  }, [open, ingredients]);

  const handleAdd = (ingredient: string) => {
    const trimmed = ingredient.trim().toLowerCase();
    if (trimmed && !localIngredients.includes(trimmed)) {
      setLocalIngredients([...localIngredients, trimmed]);
      setInputValue("");
    }
  };

  const handleRemove = (ingredient: string) => {
    setLocalIngredients(localIngredients.filter(i => i !== ingredient));
  };

  const handleQuickAdd = (ingredient: string) => {
    if (!localIngredients.includes(ingredient)) {
      setLocalIngredients([...localIngredients, ingredient]);
    }
  };

  const handleSave = () => {
    onSave(localIngredients);
    onClose();
  };

  const categorizedLocal = groupIngredients(localIngredients);

  // Filter ingredients based on search query
  const filteredCategorized = categorizedLocal
    .map(({ group, items }) => ({
      group,
      items: items.filter((ingredient) =>
        ingredient.toLowerCase().includes(searchQuery.toLowerCase())
      ),
    }))
    .filter(({ items }) => items.length > 0);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Manage My Inventory</DialogTitle>
          <DialogDescription>
            Add, search, and manage your ingredients
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Add New Ingredient & Search */}
          <div className="space-y-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleAdd(inputValue);
                  }
                }}
                placeholder="Add new ingredient..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={() => handleAdd(inputValue)}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
              >
                Add
              </button>
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search ingredients..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Current Ingredients - Categorized */}
          <div>
            {localIngredients.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-8">No ingredients added yet</p>
            ) : filteredCategorized.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-8">No ingredients match your search</p>
            ) : (
              <div className="space-y-4">
                {filteredCategorized.map(({ group, items }) => (
                  <div key={group} className="border rounded-lg p-4 bg-gray-50">
                    <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide mb-3">
                      {group} ({items.length})
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {items.map((ingredient) => (
                        <div
                          key={ingredient}
                          className="flex items-center gap-2 px-3 py-2 bg-white border-2 border-blue-200 text-blue-800 rounded-lg shadow-sm"
                        >
                          <span className="text-sm font-medium">{ingredient}</span>
                          <button
                            onClick={() => handleRemove(ingredient)}
                            className="text-blue-600 hover:text-blue-800 font-bold text-lg leading-none"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quick Add */}
          <div>
            <h3 className="font-semibold text-gray-900 mb-3">Quick Add</h3>
            <div className="flex flex-wrap gap-2">
              {quickIngredients.map((ingredient) => (
                <Chip
                  key={ingredient}
                  onClick={() => handleQuickAdd(ingredient)}
                  selected={localIngredients.includes(ingredient)}
                >
                  {ingredient}
                </Chip>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              Save
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Preferences Modal Component
interface PreferencesModalProps {
  open: boolean;
  onClose: () => void;
  ingredients: string[];
  isLoading: boolean;
  onStart: (preferences: Preferences) => Promise<void> | void;
}

function PreferencesModal({ open, onClose, ingredients, isLoading, onStart }: PreferencesModalProps) {
  const [time, setTime] = useState<string>("");
  const [style, setStyle] = useState<string>("");
  const [taste, setTaste] = useState<string[]>([]);
  const [dietary, setDietary] = useState<string[]>([]);

  useEffect(() => {
    if (open) {
      setTime("");
      setStyle("");
      setTaste([]);
      setDietary([]);
    }
  }, [open]);

  const handleTasteToggle = (option: string) => {
    setTaste(prev =>
      prev.includes(option)
        ? prev.filter(t => t !== option)
        : [...prev, option]
    );
  };

  const handleDietaryToggle = (option: string) => {
    setDietary(prev =>
      prev.includes(option)
        ? prev.filter(d => d !== option)
        : [...prev, option]
    );
  };

  const handleStart = () => {
    onStart({ time, style, taste, dietary });
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Cooking Preferences</DialogTitle>
          <DialogDescription>Select your preferences to find recipes.</DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Selected Ingredients Summary */}
          <div className="bg-blue-50 rounded-lg p-4">
            <p className="text-sm text-gray-700 mb-2">Selected ingredients:</p>
            <p className="text-gray-900 font-medium">{ingredients.join(", ")}</p>
          </div>

          {/* Time */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Cooking Time</h3>
            <div className="flex flex-wrap gap-2">
              {["Under 15 min", "Under 30 min", "No limit"].map((option) => (
                <Chip
                  key={option}
                  selected={time === option}
                  onClick={() => setTime(option === time ? "" : option)}
                >
                  {option}
                </Chip>
              ))}
            </div>
          </div>

          {/* Style */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Cuisine Style</h3>
            <div className="flex flex-wrap gap-2">
              {["Italian", "Mexican", "American", "Asian-inspired", "Korean"].map((option) => (
                <Chip
                  key={option}
                  selected={style === option}
                  onClick={() => setStyle(option === style ? "" : option)}
                >
                  {option}
                </Chip>
              ))}
            </div>
          </div>

          {/* Taste */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Taste Preference</h3>
            <div className="flex flex-wrap gap-2">
              {["Spicy", "Lighter", "Rich", "Savory"].map((option) => (
                <Chip
                  key={option}
                  selected={taste.includes(option)}
                  onClick={() => handleTasteToggle(option)}
                >
                  {option}
                </Chip>
              ))}
            </div>
          </div>

          {/* Dietary */}
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3">Dietary Restrictions (Optional)</h3>
            <div className="flex flex-wrap gap-2">
              {["Dairy-free", "Gluten-free", "Vegetarian", "Vegan"].map((option) => (
                <Chip
                  key={option}
                  selected={dietary.includes(option)}
                  onClick={() => handleDietaryToggle(option)}
                >
                  {option}
                </Chip>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <button
              onClick={onClose}
              disabled={isLoading}
              className="flex-1 px-4 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleStart}
              disabled={isLoading}
              className="flex-1 px-4 py-3 bg-orange-600 text-white rounded-lg font-medium hover:bg-orange-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {isLoading ? "Finding Recipes..." : "Find Recipes"}
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}