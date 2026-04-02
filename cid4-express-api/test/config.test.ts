import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"

import { afterEach, describe, expect, it } from "vitest"

import { resolveDataDir, resolveServerConfig } from "../src/config.js"

const originalEnvironment = { ...process.env }

async function createTempDataDir(): Promise<string> {
  const directory = await mkdtemp(path.join(os.tmpdir(), "pubchem-cid4-express-tests-"))
  await writeFile(path.join(directory, "COMPOUND_CID_4.json"), "{}")
  await writeFile(path.join(directory, "Structure2D_COMPOUND_CID_4.json"), '{"PC_Compounds": []}')
  await writeFile(path.join(directory, "Conformer3D_COMPOUND_CID_4(1).json"), '{"PC_Compounds": []}')
  return directory
}

afterEach(() => {
  process.env = { ...originalEnvironment }
})

describe("config", () => {
  it("prefers explicit DATA_DIR", async () => {
    const directory = await createTempDataDir()
    process.env.DATA_DIR = directory

    await expect(resolveDataDir()).resolves.toBe(directory)
    await rm(directory, { force: true, recursive: true })
  })

  it("falls back to crypto summary for TLS config", async () => {
    const directory = await createTempDataDir()
    process.env.EXPRESS_HOST = "127.0.0.1"
    process.env.EXPRESS_PORT = "9555"
    delete process.env.TLS_CERT_FILE
    delete process.env.TLS_KEY_FILE
    delete process.env.TLS_KEY_PASSWORD

    const certPath = path.join(directory, "cid4.demo.cert.pem")
    const keyPath = path.join(directory, "cid4.demo.key.pem")
    await writeFile(certPath, "demo-cert")
    await writeFile(keyPath, "demo-key")

    const summaryPath = path.join(directory, "out", "crypto", "cid4_crypto.summary.json")
    await mkdir(path.dirname(summaryPath), { recursive: true })
    await writeFile(
      summaryPath,
      JSON.stringify({
        demo_password: "test-secret",
        x509_and_pkcs12: {
          pem_paths: {
            certificate: certPath,
            private_key: keyPath,
          },
        },
      }),
    )

    const config = await resolveServerConfig(directory)
    expect(config.host).toBe("127.0.0.1")
    expect(config.port).toBe(9555)
    expect(config.keyPassword).toBe("test-secret")
    expect(config.certFile).toBe(certPath)
    expect(config.keyFile).toBe(keyPath)

    await rm(directory, { force: true, recursive: true })
  })
})
