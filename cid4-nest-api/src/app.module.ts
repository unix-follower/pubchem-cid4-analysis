import { DynamicModule, Module } from "@nestjs/common"

import { ApiController } from "./api.controller.js"
import { ApiService } from "./api.service.js"
import { SERVER_CONFIG } from "./constants.js"
import type { ServerConfig } from "./config.js"

@Module({})
export class AppModule {
  static register(config: ServerConfig): DynamicModule {
    return {
      module: AppModule,
      controllers: [ApiController],
      providers: [
        ApiService,
        {
          provide: SERVER_CONFIG,
          useValue: config,
        },
      ],
    }
  }
}
