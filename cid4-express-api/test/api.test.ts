import { request as httpsRequest } from "node:https"

import request from "supertest"
import { afterAll, beforeAll, describe, expect, it } from "vitest"

import { createApp } from "../src/app.js"
import { resolveDataDir, resolveServerConfig } from "../src/config.js"
import { startServer } from "../src/server.js"

let dataDir = ""

beforeAll(async () => {
  dataDir = await resolveDataDir()
})

describe("express api", () => {
  it("serves health and error health responses", async () => {
    const app = createApp({ ...(await resolveServerConfig(dataDir)), dataDir })

    const healthy = await request(app).get("/api/health")
    expect(healthy.status).toBe(200)
    expect(healthy.body.source).toBe("express")

    const error = await request(app).get("/api/health?mode=error")
    expect(error.status).toBe(503)
    expect(error.body.source).toBe("express")
  })

  it("serves conformer, compound, and algorithm routes", async () => {
    const app = createApp({ ...(await resolveServerConfig(dataDir)), dataDir })

    const conformer = await request(app).get("/api/cid4/conformer/1")
    expect(conformer.status).toBe(200)
    expect(conformer.body).toHaveProperty("PC_Compounds")

    const unknownConformer = await request(app).get("/api/cid4/conformer/99")
    expect(unknownConformer.status).toBe(404)
    expect(unknownConformer.body.message).toContain("Unknown conformer")

    const compound = await request(app).get("/api/cid4/compound")
    expect(compound.status).toBe(200)
    expect(compound.body).toHaveProperty("Record")

    const pathway = await request(app).get("/api/algorithms/pathway")
    expect(pathway.status).toBe(200)
    expect(pathway.body).toHaveProperty("graph")
  })
})

describe("https smoke", () => {
  let server: Awaited<ReturnType<typeof startServer>> | undefined
  let port = 0

  beforeAll(async () => {
    process.env.EXPRESS_HOST = "127.0.0.1"
    process.env.EXPRESS_PORT = "9556"
    server = await startServer([])
    port = 9556
  })

  afterAll(async () => {
    await new Promise<void>((resolve, reject) => {
      if (!server) {
        resolve()
        return
      }

      server.close((error) => {
        if (error) {
          reject(error)
          return
        }

        resolve()
      })
    })
  })

  it("answers over https", async () => {
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
    expect(JSON.parse(payload.body)).toHaveProperty("source", "express")
  })
})
