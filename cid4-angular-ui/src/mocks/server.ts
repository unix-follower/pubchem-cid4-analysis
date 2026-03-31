import { setupServer } from "msw/node"

import { handlers } from "./handlers"

const mockServer = setupServer(...handlers)

let started = false

export function ensureMockServerStarted(): void {
  if (started) {
    return
  }

  mockServer.listen({
    onUnhandledRequest: "bypass",
  })

  started = true
}
