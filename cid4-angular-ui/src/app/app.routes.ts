import { Routes } from "@angular/router"

import { authGuard, protocolGuard } from "./core/auth/auth.guards"

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
  {
    path: "auth",
    pathMatch: "full",
    loadComponent: () =>
      import("./features/chatbot/auth-home.page").then((module) => module.AuthHomePage),
  },
  {
    path: "auth/basic",
    loadComponent: () =>
      import("./features/chatbot/basic-auth.page").then((module) => module.BasicAuthPage),
  },
  {
    path: "auth/digest",
    loadComponent: () =>
      import("./features/chatbot/digest-auth.page").then((module) => module.DigestAuthPage),
  },
  {
    path: "auth/oauth2",
    loadComponent: () =>
      import("./features/chatbot/oauth2-auth.page").then((module) => module.OAuth2AuthPage),
  },
  {
    path: "chat/protocol",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./features/chatbot/protocol.page").then((module) => module.ProtocolPage),
  },
  {
    path: "chat/workspace",
    canActivate: [authGuard, protocolGuard],
    loadComponent: () => import("./features/chatbot/chat.page").then((module) => module.ChatPage),
  },
  {
    path: "llm",
    pathMatch: "full",
    redirectTo: "auth",
  },
]
