import { ChangeDetectionStrategy, Component, computed, inject, signal } from "@angular/core"
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms"
import { RouterLink } from "@angular/router"

import { AuthSessionService } from "../../core/auth/auth-session.service"
import { LlmClientService, LlmFramework } from "../../core/llm/llm-client.service"

type ChatMessageRole = "system" | "assistant" | "user"

interface ChatMessage {
  role: ChatMessageRole
  text: string
}

@Component({
  selector: "app-chat-page",
  imports: [ReactiveFormsModule, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: "./chat.page.html",
  styleUrl: "./chat.page.css",
})
export class ChatPage {
  private readonly formBuilder = inject(FormBuilder)
  private readonly llmClient = inject(LlmClientService)

  protected readonly authSession = inject(AuthSessionService)
  protected readonly busy = signal(false)
  protected readonly framework = signal<LlmFramework>("pytorch")
  protected readonly transcript = signal<ChatMessage[]>([
    {
      role: "system",
      text: "You are in the protected chat workspace. Responses stream as plain text over the selected transport.",
    },
  ])
  protected readonly errorMessage = signal("")
  protected readonly form = this.formBuilder.nonNullable.group({
    modelName: ["cid4_pytorch_gru_lm", [Validators.required]],
    prompt: ["CID 4 literature summary:", [Validators.required]],
    maxNewTokens: [120, [Validators.required, Validators.min(1), Validators.max(400)]],
    temperature: [0.8, [Validators.required, Validators.min(0), Validators.max(5)]],
    topK: [8, [Validators.required, Validators.min(0), Validators.max(128)]],
  })

  protected readonly selectedProtocolLabel = computed(() => {
    const protocol = this.authSession.selectedProtocol()
    if (protocol === null) {
      return "Unselected"
    }
    return protocol === "websocket" ? "WebSocket" : protocol.toUpperCase()
  })

  protected readonly statusLabel = computed(() => {
    if (this.busy()) {
      return `Streaming over ${this.selectedProtocolLabel()}`
    }
    return `Ready on ${this.selectedProtocolLabel()}`
  })

  protected setFramework(framework: LlmFramework): void {
    this.framework.set(framework)
    this.form.patchValue({
      modelName: framework === "tensorflow" ? "cid4_tensorflow_gru_lm" : "cid4_pytorch_gru_lm",
    })
  }

  protected async submitPrompt(): Promise<void> {
    if (this.form.invalid || this.authSession.selectedProtocol() === null) {
      return
    }

    const value = this.form.getRawValue()
    this.busy.set(true)
    this.errorMessage.set("")
    this.transcript.update((messages) => [...messages, { role: "user", text: value.prompt.trim() }])

    let assistantIndex = -1

    try {
      await this.llmClient.generate(
        this.authSession.selectedProtocol() ?? "http",
        {
          framework: this.framework(),
          prompt: value.prompt.trim(),
          model_name: value.modelName.trim(),
          max_new_tokens: value.maxNewTokens,
          temperature: value.temperature,
          top_k: value.topK,
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
    } finally {
      this.busy.set(false)
    }
  }

  protected clearTranscript(): void {
    this.transcript.set([
      {
        role: "system",
        text: "You are in the protected chat workspace. Responses stream as plain text over the selected transport.",
      },
    ])
    this.errorMessage.set("")
  }

  protected async logout(): Promise<void> {
    await this.authSession.logout()
  }
}
