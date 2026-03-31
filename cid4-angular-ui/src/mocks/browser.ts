import { setupWorker } from "msw/browser"

import { handlers } from "./handlers"

let startPromise: Promise<void> | null = null

export function startMockWorker(): Promise<void> {
  if (globalThis.window === undefined) {
    return Promise.resolve()
  }

  if (startPromise !== null) {
    return startPromise
  }

  const worker = setupWorker(...handlers)

  startPromise = worker
    .start({
      onUnhandledRequest: "bypass",
      serviceWorker: {
        url: "/mockServiceWorker.js",
      },
    })
    .then(() => undefined)

  return startPromise
}
