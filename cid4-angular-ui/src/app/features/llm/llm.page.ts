import { CommonModule } from "@angular/common"
import { ChangeDetectionStrategy, Component, computed, inject, signal } from "@angular/core"
import { FormsModule } from "@angular/forms"

import { LlmClientService, LlmFramework, LlmProtocol } from "../../core/llm/llm-client.service"

type ChatMessageRole = "system" | "assistant" | "user"

interface ChatMessage {
  role: ChatMessageRole
  text: string
}

@Component({
  selector: "app-llm-page",
  standalone: true,
  imports: [CommonModule, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./llm.page.html",
  styleUrl: "./llm.page.css",
})
export class LlmPage {
  private readonly llmClient = inject(LlmClientService)

  protected readonly protocol = signal<LlmProtocol>("http")
  protected readonly framework = signal<LlmFramework>("pytorch")
  protected readonly busy = signal(false)
  protected readonly transcript = signal<ChatMessage[]>([
    {
      role: "system",
      text: "Choose a protocol, send a prompt, and compare how the same FastAPI LLM response arrives over HTTP, SSE, or WebSocket.",
    },
  ])
  protected readonly errorMessage = signal("")

  protected prompt = "CID 4 literature summary:"
  protected modelName = "cid4_pytorch_gru_lm"
  protected maxNewTokens = 120
  protected temperature = 0.8
  protected topK = 8

  protected readonly statusLabel = computed(() => {
    if (this.busy()) {
      return `Streaming via ${this.protocol().toUpperCase()}`
    }
    return "Idle"
  })

  protected setProtocol(protocol: LlmProtocol): void {
    this.protocol.set(protocol)
    this.errorMessage.set("")
  }

  protected setFramework(framework: LlmFramework): void {
    this.framework.set(framework)
    this.errorMessage.set("")
    if (framework === "tensorflow" && this.modelName === "cid4_pytorch_gru_lm") {
      this.modelName = "cid4_tensorflow_gru_lm"
    }
    if (framework === "pytorch" && this.modelName === "cid4_tensorflow_gru_lm") {
      this.modelName = "cid4_pytorch_gru_lm"
    }
  }

  protected async submitPrompt(): Promise<void> {
    const trimmedPrompt = this.prompt.trim()
    if (!trimmedPrompt) {
      this.errorMessage.set("Prompt must not be empty.")
      return
    }

    this.busy.set(true)
    this.errorMessage.set("")
    this.transcript.update((messages) => [...messages, { role: "user", text: trimmedPrompt }])
    let assistantIndex = -1

    await this.llmClient.generate(
      this.protocol(),
      {
        framework: this.framework(),
        prompt: trimmedPrompt,
        model_name: this.modelName.trim() || "cid4_pytorch_gru_lm",
        max_new_tokens: this.maxNewTokens,
        temperature: this.temperature,
        top_k: this.topK,
      },
      (event) => {
        if (event.event === "start") {
          this.transcript.update((messages) => {
            const nextMessages: ChatMessage[] = [...messages, { role: "assistant", text: "" }]
            assistantIndex = nextMessages.length - 1
            return nextMessages
          })
          return
        }

        if (event.event === "token") {
          this.transcript.update((messages) => {
            if (assistantIndex < 0 || !messages[assistantIndex]) {
              return messages
            }
            const nextMessages = [...messages]
            nextMessages[assistantIndex] = {
              ...nextMessages[assistantIndex],
              text:
                event.generated_text ?? `${nextMessages[assistantIndex].text}${event.text ?? ""}`,
            }
            return nextMessages
          })
          return
        }

        if (event.event === "complete") {
          this.transcript.update((messages) => {
            if (assistantIndex < 0 || !messages[assistantIndex]) {
              return [...messages, { role: "assistant", text: event.generated_text ?? "" }]
            }
            const nextMessages = [...messages]
            nextMessages[assistantIndex] = {
              ...nextMessages[assistantIndex],
              text: event.generated_text ?? nextMessages[assistantIndex].text,
            }
            return nextMessages
          })
          return
        }

        if (event.event === "error") {
          this.errorMessage.set(event.error?.message ?? "Generation failed.")
        }
      },
    )

    this.busy.set(false)
  }

  protected clearTranscript(): void {
    this.transcript.set([
      {
        role: "system",
        text: "Choose a protocol, send a prompt, and compare how the same FastAPI LLM response arrives over HTTP, SSE, or WebSocket.",
      },
    ])
    this.errorMessage.set("")
  }
}
