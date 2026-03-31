import { BootstrapContext, bootstrapApplication } from "@angular/platform-browser"
import { App } from "./app/app"
import { config } from "./app/app.config.server"
import { ensureMockServerStarted } from "./mocks/server"

ensureMockServerStarted()

const bootstrap = (context: BootstrapContext) => bootstrapApplication(App, config, context)

export default bootstrap
