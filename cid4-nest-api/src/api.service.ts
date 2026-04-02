import { Inject, Injectable } from "@nestjs/common"

import { SERVER_CONFIG } from "./constants.js"
import {
  compoundPath,
  conformerPath,
  isoTimestampUtc,
  loadJsonDocument,
  structure2dPath,
  type ServerConfig,
} from "./config.js"
import { bioactivityFixture, pathwayFixture, taxonomyFixture } from "./fixtures.js"

@Injectable()
export class ApiService {
  constructor(@Inject(SERVER_CONFIG) private readonly config: ServerConfig) {}

  healthyPayload(): { message: string; source: string; timestamp: string } {
    return {
      message: "NestJS transport is healthy",
      source: "nestjs",
      timestamp: isoTimestampUtc(),
    }
  }

  errorPayload(): { message: string; source: string; timestamp: string } {
    return {
      message: "Transport error from NestJS",
      source: "nestjs",
      timestamp: isoTimestampUtc(),
    }
  }

  async conformer(index: number): Promise<unknown> {
    return loadJsonDocument<unknown>(conformerPath(this.config.dataDir, index))
  }

  async structure2d(): Promise<unknown> {
    return loadJsonDocument<unknown>(structure2dPath(this.config.dataDir))
  }

  async compound(): Promise<unknown> {
    return loadJsonDocument<unknown>(compoundPath(this.config.dataDir))
  }

  pathway(): typeof pathwayFixture {
    return pathwayFixture
  }

  bioactivity(): typeof bioactivityFixture {
    return bioactivityFixture
  }

  taxonomy(): typeof taxonomyFixture {
    return taxonomyFixture
  }
}
