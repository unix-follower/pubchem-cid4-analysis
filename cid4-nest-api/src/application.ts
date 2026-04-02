import "reflect-metadata"

import { NestFactory } from "@nestjs/core"
import type { INestApplication } from "@nestjs/common"
import { readFileSync } from "node:fs"
import type { NextFunction, Request, Response } from "express"

import { AppModule } from "./app.module.js"
import type { ServerConfig } from "./config.js"

function applyCors(response: Response): void {
  response.setHeader("Access-Control-Allow-Origin", "*")
  response.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS")
  response.setHeader("Access-Control-Allow-Headers", "Content-Type")
}

function applyServerDefaults(app: INestApplication): void {
  app.use((request: Request, response: Response, next: NextFunction) => {
    applyCors(response)
    if (request.method === "OPTIONS") {
      response.status(204).end()
      return
    }

    next()
  })
}

export async function createApp(
  config: ServerConfig,
  options: { https?: boolean } = {},
): Promise<INestApplication> {
  const app = await NestFactory.create(AppModule.register(config), {
    logger: false,
    httpsOptions: options.https
      ? {
          cert: readFileSync(config.certFile),
          key: readFileSync(config.keyFile),
          passphrase: config.keyPassword,
        }
      : undefined,
  })

  applyServerDefaults(app)
  await app.init()
  return app
}
