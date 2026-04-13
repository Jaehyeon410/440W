import { createBrowserRouter } from "react-router";
import Home from "./screens/Home";
import ResultsList from "./screens/ResultsList";
import RecipeDetail from "./screens/RecipeDetail";
import FinalRecipe from "./screens/FinalRecipe";
import RecipeStepDetail from "./screens/RecipeStepDetail";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Home,
  },
  {
    path: "/results",
    Component: ResultsList,
  },
  {
    path: "/recipe/:id",
    Component: RecipeDetail,
  },
  {
    path: "/final/:id",
    Component: FinalRecipe,
  },
  {
    path: "/recipe/:id/step/:stepIndex",
    Component: RecipeStepDetail,
  },
]);