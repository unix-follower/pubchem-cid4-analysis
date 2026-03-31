import { Routes } from "@angular/router"

export const routes: Routes = [
  {
    path: "",
    pathMatch: "full",
    redirectTo: "data-structures",
  },
  {
    path: "data-structures",
    loadComponent: () =>
      import("./features/data-structures/data-structures.page").then(
        (module) => module.DataStructuresPage,
      ),
  },
  {
    path: "algorithms",
    loadComponent: () =>
      import("./features/algorithms/algorithms.page").then((module) => module.AlgorithmsPage),
  },
]
