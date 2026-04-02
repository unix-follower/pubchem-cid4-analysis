import { request as httpsRequest } from "node:https"

import request from "supertest"
import { afterAll, describe, expect, it } from "vitest"

import { createApp } from "../src/application.js"
import { resolveDataDir, resolveServerConfig } from "../src/config.js"
import { startServer } from "../src/main.js"

let dataDir = ""

async function createTestApp() {
  dataDir = dataDir || (await resolveDataDir())
  return createApp({ ...(await resolveServerConfig(dataDir)), dataDir })
}

describe("nestjs api", () => {
  it("serves health and error health responses", async () => {
    const app = await createTestApp()

    const healthy = await request(app.getHttpServer()).get("/api/health")
    expect(healthy.status).toBe(200)
    expect(healthy.body.source).toBe("nestjs")

    const error = await request(app.getHttpServer()).get("/api/health?mode=error")
    expect(error.status).toBe(503)
    expect(error.body.source).toBe("nestjs")

    await app.close()
  })

  it("serves conformer, compound, and algorithm routes", async () => {
    const app = await createTestApp()

    const conformer = await request(app.getHttpServer()).get("/api/cid4/conformer/1")
    expect(conformer.status).toBe(200)
    expect(conformer.body).toHaveProperty("PC_Compounds")

    const unknownConformer = await request(app.getHttpServer()).get("/api/cid4/conformer/99")
    expect(unknownConformer.status).toBe(404)
    expect(unknownConformer.body.message).toContain("Unknown conformer")

    const compound = await request(app.getHttpServer()).get("/api/cid4/compound")
    expect(compound.status).toBe(200)
    expect(compound.body).toHaveProperty("Record")

    const pathway = await request(app.getHttpServer()).get("/api/algorithms/pathway")
    expect(pathway.status).toBe(200)
    expect(pathway.body).toHaveProperty("graph")

    await app.close()
  })
})

describe("https smoke", () => {
  let app: Awaited<ReturnType<typeof startServer>> | undefined
  let port = 0

  afterAll(async () => {
    await app?.close()
  })

  it("answers over https", async () => {
    process.env.NEST_HOST = "127.0.0.1"
    process.env.NEST_PORT = "9566"
    app = await startServer([])
    port = 9566

    const payload = await new Promise<{ statusCode: number; body: string }>((resolve, reject) => {
      const req = httpsRequest(
        {
          hostname: "127.0.0.1",
          port,
          path: "/api/health",
          method: "GET",
          rejectUnauthorized: false,
        },
        (response) => {
          let body = ""
          response.setEncoding("utf8")
          response.on("data", (chunk) => {
            body += chunk
          })
          response.on("end", () => {
            resolve({ statusCode: response.statusCode ?? 0, body })
          })
        },
      )

      req.on("error", reject)
      req.end()
    })

    expect(payload.statusCode).toBe(200)
    expect(JSON.parse(payload.body)).toHaveProperty("source", "nestjs")
  })
})
