import { provideHttpClient, withFetch } from "@angular/common/http"
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from "@angular/core"
import { provideClientHydration, withEventReplay } from "@angular/platform-browser"
import { provideRouter } from "@angular/router"
import { provideTanStackQuery } from "@tanstack/angular-query-experimental"

import { routes } from "./app.routes"
import { APP_QUERY_CLIENT } from "./app.query-client"

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(withFetch()),
    provideRouter(routes),
    provideClientHydration(withEventReplay()),
    provideTanStackQuery(APP_QUERY_CLIENT),
  ],
}
