import { Controller, Get, Param, Query, Res } from "@nestjs/common"
import type { Response } from "express"

import { ApiService } from "./api.service.js"

function jsonMessage(response: Response, statusCode: number, payload: unknown): void {
  response.status(statusCode).json(payload)
}

function handleRouteError(response: Response, error: unknown): void {
  if (error instanceof RangeError) {
    jsonMessage(response, 404, { message: error.message })
    return
  }

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
}

@Controller("api")
export class ApiController {
  constructor(private readonly apiService: ApiService) {}

  @Get("health")
  health(@Query("mode") mode: string | undefined, @Res() response: Response): void {
    if (mode === "error") {
      jsonMessage(response, 503, this.apiService.errorPayload())
      return
    }

    jsonMessage(response, 200, this.apiService.healthyPayload())
  }

  @Get("cid4/conformer/:index")
  async conformer(@Param("index") indexParam: string, @Res() response: Response): Promise<void> {
    const index = Number.parseInt(indexParam ?? "", 10)
    if (!Number.isInteger(index)) {
      jsonMessage(response, 404, { message: `Unknown conformer ${indexParam ?? ""}` })
      return
    }

    try {
      jsonMessage(response, 200, await this.apiService.conformer(index))
    } catch (error) {
      handleRouteError(response, error)
    }
  }

  @Get("cid4/structure/2d")
  async structure2d(@Res() response: Response): Promise<void> {
    try {
      jsonMessage(response, 200, await this.apiService.structure2d())
    } catch (error) {
      handleRouteError(response, error)
    }
  }

  @Get("cid4/compound")
  async compound(@Res() response: Response): Promise<void> {
    try {
      jsonMessage(response, 200, await this.apiService.compound())
    } catch (error) {
      handleRouteError(response, error)
    }
  }

  @Get("algorithms/pathway")
  pathway(@Res() response: Response): void {
    jsonMessage(response, 200, this.apiService.pathway())
  }

  @Get("algorithms/bioactivity")
  bioactivity(@Res() response: Response): void {
    jsonMessage(response, 200, this.apiService.bioactivity())
  }

  @Get("algorithms/taxonomy")
  taxonomy(@Res() response: Response): void {
    jsonMessage(response, 200, this.apiService.taxonomy())
  }
}
