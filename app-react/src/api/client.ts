type JsonValue = Record<string, unknown> | unknown[];

const env = ((import.meta as unknown as { env?: Record<string, string | undefined> }).env || {}) as Record<
  string,
  string | undefined
>;

const rawBaseUrl =
  env.VITE_API_URL ||
  env.REACT_APP_API_URL ||
  "http://127.0.0.1:8000";

export const API_BASE_URL = rawBaseUrl.replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 60000;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(REQUEST_TIMEOUT_MS / 1000)}s`);
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const errorJson = (await response.json()) as { detail?: string };
      if (errorJson?.detail) {
        message = errorJson.detail;
      }
    } catch {
      const text = await response.text();
      if (text) {
        message = text;
      }
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export interface PreferencesPayload {
  time_limit: number;
  spicy: boolean;
  lighter: boolean;
  cuisine: string;
}

export interface DietaryPayload {
  dairy_free: boolean;
  gluten_free: boolean;
}

export interface RecommendRecipe {
  id: string;
  title: string;
  time_minutes: number;
  cook_now: boolean;
  missing_main: string[];
  missing_seasoning: string[];
  missing_other?: string[];
  match_percent: number;
}

export interface RecommendResponse {
  recipes: RecommendRecipe[];
}

export interface RecipeIngredientStatus {
  name: string;
  status: "available" | "missing" | "unknown";
}

export interface RecipeDetailResponse {
  id: string;
  title: string;
  ingredients: RecipeIngredientStatus[];
  steps: string[];
  missing_main: string[];
  missing_seasoning: string[];
  missing_other: string[];
  ingredient_importance?: Record<string, number>;
}

export interface SubstitutionOption {
  to: string;
  reason: string;
  confidence?: number;
}

export interface OtherSubstitutionOption {
  to: string;
  reason: string;
  confidence: number;
}

export interface OtherOptionsEntry {
  category: "produce" | "starch" | "dairy" | "protein" | "seasoning" | "fat" | "liquid" | "misc";
  suggested: OtherSubstitutionOption[];
  fallback_actions: Array<"skip" | "add_to_shopping_list">;
}

export interface SubstitutionsResponse {
  main_options: Record<string, SubstitutionOption[]>;
  seasoning_options: Record<
    string,
    {
      similar: SubstitutionOption[];
      different: SubstitutionOption[];
    }
  >;
  other_options: Record<string, OtherOptionsEntry>;
  other_notes: Record<string, string>;
}

export interface RemixResponse {
  recipe_id?: string;
  substitutions: {
    main: Array<{ from: string; to: string; reason: string }>;
    seasoning: Array<{ from: string; to: string; reason: string }>;
    other?: Array<{ from: string; to: string; reason: string }>;
  };
  flavor_change_summary: string;
  edited_steps: string[];
  changed_steps: number[];
  substitution_explanations: Record<string, string>;
  method_adjustment_notes?: Record<string, string>;
  step_tips?: string[];
  missing_remaining: string[];
}

export function recommend(payload: {
  ingredients: string[];
  preferences: PreferencesPayload;
  dietary?: DietaryPayload;
  allergies?: string[];
}): Promise<RecommendResponse> {
  return request<RecommendResponse>("/api/recommend", {
    method: "POST",
    body: JSON.stringify(payload as JsonValue),
  });
}

export function getRecipeDetail(recipeId: string, userIngredients: string[]): Promise<RecipeDetailResponse> {
  const encodedIngredients = encodeURIComponent(userIngredients.join(","));
  return request<RecipeDetailResponse>(`/api/recipe/${recipeId}?user_ingredients=${encodedIngredients}`);
}

export function getSubstitutions(payload: {
  recipe_id: string;
  user_ingredients: string[];
  missing_main: string[];
  missing_seasoning: string[];
  missing_other: string[];
  preferences?: PreferencesPayload;
  dietary?: DietaryPayload;
  allergies?: string[];
}): Promise<SubstitutionsResponse> {
  return request<SubstitutionsResponse>("/api/substitutions", {
    method: "POST",
    body: JSON.stringify(payload as JsonValue),
  });
}

export function remixRecipe(payload: {
  recipe_id: string;
  user_ingredients: string[];
  selected_main_subs: Record<string, string>;
  selected_seasoning_subs: Record<string, string>;
  selected_other_subs?: Record<string, string>;
  preferences: PreferencesPayload;
}): Promise<RemixResponse> {
  return request<RemixResponse>("/api/remix", {
    method: "POST",
    body: JSON.stringify(payload as JsonValue),
  });
}
