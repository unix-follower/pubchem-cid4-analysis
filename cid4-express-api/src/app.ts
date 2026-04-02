import express from "express"
import type { NextFunction, Request, Response } from "express"

import {
  compoundPath,
  conformerPath,
  isoTimestampUtc,
  loadJsonDocument,
  structure2dPath,
  type ServerConfig,
} from "./config.js"
import { bioactivityFixture, pathwayFixture, taxonomyFixture } from "./fixtures.js"

function applyCors(response: Response): void {
  response.setHeader("Access-Control-Allow-Origin", "*")
  response.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS")
  response.setHeader("Access-Control-Allow-Headers", "Content-Type")
}

function jsonMessage(response: Response, statusCode: number, payload: unknown): void {
  applyCors(response)
  response.status(statusCode).json(payload)
}

async function jsonFileResponse(response: Response, filePath: string): Promise<void> {
  const payload = await loadJsonDocument<unknown>(filePath)
  jsonMessage(response, 200, payload)
}

function asyncRoute(
  handler: (request: Request, response: Response) => Promise<void>,
): (request: Request, response: Response, next: NextFunction) => void {
  return (request, response, next) => {
    void handler(request, response).catch(next)
  }
}

export function createApp(config: ServerConfig) {
  const app = express()

  app.use((request, response, next) => {
    applyCors(response)
    if (request.method === "OPTIONS") {
      response.status(204).end()
      return
    }

    next()
  })

  app.get("/api/health", (request, response) => {
    if (request.query.mode === "error") {
      jsonMessage(response, 503, {
        message: "Transport error from Express",
        source: "express",
        timestamp: isoTimestampUtc(),
      })
      return
    }

    jsonMessage(response, 200, {
      message: "Express transport is healthy",
      source: "express",
      timestamp: isoTimestampUtc(),
    })
  })

  app.get(
    "/api/cid4/conformer/:index",
    asyncRoute(async (request, response) => {
      const indexParam = Array.isArray(request.params.index)
        ? request.params.index[0]
        : request.params.index
      const index = Number.parseInt(indexParam ?? "", 10)
      if (!Number.isInteger(index)) {
        jsonMessage(response, 404, { message: `Unknown conformer ${indexParam ?? ""}` })
        return
      }

      try {
        await jsonFileResponse(response, conformerPath(config.dataDir, index))
      } catch (error) {
        if (error instanceof RangeError) {
          jsonMessage(response, 404, { message: error.message })
          return
        }

        throw error
      }
    }),
  )

  app.get(
    "/api/cid4/structure/2d",
    asyncRoute(async (_request, response) => {
      await jsonFileResponse(response, structure2dPath(config.dataDir))
    }),
  )

  app.get(
    "/api/cid4/compound",
    asyncRoute(async (_request, response) => {
      await jsonFileResponse(response, compoundPath(config.dataDir))
    }),
  )

  app.get("/api/algorithms/pathway", (_request, response) => {
    jsonMessage(response, 200, pathwayFixture)
  })

  app.get("/api/algorithms/bioactivity", (_request, response) => {
    jsonMessage(response, 200, bioactivityFixture)
  })

  app.get("/api/algorithms/taxonomy", (_request, response) => {
    jsonMessage(response, 200, taxonomyFixture)
  })

  app.use((error: unknown, _request: Request, response: Response, _next: NextFunction) => {
    if (error instanceof Error && error.message.startsWith("ENOENT:")) {
      jsonMessage(response, 404, { message: "Missing JSON payload" })
      return
    }

    if (error instanceof Error && error.message.startsWith("Unexpected token")) {
      jsonMessage(response, 500, { message: "Invalid JSON payload" })
      return
    }

    const message = error instanceof Error ? error.message : "Internal server error"
    jsonMessage(response, 500, { message })
  })

  return app
}
