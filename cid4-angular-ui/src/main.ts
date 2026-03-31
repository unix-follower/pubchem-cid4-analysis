import { bootstrapApplication } from "@angular/platform-browser"
import { appConfig } from "./app/app.config"
import { App } from "./app/app"
import { startMockWorker } from "./mocks/browser"

try {
  await startMockWorker()
} catch (error) {
  console.error("Failed to start MSW browser worker", error)
}

try {
  await bootstrapApplication(App, appConfig)
} catch (error) {
  console.error(error)
}
