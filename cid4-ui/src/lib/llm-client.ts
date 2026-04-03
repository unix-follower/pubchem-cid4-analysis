export type LlmProtocol = "http" | "sse" | "websocket"
export type LlmFramework = "pytorch" | "tensorflow"

export interface LlmGenerateRequest {
  framework: LlmFramework
  prompt: string
  model_name: string
  max_new_tokens: number
  temperature: number
  top_k: number
}

export interface LlmStreamEvent {
  event: "start" | "token" | "complete" | "error"
  framework?: string
  model_name?: string
  prompt?: string
  text?: string
  generated_text?: string
  generated_suffix?: string
  error?: {
    code: string
    message: string
  }
}

interface FetchApiOwner {
  fetchApi: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
}

export class LlmClient {
  constructor(private readonly authSession: FetchApiOwner) {}

  async generate(
    protocol: LlmProtocol,
    request: LlmGenerateRequest,
    onEvent: (event: LlmStreamEvent) => void,
  ) {
    if (protocol === "http") {
      await this.generateHttp(request, onEvent)
      return
    }

    if (protocol === "sse") {
      await this.generateSse(request, onEvent)
      return
    }

    await this.generateWebSocket(request, onEvent)
  }

  private async generateHttp(
    request: LlmGenerateRequest,
    onEvent: (event: LlmStreamEvent) => void,
  ) {
    onEvent({
      event: "start",
      framework: request.framework,
      model_name: request.model_name,
      prompt: request.prompt,
    })

    const response = await this.authSession.fetchApi("/api/llm/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    })

    const payload = (await response.json()) as Record<string, unknown>
    if (!response.ok || payload.status === "error") {
      const error = payload.error as { code: string; message: string } | undefined
      onEvent({
        event: "error",
        framework: request.framework,
        error: {
          code: error?.code ?? "http_error",
          message: error?.message ?? `Request failed with status ${response.status}`,
        },
      })
      return
    }

    onEvent({
      event: "complete",
      framework: stringValue(payload.framework, request.framework),
      model_name: stringValue(payload.model_name, request.model_name),
      prompt: stringValue(payload.prompt, request.prompt),
      generated_text: stringValue(payload.generated_text, ""),
      generated_suffix: stringValue(payload.generated_suffix, ""),
    })
  }

  private async generateSse(request: LlmGenerateRequest, onEvent: (event: LlmStreamEvent) => void) {
    const response = await this.authSession.fetchApi("/api/llm/generate/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    })

    if (!response.ok || !response.body) {
      onEvent({
        event: "error",
        framework: request.framework,
        error: {
          code: "sse_unavailable",
          message: `Streaming request failed with status ${response.status}`,
        },
      })
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
      const { value, done } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split("\n\n")
      buffer = frames.pop() ?? ""

      for (const frame of frames) {
        const event = parseSseFrame(frame)
        if (event) {
          onEvent(event)
        }
      }
    }
  }

  private async generateWebSocket(
    request: LlmGenerateRequest,
    onEvent: (event: LlmStreamEvent) => void,
  ) {
    if (globalThis.window === undefined) {
      onEvent({
        event: "error",
        framework: request.framework,
        error: {
          code: "websocket_unavailable",
          message: "WebSocket transport is only available in the browser.",
        },
      })
      return
    }

    const url = new URL("/ws/llm/generate", globalThis.window.location.origin)
    url.protocol = globalThis.window.location.protocol === "https:" ? "wss:" : "ws:"

    await new Promise<void>((resolve) => {
      const socket = new WebSocket(url)
      let completed = false

      socket.addEventListener("open", () => {
        socket.send(JSON.stringify(request))
      })

      socket.addEventListener("message", (message) => {
        const event = JSON.parse(String(message.data)) as LlmStreamEvent
        onEvent(event)
        if (event.event === "complete" || event.event === "error") {
          completed = true
          socket.close(1000)
        }
      })

      socket.addEventListener("error", () => {
        onEvent({
          event: "error",
          framework: request.framework,
          error: {
            code: "websocket_error",
            message: "WebSocket generation failed.",
          },
        })
      })

      socket.addEventListener("close", () => {
        if (!completed) {
          onEvent({
            event: "error",
            framework: request.framework,
            error: {
              code: "websocket_closed",
              message: "The WebSocket closed before generation completed.",
            },
          })
        }
        resolve()
      })
    })
  }
}

function parseSseFrame(frame: string): LlmStreamEvent | null {
  const lines = frame
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
  const dataLine = lines.find((line) => line.startsWith("data:"))

  if (!dataLine) {
    return null
  }

  return JSON.parse(dataLine.slice(5).trim()) as LlmStreamEvent
}

function stringValue(value: unknown, fallback: string) {
  return typeof value === "string" ? value : fallback
}
