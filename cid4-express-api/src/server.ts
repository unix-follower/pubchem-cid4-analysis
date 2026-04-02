import { createServer } from "node:https"
import { readFileSync } from "node:fs"

import { createApp } from "./app.js"
import { resolveDataDir, resolveServerConfig } from "./config.js"

function hostOverride(argv: readonly string[]): string | undefined {
  const index = argv.indexOf("--host")
  return index >= 0 && index + 1 < argv.length ? argv[index + 1] : undefined
}

function portOverride(argv: readonly string[]): number | undefined {
  const index = argv.indexOf("--port")
  if (index < 0 || index + 1 >= argv.length) {
    return undefined
  }

  const parsed = Number.parseInt(argv[index + 1] ?? "", 10)
  return Number.isInteger(parsed) && parsed > 0 && parsed <= 65535 ? parsed : undefined
}

export async function startServer(argv: readonly string[] = process.argv.slice(2)) {
  const dataDir = await resolveDataDir()
  const config = await resolveServerConfig(dataDir)

  const host = hostOverride(argv) ?? config.host
  const port = portOverride(argv) ?? config.port
  const app = createApp({ ...config, host, port })

  const httpsServer = createServer(
    {
      cert: readFileSync(config.certFile),
      key: readFileSync(config.keyFile),
      passphrase: config.keyPassword,
    },
    app,
  )

  await new Promise<void>((resolve, reject) => {
    httpsServer.once("error", reject)
    httpsServer.listen(port, host, () => {
      httpsServer.off("error", reject)
      resolve()
    })
  })

  console.log(`Express API server listening on https://${host}:${port}`)
  return httpsServer
}

if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    await startServer()
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.error(`Failed to start Express API server: ${message}`)
    process.exitCode = 1
  }
}
